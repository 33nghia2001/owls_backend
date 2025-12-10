# backend/apps/payments/views.py

import logging
from decimal import Decimal
from typing import Tuple, Optional, Dict, Any

from django.conf import settings
from django.db import transaction, DatabaseError
from django.db.models import F
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from ipware import get_client_ip

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle
from rest_framework.exceptions import ValidationError

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
# 1. HELPER FUNCTIONS (Service Layer - Pure Logic)
# ==============================================================================

def calculate_payment_amounts(course: Course, discount: Optional[Discount]) -> Tuple[Decimal, Decimal, Decimal]:
    """
    Tính toán giá trị đơn hàng.
    Returns: (original_price, discount_amount, final_price)
    """
    original_price = course.price
    discount_amount = Decimal('0')

    if discount:
        if discount.discount_type == 'percentage':
            calculated_dist = (original_price * discount.discount_value) / 100
            if discount.max_discount_amount:
                discount_amount = min(calculated_dist, discount.max_discount_amount)
            else:
                discount_amount = calculated_dist
        else:
            discount_amount = discount.discount_value
    
    final_price = max(Decimal('0'), original_price - discount_amount)
    return original_price, discount_amount, final_price


def process_payment_confirmation(payment: Payment, vnp_params: Dict[str, Any]) -> Tuple[bool, bool, Optional[int]]:
    """
    Xử lý logic nghiệp vụ khi thanh toán thành công (Update DB, Enroll, Notify).
    Hàm này được gọi bên trong một transaction atomic.
    """
    vnp_response_code = vnp_params.get('vnp_ResponseCode')
    
    # 1. Cập nhật thông tin transaction VNPay
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
                amount_saved=payment.discount_amount
            )
        
        # Tạo Enrollment (Idempotent)
        enrollment, created = Enrollment.objects.get_or_create(
            student=payment.user,
            course=payment.course,
            defaults={
                'status': 'active',
                'payment': payment
            }
        )
        
        # Cập nhật payment reference nếu enrollment đã tồn tại
        if not created and not enrollment.payment:
            enrollment.payment = payment
            enrollment.save(update_fields=['payment'])
        
        return True, created, enrollment.id
    
    else:
        # Thanh toán thất bại -> Hoàn trả discount slot
        if payment.discount:
            Discount.objects.filter(id=payment.discount.id).update(
                used_count=F('used_count') - 1
            )
            
        payment.status = 'failed'
        payment.save()
        return False, False, None


