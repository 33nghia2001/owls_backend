from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.db.models import F
from turnstile.fields import TurnstileField # Yêu cầu cài đặt thư viện django-turnstile

from .models import Payment, VNPayTransaction, Discount
from apps.courses.models import Course
from apps.enrollments.models import Enrollment

User = get_user_model()


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer cho Payment với tính năng chống spam và validate chặt chẽ"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    discount_code = serializers.CharField(source='discount.code', read_only=True)
    payment_url = serializers.SerializerMethodField()
    
    # Chống bot spam tạo đơn hàng ảo
    turnstile = TurnstileField(write_only=True) 
    
    class Meta:
        model = Payment
        fields = [
            'id', 'transaction_id', 'user', 'user_name', 'course', 'course_title',
            'amount', 'currency', 'payment_method', 'status', 'discount', 'discount_code',
            'gateway_transaction_id', 'description', 'payment_url', 'turnstile',
            'created_at', 'paid_at'
        ]
        read_only_fields = [
            'transaction_id', 'user', 'status', 'gateway_transaction_id',
            'created_at', 'paid_at'
        ]
    
    def get_payment_url(self, obj):
        """Trả về payment URL nếu có"""
        return obj.gateway_response.get('payment_url', None)
    
    def validate_course(self, value):
        """Validate course tồn tại và đang active"""
        if value.status != 'published':
            raise serializers.ValidationError("This course is not available for enrollment.")
        return value
    
    def validate(self, data):
        """Validate toàn bộ logic thanh toán"""
        request = self.context.get('request')
        course = data.get('course')
        discount = data.get('discount')
        
        # 1. Loại bỏ trường turnstile sau khi đã validate xong (không lưu vào model)
        data.pop('turnstile', None)
        
        if request and course:
            user = request.user
            
            # --- KIỂM TRA ENROLLMENT ---
            if Enrollment.objects.filter(student=user, course=course).exists():
                raise serializers.ValidationError({
                    'course': 'You are already enrolled in this course.'
                })
            
            # --- XỬ LÝ PENDING PAYMENT CŨ ---
            # Tìm các payment pending quá hạn (10 phút) -> Hủy & Trả lại discount slot
            # REDUCED FROM 15min to prevent Ghost Payment DOS attack
            cutoff_time = timezone.now() - timedelta(minutes=10)
            old_pending_payments = Payment.objects.filter(
                user=user,
                course=course,
                status='pending',
                created_at__lt=cutoff_time
            )
            
            # Hoàn trả lượt dùng mã giảm giá nếu có
            for p in old_pending_payments:
                if p.discount:
                    Discount.objects.filter(id=p.discount.id).update(
                        used_count=F('used_count') - 1
                    )
            
            # Đánh dấu hết hạn hàng loạt
            old_pending_payments.update(status='expired')
            
            # CHỐNG GHOST PAYMENT DOS: Giới hạn số lượng pending payments
            # Không cho phép user có quá 2 đơn pending cùng lúc (bất kể course nào)
            user_pending_count = Payment.objects.filter(
                user=user,
                status='pending'
            ).count()
            
            if user_pending_count >= 2:
                raise serializers.ValidationError({
                    'non_field_errors': 'You have too many pending payments. Please complete or wait for them to expire first.'
                })
            
            # Kiểm tra xem có payment nào mới tạo gần đây cho course này không (tránh spam liên tục)
            recent_pending = Payment.objects.filter(
                user=user,
                course=course,
                status='pending',
                created_at__gte=cutoff_time
            ).exists()
            
            if recent_pending:
                raise serializers.ValidationError({
                    'course': 'You have a pending payment for this course created recently. Please complete or cancel it first.'
                })
            
            # --- VALIDATE DISCOUNT ---
            expected_amount = course.price
            
            if discount:
                if not discount.is_active:
                    raise serializers.ValidationError({'discount': 'This discount code is not active.'})
                
                # Kiểm tra hạn sử dụng
                now = timezone.now()
                if discount.valid_from and discount.valid_from > now:
                     raise serializers.ValidationError({'discount': 'This discount code is not yet valid.'})
                if discount.valid_until and discount.valid_until < now:
                     raise serializers.ValidationError({'discount': 'This discount code has expired.'})

                # Kiểm tra số lượng (Usage Limit)
                if discount.max_uses and discount.current_uses >= discount.max_uses:
                    raise serializers.ValidationError({'discount': 'This discount code has reached its usage limit.'})
                
                # Kiểm tra giá trị đơn hàng tối thiểu
                if discount.min_purchase_amount and course.price < discount.min_purchase_amount:
                    raise serializers.ValidationError({
                        'discount': f'Minimum purchase amount is {discount.min_purchase_amount} VND'
                    })
                
                # Tính toán giá sau giảm
                if discount.discount_type == 'percentage':
                    discount_val = course.price * (discount.discount_value / 100)
                    # Không có max_discount_amount trong model Discount gốc, nếu cần thì thêm vào
                    # discount_val = min(discount_val, discount.max_discount_amount) 
                else:
                    discount_val = discount.discount_value
                
                expected_amount = max(0, course.price - discount_val)
            
            # --- VALIDATE FINAL AMOUNT ---
            # SECURITY FIX: Use Decimal for precise currency comparison
            # Never use float for financial calculations due to floating-point precision errors
            from decimal import Decimal
            client_amount = Decimal(str(data.get('amount')))
            expected_amount_decimal = Decimal(str(expected_amount))
            
            if client_amount != expected_amount_decimal:
                raise serializers.ValidationError({
                    'amount': f'Amount mismatch. Expected: {expected_amount} VND'
                })
        
        return data


