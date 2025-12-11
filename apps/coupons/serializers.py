from rest_framework import serializers
from .models import Coupon, CouponUsage


class CouponSerializer(serializers.ModelSerializer):
    """Serializer for coupons."""
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'description', 'discount_type', 'discount_value',
            'min_order_amount', 'max_discount_amount', 'start_date', 'end_date',
            'is_valid', 'is_public'
        ]
    
    def get_is_valid(self, obj):
        return obj.is_valid()


class ApplyCouponSerializer(serializers.Serializer):
    """Serializer for applying coupon."""
    code = serializers.CharField(max_length=50)
    order_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)


class CouponUsageSerializer(serializers.ModelSerializer):
    """Serializer for coupon usage."""
    coupon_code = serializers.CharField(source='coupon.code', read_only=True)
    
    class Meta:
        model = CouponUsage
        fields = ['id', 'coupon_code', 'discount_applied', 'used_at']
