from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import ScopedRateThrottle
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re

from .models import Coupon, CouponUsage
from .serializers import CouponSerializer, ApplyCouponSerializer


def normalize_email(email: str) -> str:
    """
    Normalize email to prevent abuse via aliases.
    - Lowercase the entire email
    - For Gmail: remove dots and +alias parts from local part
    - For other providers: just remove +alias parts
    
    Examples:
    - user.name+alias@gmail.com -> username@gmail.com
    - user+test@example.com -> user@example.com
    """
    if not email:
        return email
    
    email = email.lower().strip()
    
    try:
        local_part, domain = email.rsplit('@', 1)
    except ValueError:
        return email
    
    # Remove +alias part for all providers
    local_part = local_part.split('+')[0]
    
    # For Gmail (and Google-hosted domains), also remove dots
    gmail_domains = ['gmail.com', 'googlemail.com']
    if domain in gmail_domains:
        local_part = local_part.replace('.', '')
    
    return f'{local_part}@{domain}'


class SensitiveRateThrottle(ScopedRateThrottle):
    """Custom throttle for sensitive operations like coupon validation."""
    scope = 'sensitive'


class CouponViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for coupons."""
    serializer_class = CouponSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Coupon.objects.filter(is_active=True, is_public=True)
    
    @action(detail=False, methods=['post'], throttle_classes=[SensitiveRateThrottle])
    def validate(self, request):
        """Validate a coupon code."""
        serializer = ApplyCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data['code']
        order_amount = serializer.validated_data.get('order_amount', 0)
        guest_email = serializer.validated_data.get('email', '')
        
        try:
            coupon = Coupon.objects.get(code__iexact=code)
        except Coupon.DoesNotExist:
            return Response(
                {'valid': False, 'error': 'Coupon not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not coupon.is_valid():
            return Response(
                {'valid': False, 'error': 'Coupon is expired or inactive.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # SECURITY: Check if coupon requires login (for high-value coupons)
        if coupon.requires_login and not request.user.is_authenticated:
            return Response({
                'valid': False,
                'error': 'Mã giảm giá này yêu cầu đăng nhập để sử dụng.'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check minimum order amount
        if coupon.min_order_amount and order_amount < coupon.min_order_amount.amount:
            return Response({
                'valid': False,
                'error': f'Minimum order amount is {coupon.min_order_amount}.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check user usage limit
        if request.user.is_authenticated:
            user_usage = CouponUsage.objects.filter(
                coupon=coupon, user=request.user
            ).count()
            if user_usage >= coupon.usage_limit_per_user:
                return Response({
                    'valid': False,
                    'error': 'You have already used this coupon.'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Guest user - require and validate email for tracking
            if not guest_email:
                return Response({
                    'valid': False,
                    'error': 'Email is required for guest checkout.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                validate_email(guest_email)
            except ValidationError:
                return Response({
                    'valid': False,
                    'error': 'Invalid email address.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # SECURITY: Normalize email to prevent alias abuse (user+1@gmail.com, u.ser@gmail.com)
            normalized_email = normalize_email(guest_email)
            
            # Check guest email usage with normalized email
            guest_usage = CouponUsage.objects.filter(
                coupon=coupon, guest_email__iexact=normalized_email
            ).count()
            if guest_usage >= coupon.usage_limit_per_user:
                return Response({
                    'valid': False,
                    'error': 'This email has already used this coupon.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        discount = coupon.calculate_discount(order_amount) if order_amount else 0
        
        return Response({
            'valid': True,
            'coupon': CouponSerializer(coupon).data,
            'discount_amount': discount
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_coupons(self, request):
        """Get coupons available for current user."""
        public_coupons = Coupon.objects.filter(is_active=True, is_public=True)
        eligible_coupons = request.user.eligible_coupons.filter(is_active=True)
        
        all_coupons = (public_coupons | eligible_coupons).distinct()
        valid_coupons = [c for c in all_coupons if c.is_valid()]
        
        serializer = CouponSerializer(valid_coupons, many=True)
        return Response(serializer.data)
