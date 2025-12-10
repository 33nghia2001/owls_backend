# backend/apps/payments/views.py

import logging
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle

from .models import Payment, VNPayTransaction, Discount, DiscountUsage
from .serializers import (
    PaymentSerializer,
    VNPayTransactionSerializer,
    DiscountSerializer,
    ApplyDiscountSerializer
)
from .vnpay import create_vnpay_payment_url, VNPay, get_vnpay_response_message
from .tasks import send_payment_success_email, send_enrollment_confirmation_email
from apps.enrollments.models import Enrollment
from apps.courses.models import Course

logger = logging.getLogger(__name__)


# ==============================================================================
# HELPER FUNCTIONS (Service Layer)
# ==============================================================================

def process_payment_confirmation(payment, vnp_params):
    """
    Xử lý logic xác nhận thanh toán thành công.
    Được gọi bởi cả IPN và Return URL để tránh lặp code.
    
    Args:
        payment (Payment): Payment object đã được lock (select_for_update)
        vnp_params (dict): Dữ liệu từ VNPay
    
    Returns:
        bool: True nếu xử lý thành công, False nếu thất bại
    """
    vnp_response_code = vnp_params.get('vnp_ResponseCode')
    
    # 1. Cập nhật thông tin transaction
    vnpay_transaction = payment.vnpay_transaction
    vnpay_transaction.vnp_ResponseCode = vnp_response_code
    vnpay_transaction.vnp_TransactionNo = vnp_params.get('vnp_TransactionNo')
    vnpay_transaction.vnp_BankCode = vnp_params.get('vnp_BankCode')
    vnpay_transaction.vnp_BankTranNo = vnp_params.get('vnp_BankTranNo')
    vnpay_transaction.vnp_CardType = vnp_params.get('vnp_CardType')
    vnpay_transaction.vnp_PayDate = vnp_params.get('vnp_PayDate')
    vnpay_transaction.response_data = vnp_params
    vnpay_transaction.save()

    # 2. Xử lý trạng thái Payment
    if vnp_response_code == '00':
        payment.status = 'completed'
        payment.paid_at = timezone.now()
        payment.gateway_transaction_id = vnp_params.get('vnp_TransactionNo')
        payment.save()
        
        # Tạo DiscountUsage record
        if payment.discount:
            DiscountUsage.objects.create(
                user=payment.user,
                discount=payment.discount,
                payment=payment,
                amount_saved=payment.discount_amount  # Use calculated amount, not raw value
            )
        
        # Tạo Enrollment (Idempotent: get_or_create)
        enrollment, created = Enrollment.objects.get_or_create(
            student=payment.user,
            course=payment.course,
            defaults={
                'status': 'active',
                'payment': payment
            }
        )
        
        # Gửi Email & Notification (Async Tasks)
        # Chỉ gửi task sau khi transaction đã commit thành công (được gọi ở View)
        return True, created, enrollment.id
    
    else:
        # Thanh toán thất bại
        # Hoàn trả lượt dùng mã giảm giá
        if payment.discount:
            Discount.objects.filter(id=payment.discount.id).update(
                used_count=F('used_count') - 1
            )
            
        payment.status = 'failed'
        payment.save()
        return False, False, None


# ==============================================================================
# VIEW SETS
# ==============================================================================

class PaymentCreateThrottle(UserRateThrottle):
    """
    Limit payment creation to prevent Ghost Payment DOS attacks.
    Rate: 5 requests / hour
    """
    scope = 'payment'