class VNPayTransactionSerializer(serializers.ModelSerializer):
    """Serializer cho VNPay transaction"""
    class Meta:
        model = VNPayTransaction
        fields = '__all__'
        read_only_fields = ['payment']


class DiscountSerializer(serializers.ModelSerializer):
    """Serializer cho Discount codes"""
    class Meta:
        model = Discount
        fields = [
            'id', 'code', 'description', 'discount_type', 'discount_value',
            'min_purchase_amount', 'max_uses', 'current_uses', 
            'max_uses_per_user', 'all_courses', 'courses',
            'is_active', 'valid_from', 'valid_until', 
            'created_at'
        ]
        read_only_fields = ['current_uses', 'created_at']
    
    def validate_code(self, value):
        """Đảm bảo mã giảm giá là duy nhất và lưu dưới dạng in hoa"""
        if self.instance is None:  # Chỉ check khi tạo mới
            if Discount.objects.filter(code=value.upper()).exists():
                raise serializers.ValidationError("This discount code already exists.")
        return value.upper()
    
    def validate(self, data):
        """Kiểm tra logic ngày tháng"""
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        
        if valid_from and valid_until and valid_from >= valid_until:
            raise serializers.ValidationError({
                'valid_until': 'Expiration date must be after start date.'
            })
        return data


class ApplyDiscountSerializer(serializers.Serializer):
    """Serializer để apply discount code (API check giá)"""
    code = serializers.CharField(max_length=50)
    course_id = serializers.IntegerField()
    
    def validate(self, data):
        code = data.get('code').upper()
        course_id = data.get('course_id')
        
        # 1. Tìm Course
        try:
            course = Course.objects.get(id=course_id, status='published')
        except Course.DoesNotExist:
            raise serializers.ValidationError("Course not found or not available.")
            
        # 2. Tìm Discount
        try:
            discount = Discount.objects.get(code=code, is_active=True)
        except Discount.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired discount code.")
        
        # 3. Validate Discount Rules
        now = timezone.now()
        if discount.valid_from and discount.valid_from > now:
            raise serializers.ValidationError("This discount code is not yet valid.")
        
        if discount.valid_until and discount.valid_until < now:
            raise serializers.ValidationError("This discount code has expired.")
        
        if discount.max_uses and discount.current_uses >= discount.max_uses:
            raise serializers.ValidationError("This discount code has reached its usage limit.")
            
        # Validate áp dụng cho khóa học cụ thể
        if not discount.all_courses and not discount.courses.filter(id=course.id).exists():
             raise serializers.ValidationError("This discount code is not applicable to this course.")

        # Trả về data đã validate để View xử lý tiếp
        return data