def execute_payment_confirmation(transaction_id: str, vnp_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hàm wrapper xử lý toàn bộ quy trình confirm (Lock DB -> Validate -> Process).
    Dùng chung cho cả IPN và Return URL để tránh lặp code.
    
    Returns: Dict kết quả để View xử lý response.
    """
    try:
        with transaction.atomic():
            # 1. Lock row
            payment = Payment.objects.select_related('user', 'course', 'discount', 'vnpay_transaction')\
                .select_for_update().get(transaction_id=transaction_id)
            
            # 2. Check Idempotency (Tránh xử lý lặp lại)
            if payment.status == 'completed':
                return {'status': 'success', 'code': '00', 'message': 'Payment already completed'}
            
            if payment.status == 'failed':
                return {'status': 'error', 'code': '01', 'message': 'Payment previously failed'}
            
            if payment.status == 'cancelled':
                return {'status': 'error', 'code': '02', 'message': 'Payment was cancelled'}
            
            # 3. Check Amount (So sánh integer để chính xác)
            incoming_amount = int(vnp_params.get('vnp_Amount', '0'))
            expected_amount = int(payment.amount * 100)
            
            if incoming_amount != expected_amount:
                # Đánh dấu failed nếu sai tiền (nghi vấn hack)
                payment.status = 'failed'
                payment.save()
                return {'status': 'error', 'code': '04', 'message': 'Invalid Amount'}
            
            # 4. Process Logic
            success, created_enrollment, enrollment_id = process_payment_confirmation(payment, vnp_params)
            
            if success:
                # Async Tasks (chỉ chạy sau khi commit)
                transaction.on_commit(lambda: send_payment_success_email.delay(payment.id))
                if created_enrollment:
                    transaction.on_commit(lambda eid=enrollment_id: send_enrollment_confirmation_email.delay(eid))
                
                return {'status': 'success', 'code': '00', 'message': 'Confirm Success'}
            else:
                return {'status': 'error', 'code': vnp_params.get('vnp_ResponseCode'), 'message': 'Payment Failed from Gateway'}

    except Payment.DoesNotExist:
        return {'status': 'error', 'code': '01', 'message': 'Order not found'}
    except Exception as e:
        logger.error(f"Payment Confirmation Error: {str(e)}", exc_info=True)
        return {'status': 'error', 'code': '99', 'message': 'Unknown Error'}


# ==============================================================================
# 2. THROTTLES & PERMISSIONS
# ==============================================================================

class PaymentCreateThrottle(UserRateThrottle):
    scope = 'payment'

class DiscountCheckThrottle(UserRateThrottle):
    rate = '10/hour'

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.role == 'admin'


# ==============================================================================
# 3. VIEW SETS
# ==============================================================================

class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet quản lý thanh toán.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_throttles(self):
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
        """
        Tạo payment, giữ chỗ discount và tạo URL thanh toán.
        """
        course = serializer.validated_data['course']
        user = self.request.user
        
        # 1. SECURITY CHECK: Prevent payment if already enrolled
        if Enrollment.objects.filter(
            student=user,
            course=course,
            status__in=['active', 'completed']
        ).exists():
            raise ValidationError({
                'course': 'You are already enrolled in this course.',
                'message': 'Cannot create payment for a course you already have access to.'
            })
        
        discount = serializer.validated_data.get('discount')
        
        # 2. Reserve discount slot
        if discount:
            updated = Discount.objects.filter(
                id=discount.id,
                used_count__lt=F('usage_limit')
            ).update(used_count=F('used_count') + 1)
            
            if not updated:
                raise ValidationError({'discount': 'This discount code has reached its usage limit.'})
        
        # 3. Calculate Prices (SERVER AUTHORITY: Server always decides final price)
        original_price, discount_amount, final_price = calculate_payment_amounts(course, discount)
        
        # 4. Get client metadata
        client_ip, _ = get_client_ip(self.request)
        # DEPLOYMENT WARNING: Ensure IPWARE_TRUSTED_PROXY_LIST is configured in production
        # when behind Cloudflare, Nginx, or AWS ALB to get accurate client IP
        
        # 5. Save payment with SERVER-CALCULATED amounts (ignore client-provided amount)
        payment = serializer.save(
            user=user,
            status='pending',
            amount=final_price,  # CRITICAL: Override client amount with server calculation
            original_price=original_price,
            discount_amount=discount_amount,
            ip_address=client_ip or '0.0.0.0',
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
        
        # 6. SPECIAL CASE: Handle Free Courses / 100% Discount
        if final_price == 0:
            # Auto-complete payment for free courses
            payment.status = 'completed'
            payment.payment_method = 'free'  # Force method to 'free'
            payment.paid_at = timezone.now()
            payment.save()
            
            # Create DiscountUsage if discount was applied
            if discount:
                DiscountUsage.objects.create(
                    user=user,
                    discount=discount,
                    payment=payment,
                    amount_saved=discount_amount
                )
            
            # Create Enrollment immediately (no payment gateway needed)
            enrollment, created = Enrollment.objects.get_or_create(
                student=user,
                course=course,
                defaults={'status': 'active', 'payment': payment}
            )
            
            # Send confirmation email asynchronously
            transaction.on_commit(
                lambda: send_enrollment_confirmation_email.delay(enrollment.id)
            )
            
            logger.info(f"Free enrollment created for user {user.id} in course {course.id}")
            # No VNPay URL needed for free courses
            return
        
        # 7. Generate VNPay URL (Only for paid courses)
        if payment.payment_method == 'vnpay':
            payment_url = create_vnpay_payment_url(payment, self.request)
            payment.gateway_response = {'payment_url': payment_url}
            payment.save(update_fields=['gateway_response'])
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Hủy payment và hoàn trả discount slot.
        Sử dụng Atomic Transaction để chống Race Condition.
        """
        try:
            with transaction.atomic():
                # Lock row immediately
                payment_qs = Payment.objects.select_for_update()
                
                if request.user.role == 'admin':
                    payment = get_object_or_404(payment_qs, pk=pk)
                else:
                    payment = get_object_or_404(payment_qs, pk=pk, user=request.user)
                
                if payment.status != 'pending':
                    return Response(
                        {'error': 'Only pending payments can be cancelled.'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Update status
                payment.status = 'cancelled'
                payment.save(update_fields=['status'])
                
                # Refund discount slot
                if payment.discount:
                    Discount.objects.filter(id=payment.discount.id).update(
                        used_count=F('used_count') - 1
                    )
                    
            return Response({'status': 'success', 'message': 'Payment cancelled.'})

        except Exception as e:
            logger.error(f"Cancel Payment Error: {e}")
            return Response({'error': 'System error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        
        # Calculate final price (DRY: Reusing helper function)
        original_price, discount_amount, final_price = calculate_payment_amounts(course, discount)
        
        return Response({
            'original_price': original_price,
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


# ==============================================================================
# 4. VNPAY HANDLERS (Views)
# ==============================================================================

class VNPayReturnView(APIView):
    """
    Handle Redirect from VNPay (Browser-based).
    Redirects user to Frontend based on result.
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
        
        # 2. Execute Payment Logic (Atomic & Locked)
        result = execute_payment_confirmation(vnp_TxnRef, vnpay_params)
        
        # 3. Handle Redirects
        if result['status'] == 'success':
            return redirect(f'{settings.FRONTEND_URL}/payment-success?transaction_id={vnp_TxnRef}')
        elif result['code'] == '00': 
            # Trường hợp success nhưng idempotent check trả về success
             return redirect(f'{settings.FRONTEND_URL}/payment-success?transaction_id={vnp_TxnRef}')
        else:
            return redirect(f'{settings.FRONTEND_URL}/payment-failed?error={result["message"]}')


class VNPayIPNView(APIView):
    """
    Handle IPN from VNPay (Server-to-Server).
    Returns JSON response code to VNPay.
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

        # 2. Execute Payment Logic (Atomic & Locked)
        result = execute_payment_confirmation(vnp_TxnRef, vnpay_params)
        
        # 3. Map internal result to VNPay Response
        # RspCode: 00=Success, 01=Order Not Found, 02=Order Already Confirmed, 04=Invalid Amount, 99=Unknown
        return Response({
            'RspCode': result['code'],
            'Message': result['message']
        })