class DiscountCheckThrottle(UserRateThrottle):
    """
    Limit discount code validation to prevent brute-force attacks.
    Rate: 10 requests / hour
    """
    rate = '10/hour'


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet quản lý thanh toán.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_throttles(self):
        """SECURITY FIX: Apply throttles to prevent abuse"""
        if self.action == 'create':
            return [PaymentCreateThrottle()]
        if self.action == 'apply_discount':
            return [DiscountCheckThrottle()]
        return super().get_throttles()
    
    def get_queryset(self):
        if self.request.user.role == 'admin':
            return Payment.objects.all().select_related('user', 'course')
        return Payment.objects.filter(user=self.request.user).select_related('course')
    
    def perform_create(self, serializer):
        """Tạo payment, giữ chỗ discount và tạo URL thanh toán"""
        discount = serializer.validated_data.get('discount')
        
        # 1. Reserve discount slot (Flash Mob Attack Prevention)
        if discount:
            updated = Discount.objects.filter(
                id=discount.id,
                used_count__lt=F('usage_limit')
            ).update(used_count=F('used_count') + 1)
            
            if not updated:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'discount': 'This discount code has reached its usage limit.'})
        
        # 2. Calculate and save original_price and discount_amount
        course = serializer.validated_data['course']
        original_price = course.price
        discount_amount = 0
        
        if discount:
            if discount.discount_type == 'percentage':
                discount_amount = (original_price * discount.discount_value) / 100
                if discount.max_discount_amount:
                    discount_amount = min(discount_amount, discount.max_discount_amount)
            else:
                discount_amount = discount.discount_value
        
        # 3. Save payment with snapshot values
        payment = serializer.save(
            user=self.request.user,
            status='pending',
            original_price=original_price,
            discount_amount=discount_amount,
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
        
        # 3. Generate VNPay URL
        if payment.payment_method == 'vnpay':
            payment_url = create_vnpay_payment_url(payment, self.request)
            payment.gateway_response = {'payment_url': payment_url}
            payment.save(update_fields=['gateway_response'])
    
    def get_client_ip(self):
        """SECURITY FIX: Use django-ipware for accurate IP detection behind proxies"""
        from ipware import get_client_ip
        client_ip, is_routable = get_client_ip(self.request)
        return client_ip or '0.0.0.0'
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Hủy payment và hoàn trả discount slot"""
        payment = self.get_object()
        
        if payment.user != request.user and request.user.role != 'admin':
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        if payment.status != 'pending':
            return Response({'error': 'Only pending payments can be cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            payment.status = 'cancelled'
            payment.save(update_fields=['status'])
            
            # Refund discount slot
            if payment.discount:
                Discount.objects.filter(id=payment.discount.id).update(
                    used_count=F('used_count') - 1
                )
        
        return Response({'status': 'success', 'message': 'Payment cancelled.'})
    
    @action(detail=False, methods=['post'])
    def apply_discount(self, request):
        """API kiểm tra và áp dụng mã giảm giá"""
        serializer = ApplyDiscountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data['code']
        course_id = serializer.validated_data['course_id']
        
        discount = get_object_or_404(Discount, code=code)
        course = get_object_or_404(Course, id=course_id)
        
        # Check min purchase amount
        if discount.min_purchase_amount and course.price < discount.min_purchase_amount:
            return Response({
                'error': f'Minimum purchase amount is {discount.min_purchase_amount} VND'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate final price
        if discount.discount_type == 'percentage':
            discount_amount = course.price * (discount.discount_value / 100)
            if discount.max_discount_amount:
                discount_amount = min(discount_amount, discount.max_discount_amount)
        else:
            discount_amount = discount.discount_value
        
        final_price = max(0, course.price - discount_amount)
        
        return Response({
            'original_price': course.price,
            'discount_amount': discount_amount,
            'final_price': final_price,
            'discount_code': code
        })


class DiscountViewSet(viewsets.ModelViewSet):
    serializer_class = DiscountSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.role == 'admin':
            return Discount.objects.all()
        return Discount.objects.filter(is_active=True)
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsAdminUser()]
        return super().get_permissions()


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.role == 'admin'


# ==============================================================================
# VNPAY HANDLERS
# ==============================================================================

class VNPayReturnView(APIView):
    """
    Handle Redirect from VNPay (Browser-based)
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        vnpay_params = request.GET.dict()
        
        if not vnpay_params:
            return redirect(f'{settings.FRONTEND_URL}/payment-error?error=no_params')
        
        # 1. Validate Signature
        vnpay = VNPay()
        vnpay.response_data = vnpay_params.copy()
        if not vnpay.validate_response(settings.VNPAY_HASH_SECRET):
            return redirect(f'{settings.FRONTEND_URL}/payment-error?error=invalid_signature')
        
        vnp_TxnRef = vnpay_params.get('vnp_TxnRef')
        vnp_ResponseCode = vnpay_params.get('vnp_ResponseCode')
        
        try:
            with transaction.atomic():
                # Lock row to prevent race condition with IPN
                payment = Payment.objects.select_related('user', 'course', 'discount', 'vnpay_transaction')\
                    .select_for_update().get(transaction_id=vnp_TxnRef)
                
                # Check Idempotency
                if payment.status == 'completed':
                    return redirect(f'{settings.FRONTEND_URL}/payment-success?transaction_id={vnp_TxnRef}')
                
                if payment.status == 'failed':
                    return redirect(f'{settings.FRONTEND_URL}/payment-failed?error=already_failed')
                
                # SECURITY FIX: Prevent discount bypass via race condition
                # If payment was cancelled (and discount slot refunded), reject processing
                if payment.status == 'cancelled':
                    return redirect(f'{settings.FRONTEND_URL}/payment-failed?error=payment_cancelled')
                
                # Check Amount (Integer comparison)
                if int(payment.amount * 100) != int(vnpay_params.get('vnp_Amount', '0')):
                    payment.status = 'failed'
                    payment.save()
                    return redirect(f'{settings.FRONTEND_URL}/payment-error?error=amount_mismatch')
                
                # Process Payment
                success, created_enrollment, enrollment_id = process_payment_confirmation(payment, vnpay_params)
                
                if success:
                    # Use transaction.on_commit to prevent Celery race condition
                    # Tasks will only be sent after database transaction commits successfully
                    transaction.on_commit(lambda: send_payment_success_email.delay(payment.id))
                    if created_enrollment:
                        transaction.on_commit(lambda eid=enrollment_id: send_enrollment_confirmation_email.delay(eid))
                    
                    return redirect(f'{settings.FRONTEND_URL}/payment-success?transaction_id={vnp_TxnRef}')
                else:
                    msg = get_vnpay_response_message(vnp_ResponseCode)
                    return redirect(f'{settings.FRONTEND_URL}/payment-failed?error={msg}')
                    
        except Payment.DoesNotExist:
            return redirect(f'{settings.FRONTEND_URL}/payment-error?error=payment_not_found')


class VNPayIPNView(APIView):
    """
    Handle IPN from VNPay (Server-to-Server)
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        vnpay_params = request.GET.dict()
        
        # 1. Validate Signature
        vnpay = VNPay()
        vnpay.response_data = vnpay_params.copy()
        if not vnpay.validate_response(settings.VNPAY_HASH_SECRET):
            return Response({'RspCode': '97', 'Message': 'Invalid Signature'})
        
        vnp_TxnRef = vnpay_params.get('vnp_TxnRef')
        
        try:
            with transaction.atomic():
                # Lock row
                payment = Payment.objects.select_related('user', 'course', 'discount', 'vnpay_transaction')\
                    .select_for_update().get(transaction_id=vnp_TxnRef)
                
                # Check Amount
                if int(payment.amount * 100) != int(vnpay_params.get('vnp_Amount', '0')):
                    return Response({'RspCode': '04', 'Message': 'Invalid Amount'})
                
                # Check Idempotency
                if payment.status != 'pending':
                    return Response({'RspCode': '02', 'Message': 'Order already confirmed'})
                
                # Process Payment
                success, created_enrollment, enrollment_id = process_payment_confirmation(payment, vnpay_params)
                
                if success:
                    # Use transaction.on_commit to prevent Celery race condition
                    transaction.on_commit(lambda: send_payment_success_email.delay(payment.id))
                    if created_enrollment:
                        transaction.on_commit(lambda eid=enrollment_id: send_enrollment_confirmation_email.delay(eid))
            
            return Response({'RspCode': '00', 'Message': 'Confirm Success'})
            
        except Payment.DoesNotExist:
            return Response({'RspCode': '01', 'Message': 'Order not found'})
        except Exception as e:
            logger.error(f"IPN Error: {str(e)}")
            return Response({'RspCode': '99', 'Message': 'Unknown Error'})