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
        """Calculate discount amount for given order amount."""
        if self.discount_type == 'percentage':
            discount = amount * (self.discount_value / 100)
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount.amount)
        elif self.discount_type == 'fixed':
            discount = min(self.discount_value, amount)
        else:  # free_shipping
            discount = 0  # Handled separately
        
        return discount


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
    guest_email = models.EmailField(blank=True, db_index=True)  # For guest checkout tracking
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
