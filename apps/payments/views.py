from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import redirect
from django.utils import timezone
from django.db import transaction
from .models import Payment, VNPayTransaction, Discount
from .serializers import (
    PaymentSerializer,
    VNPayTransactionSerializer,
    DiscountSerializer,
    ApplyDiscountSerializer
)
from .vnpay import create_vnpay_payment_url, VNPay, get_vnpay_response_message
from django.conf import settings


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet cho Payments.
    - List/Retrieve: Chỉ xem payment của chính mình (hoặc admin xem tất cả)
    - Create: Tạo payment mới và nhận VNPay URL
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """User chỉ xem payment của mình, admin xem tất cả"""
        if self.request.user.role == 'admin':
            return Payment.objects.all().select_related('user', 'course')
        return Payment.objects.filter(user=self.request.user).select_related('course')
    
    def perform_create(self, serializer):
        """Tạo payment và generate VNPay URL"""
        # Lưu payment với status pending
        payment = serializer.save(
            user=self.request.user,
            status='pending',
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Nếu là VNPay, tạo payment URL
        if payment.payment_method == 'vnpay':
            payment_url = create_vnpay_payment_url(payment, self.request)
            payment.gateway_response = {'payment_url': payment_url}
            payment.save(update_fields=['gateway_response'])
    
    def get_client_ip(self):
        """Lấy IP của client"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Hủy payment (chỉ cancel được khi đang pending)"""
        payment = self.get_object()
        
        if payment.user != request.user and request.user.role != 'admin':
            return Response(
                {'error': 'You can only cancel your own payments.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if payment.status != 'pending':
            return Response(
                {'error': f'Cannot cancel payment with status: {payment.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment.status = 'cancelled'
        payment.save(update_fields=['status'])
        
        return Response({
            'status': 'success',
            'message': 'Payment cancelled successfully.'
        })
    
    @action(detail=False, methods=['post'])
    def apply_discount(self, request):
        """Apply discount code và tính giá sau giảm"""
        serializer = ApplyDiscountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data['code']
        course_id = serializer.validated_data['course_id']
        
        # Get discount and course
        discount = Discount.objects.get(code=code)
        from apps.courses.models import Course
        course = Course.objects.get(id=course_id)
        
        # Check min purchase amount
        if discount.min_purchase_amount and course.price < discount.min_purchase_amount:
            return Response({
                'error': f'Minimum purchase amount is {discount.min_purchase_amount} VND'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate discount
        if discount.discount_type == 'percentage':
            discount_amount = course.price * (discount.discount_value / 100)
            if discount.max_discount_amount:
                discount_amount = min(discount_amount, discount.max_discount_amount)
        else:  # fixed
            discount_amount = discount.discount_value
        
        final_price = max(0, course.price - discount_amount)
        
        return Response({
            'original_price': course.price,
            'discount_amount': discount_amount,
            'final_price': final_price,
            'discount_code': code
        })


class VNPayReturnView(APIView):
    """
    VNPay Return URL - User được redirect về đây sau khi thanh toán
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Xử lý response từ VNPay"""
        # Lấy toàn bộ query params
        vnpay_params = request.GET.dict()
        
        if not vnpay_params:
            return redirect(f'{settings.FRONTEND_URL}/payment-error?error=no_params')
        
        # Validate signature
        vnpay = VNPay()
        vnpay.response_data = vnpay_params.copy()
        
        is_valid = vnpay.validate_response(settings.VNPAY_HASH_SECRET)
        
        if not is_valid:
            return redirect(f'{settings.FRONTEND_URL}/payment-error?error=invalid_signature')
        
        # Get transaction
        vnp_TxnRef = vnpay_params.get('vnp_TxnRef')
        vnp_ResponseCode = vnpay_params.get('vnp_ResponseCode')
        vnp_Amount = int(vnpay_params.get('vnp_Amount', 0)) / 100  # VNPay trả về amount * 100
        
        try:
            # Find payment by transaction_id
            payment = Payment.objects.get(transaction_id=vnp_TxnRef)
            
            # 1. CRITICAL: Validate số tiền
            if float(payment.amount) != float(vnp_Amount):
                payment.status = 'failed'
                payment.save()
                return redirect(f'{settings.FRONTEND_URL}/payment-error?error=amount_mismatch')
            
            vnpay_transaction = payment.vnpay_transaction
            
            # Update VNPay transaction
            vnpay_transaction.vnp_ResponseCode = vnp_ResponseCode
            vnpay_transaction.vnp_TransactionNo = vnpay_params.get('vnp_TransactionNo')
            vnpay_transaction.vnp_BankCode = vnpay_params.get('vnp_BankCode')
            vnpay_transaction.vnp_BankTranNo = vnpay_params.get('vnp_BankTranNo')
            vnpay_transaction.vnp_CardType = vnpay_params.get('vnp_CardType')
            vnpay_transaction.vnp_PayDate = vnpay_params.get('vnp_PayDate')
            vnpay_transaction.response_data = vnpay_params
            vnpay_transaction.save()
            
            # Update payment status
            if vnp_ResponseCode == '00':
                with transaction.atomic():
                    payment.status = 'completed'
                    payment.paid_at = timezone.now()
                    payment.gateway_transaction_id = vnpay_params.get('vnp_TransactionNo')
                    payment.save()
                    
                    # Tạo Enrollment tự động
                    from apps.enrollments.models import Enrollment
                    Enrollment.objects.get_or_create(
                        student=payment.user,
                        course=payment.course,
                        defaults={
                            'status': 'active',
                            'payment': payment
                        }
                    )
                
                return redirect(f'{settings.FRONTEND_URL}/payment-success?transaction_id={vnp_TxnRef}')
            else:
                payment.status = 'failed'
                payment.save()
                error_msg = get_vnpay_response_message(vnp_ResponseCode)
                return redirect(f'{settings.FRONTEND_URL}/payment-failed?error={error_msg}')
                
        except Payment.DoesNotExist:
            return redirect(f'{settings.FRONTEND_URL}/payment-error?error=payment_not_found')


class VNPayIPNView(APIView):
    """
    VNPay IPN (Instant Payment Notification) - Callback từ VNPay server
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Xử lý IPN từ VNPay"""
        vnpay_params = request.GET.dict()
        
        # Validate signature
        vnpay = VNPay()
        vnpay.response_data = vnpay_params.copy()
        
        if not vnpay.validate_response(settings.VNPAY_HASH_SECRET):
            return Response({'RspCode': '97', 'Message': 'Invalid Signature'})
        
        vnp_TxnRef = vnpay_params.get('vnp_TxnRef')
        vnp_ResponseCode = vnpay_params.get('vnp_ResponseCode')
        vnp_Amount = int(vnpay_params.get('vnp_Amount', 0)) / 100  # VNPay trả về amount * 100
        
        try:
            payment = Payment.objects.get(transaction_id=vnp_TxnRef)
            
            # 1. CRITICAL: Validate số tiền
            if float(payment.amount) != float(vnp_Amount):
                return Response({'RspCode': '04', 'Message': 'Invalid Amount'})
            
            # 2. Idempotency: Chỉ xử lý nếu payment đang pending
            if payment.status != 'pending':
                # Nếu đã completed hoặc failed rồi thì trả về success luôn
                return Response({'RspCode': '02', 'Message': 'Order already confirmed'})
            
            # 3. Xử lý payment
            # 3. Xử lý payment
            if vnp_ResponseCode == '00':
                with transaction.atomic():
                    payment.status = 'completed'
                    payment.paid_at = timezone.now()
                    payment.gateway_transaction_id = vnpay_params.get('vnp_TransactionNo')
                    payment.save()
                    
                    # Tạo Enrollment
                    from apps.enrollments.models import Enrollment
                    Enrollment.objects.get_or_create(
                        student=payment.user,
                        course=payment.course,
                        defaults={
                            'status': 'active',
                            'payment': payment
                        }
                    )
            else:
                payment.status = 'failed'
                payment.save()
            
            return Response({'RspCode': '00', 'Message': 'Confirm Success'})
            
        except Payment.DoesNotExist:
            return Response({'RspCode': '01', 'Message': 'Order not found'})


class DiscountViewSet(viewsets.ModelViewSet):
    """
    ViewSet cho Discount codes.
    - Admin: Full CRUD
    - User: Chỉ xem active discounts
    """
    serializer_class = DiscountSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """User chỉ xem active discounts, admin xem tất cả"""
        if self.request.user.is_authenticated and self.request.user.role == 'admin':
            return Discount.objects.all()
        return Discount.objects.filter(is_active=True)
    
    def get_permissions(self):
        """Chỉ admin mới create/update/delete"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsAdminUser()]
        return super().get_permissions()


class IsAdminUser(permissions.BasePermission):
    """Permission: Chỉ admin"""
    def has_permission(self, request, view):
        return request.user and request.user.role == 'admin'

