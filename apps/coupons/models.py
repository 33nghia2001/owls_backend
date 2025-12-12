from django.db import models
from django.conf import settings
from django.utils import timezone
from djmoney.models.fields import MoneyField
import uuid


class Coupon(models.Model):
    """Discount coupons for orders."""
    
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage'
        FIXED = 'fixed', 'Fixed Amount'
        FREE_SHIPPING = 'free_shipping', 'Free Shipping'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Constraints
    min_order_amount = MoneyField(
        max_digits=12, decimal_places=2, default_currency='VND',
        blank=True, null=True
    )
    max_discount_amount = MoneyField(
        max_digits=12, decimal_places=2, default_currency='VND',
        blank=True, null=True
    )  # Cap for percentage discounts
    
    # Usage limits
    usage_limit = models.PositiveIntegerField(blank=True, null=True)  # Total uses
    usage_limit_per_user = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)
    
    # Validity
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Restrictions
    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='coupons'
    )  # Null = platform-wide coupon
    categories = models.ManyToManyField(
        'products.Category',
        blank=True,
        related_name='coupons'
    )
    products = models.ManyToManyField(
        'products.Product',
        blank=True,
        related_name='coupons'
    )
    
    # Only for specific users (VIP, first-time, etc.)
    eligible_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='eligible_coupons'
    )
    is_public = models.BooleanField(default=True)  # Show in coupon list
    
    # SECURITY: Require login for high-value coupons to prevent guest abuse
    requires_login = models.BooleanField(
        default=False, 
        help_text='If True, only authenticated users can use this coupon (prevents guest abuse)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'coupons'
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.discount_type}"
    
    def is_valid(self):
        """Check if coupon is currently valid."""
        now = timezone.now()
        
        if not self.is_active:
            return False
        if now < self.start_date or now > self.end_date:
            return False
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
        
        return True
    
    def calculate_discount(self, amount):
        """
        Calculate discount amount for given order amount.
        
        IMPORTANT: This is the SINGLE SOURCE OF TRUTH for discount calculation.
        Both CouponViewSet.validate and OrderViewSet.create use this method
        to ensure consistent calculations.
        
        Args:
            amount: Order subtotal (can be Decimal or MoneyField)
        
        Returns:
            Decimal: The discount amount, rounded to 2 decimal places
        """
        from decimal import Decimal, ROUND_HALF_UP
        
        # Ensure we're working with Decimal
        if hasattr(amount, 'amount'):
            # MoneyField
            amount = Decimal(str(amount.amount))
        else:
            amount = Decimal(str(amount))
        
        if self.discount_type == 'percentage':
            discount = amount * (Decimal(str(self.discount_value)) / Decimal('100'))
            if self.max_discount_amount:
                max_discount = Decimal(str(self.max_discount_amount.amount))
                discount = min(discount, max_discount)
        elif self.discount_type == 'fixed':
            discount = min(Decimal(str(self.discount_value)), amount)
        else:  # free_shipping
            discount = Decimal('0')  # Handled separately in shipping calculation
        
        # Round to 2 decimal places for currency consistency
        return discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class CouponUsage(models.Model):
    """Track coupon usage by users."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coupon_usages',
        null=True,
        blank=True
    )
    # SECURITY: Store normalized email to prevent alias abuse
    # Original email stored in order, this is for usage tracking
    guest_email = models.EmailField(blank=True, db_index=True)  # Normalized email for tracking
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        related_name='coupon_usages'
    )
    
    discount_applied = MoneyField(max_digits=12, decimal_places=2, default_currency='VND')
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'coupon_usages'
        verbose_name = 'Coupon Usage'
        verbose_name_plural = 'Coupon Usages'
    
    def save(self, *args, **kwargs):
        """Normalize guest_email before saving."""
        if self.guest_email:
            self.guest_email = self._normalize_email(self.guest_email)
        super().save(*args, **kwargs)
    
    @staticmethod
    def _normalize_email(email: str) -> str:
        """Normalize email to prevent alias abuse."""
        if not email:
            return email
        
        email = email.lower().strip()
        try:
            local_part, domain = email.rsplit('@', 1)
        except ValueError:
            return email
        
        # Remove +alias part
        local_part = local_part.split('+')[0]
        
        # For Gmail, also remove dots
        if domain in ['gmail.com', 'googlemail.com']:
            local_part = local_part.replace('.', '')
        
        return f'{local_part}@{domain}'
