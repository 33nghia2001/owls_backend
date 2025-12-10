from rest_framework import serializers
from django.contrib.auth import get_user_model
from turnstile.fields import TurnstileField
from .models import Payment, VNPayTransaction, Discount
from apps.courses.models import Course

User = get_user_model()


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer cho Payment"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    discount_code = serializers.CharField(source='discount.code', read_only=True)
    payment_url = serializers.SerializerMethodField()
    turnstile = TurnstileField()  # Cloudflare Turnstile CAPTCHA
    
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
        """Validate payment data"""
        request = self.context.get('request')
        course = data.get('course')
        discount = data.get('discount')
        
        if request and course:
            # Kiểm tra đã enroll chưa
            from apps.enrollments.models import Enrollment
            if Enrollment.objects.filter(student=request.user, course=course).exists():
                raise serializers.ValidationError({
                    'course': 'You are already enrolled in this course.'
                })
            
            # AUTO-CANCEL old pending payments (Fix UX issue)
            from django.utils import timezone
            from datetime import timedelta
            old_pending = Payment.objects.filter(
                user=request.user,
                course=course,
                status='pending',
                created_at__lt=timezone.now() - timedelta(minutes=15)
            )
            
            # Giảm used_count cho các discount bị expire (release reservation)
            for payment in old_pending:
                if payment.discount:
                    from django.db.models import F
                    Discount.objects.filter(id=payment.discount.id).update(
                        used_count=F('used_count') - 1
                    )
            
            old_pending.update(status='expired')
            
            # Kiểm tra còn pending payment mới (< 15 phút)
            recent_pending = Payment.objects.filter(
                user=request.user,
                course=course,
                status='pending',
                created_at__gte=timezone.now() - timedelta(minutes=15)
            ).exists()
            
            if recent_pending:
                raise serializers.ValidationError({
                    'course': 'You have a pending payment for this course. Please complete or cancel it first.'
                })
            
            # Validate discount nếu có
            if discount:
                if not discount.is_active:
                    raise serializers.ValidationError({'discount': 'This discount code is not active.'})
                
                # Kiểm tra usage limit với race condition protection
                if discount.usage_limit and discount.used_count >= discount.usage_limit:
                    raise serializers.ValidationError({'discount': 'This discount code has reached its usage limit.'})
                
                # Kiểm tra min purchase
                if discount.min_purchase_amount and course.price < discount.min_purchase_amount:
                    raise serializers.ValidationError({
                        'discount': f'Minimum purchase amount is {discount.min_purchase_amount} VND'
                    })
            
            # Validate amount khớp với course price (nếu không có discount)
            amount = data.get('amount')
            expected_amount = course.price
            
            # Nếu có discount, tính giá sau giảm
            if discount:
                if discount.discount_type == 'percentage':
                    discount_amount = course.price * (discount.discount_value / 100)
                    if discount.max_discount_amount:
                        discount_amount = min(discount_amount, discount.max_discount_amount)
                else:
                    discount_amount = discount.discount_value
                expected_amount = max(0, course.price - discount_amount)
            
            if float(amount) != float(expected_amount):
                raise serializers.ValidationError({
                    'amount': f'Amount must be {expected_amount} VND'
                })
        
        # Remove turnstile from validated_data (chỉ dùng để verify, không lưu vào DB)
        data.pop('turnstile', None)
        
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
            'id', 'code', 'discount_type', 'discount_value',
            'min_purchase_amount', 'max_discount_amount',
            'usage_limit', 'used_count', 'valid_from', 'valid_to',
            'is_active'
        ]
        read_only_fields = ['used_count']
    
    def validate_code(self, value):
        """Validate discount code unique"""
        if self.instance is None:  # Only on create
            if Discount.objects.filter(code=value).exists():
                raise serializers.ValidationError("This discount code already exists.")
        return value.upper()  # Store uppercase
    
    def validate(self, data):
        """Validate discount data"""
        valid_from = data.get('valid_from')
        valid_to = data.get('valid_to')
        
        if valid_from and valid_to and valid_from >= valid_to:
            raise serializers.ValidationError({
                'valid_to': 'Valid to date must be after valid from date.'
            })
        
        return data


class ApplyDiscountSerializer(serializers.Serializer):
    """Serializer để apply discount code"""
    code = serializers.CharField(max_length=50)
    course_id = serializers.IntegerField()
    
    def validate_code(self, value):
        """Validate discount code tồn tại và còn hiệu lực"""
        from django.utils import timezone
        
        try:
            discount = Discount.objects.get(code=value.upper(), is_active=True)
        except Discount.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired discount code.")
        
        # Check dates
        now = timezone.now()
        if discount.valid_from and discount.valid_from > now:
            raise serializers.ValidationError("This discount code is not yet valid.")
        
        if discount.valid_to and discount.valid_to < now:
            raise serializers.ValidationError("This discount code has expired.")
        
        # Check usage limit
        if discount.usage_limit and discount.used_count >= discount.usage_limit:
            raise serializers.ValidationError("This discount code has reached its usage limit.")
        
        return value.upper()
    
    def validate_course_id(self, value):
        """Validate course exists"""
        try:
            course = Course.objects.get(id=value, status='published')
        except Course.DoesNotExist:
            raise serializers.ValidationError("Course not found or not available.")
        return value
