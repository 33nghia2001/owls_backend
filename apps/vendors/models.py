from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.db import IntegrityError
from phonenumber_field.modelfields import PhoneNumberField
import uuid
import secrets


def generate_unique_slug(base_slug, model_class, existing_instance=None):
    """
    Generate a unique slug with retry logic to handle race conditions.
    Similar to order number generation pattern.
    
    Args:
        base_slug: The initial slug to try
        model_class: The Django model class to check uniqueness against
        existing_instance: If updating, exclude this instance from uniqueness check
    
    Returns:
        A unique slug string
    """
    slug = base_slug
    max_retries = 10
    
    for attempt in range(max_retries):
        # Build queryset to check for duplicates
        qs = model_class.objects.filter(slug=slug)
        if existing_instance and existing_instance.pk:
            qs = qs.exclude(pk=existing_instance.pk)
        
        if not qs.exists():
            return slug
        
        # Collision found, add random suffix
        suffix = secrets.token_hex(3)  # 6 hex chars
        slug = f"{base_slug}-{suffix}"
    
    # Last resort: use UUID
    return f"{base_slug}-{uuid.uuid4().hex[:8]}"


class Vendor(models.Model):
    """Vendor/Shop model for marketplace sellers."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        SUSPENDED = 'suspended', 'Suspended'
        REJECTED = 'rejected', 'Rejected'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # Prevent deletion of user with vendor profile
        related_name='vendor_profile'
    )
    
    # Shop Information
    shop_name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='vendors/logos/', blank=True, null=True)
    banner = models.ImageField(upload_to='vendors/banners/', blank=True, null=True)
    
    # Contact Information
    business_email = models.EmailField()
    business_phone = PhoneNumberField()
    
    # Business Details
    business_name = models.CharField(max_length=200, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    business_license = models.FileField(upload_to='vendors/licenses/', blank=True, null=True)
    
    # Address
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='Vietnam')
    postal_code = models.CharField(max_length=20)
    
    # Status & Metrics
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_featured = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_sales = models.PositiveIntegerField(default=0)
    total_products = models.PositiveIntegerField(default=0)
    
    # Commission rate (percentage)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'vendors'
        verbose_name = 'Vendor'
        verbose_name_plural = 'Vendors'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.shop_name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.shop_name)
            self.slug = generate_unique_slug(base_slug, Vendor, self)
        
        # Retry loop to handle race conditions
        max_retries = 5
        for attempt in range(max_retries):
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                if 'slug' in str(e).lower() and attempt < max_retries - 1:
                    # Slug collision during concurrent request, regenerate
                    base_slug = slugify(self.shop_name)
                    self.slug = generate_unique_slug(base_slug, Vendor, self)
                else:
                    raise


class VendorBankAccount(models.Model):
    """Bank account information for vendor payouts."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='bank_accounts')
    
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    branch_name = models.CharField(max_length=100, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'vendor_bank_accounts'
        verbose_name = 'Vendor Bank Account'
        verbose_name_plural = 'Vendor Bank Accounts'
    
    def __str__(self):
        return f"{self.vendor.shop_name} - {self.bank_name}"
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            VendorBankAccount.objects.filter(
                vendor=self.vendor, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class VendorPayout(models.Model):
    """Payout records for vendors."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='payouts')
    bank_account = models.ForeignKey(VendorBankAccount, on_delete=models.SET_NULL, null=True)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reference_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'vendor_payouts'
        verbose_name = 'Vendor Payout'
        verbose_name_plural = 'Vendor Payouts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.vendor.shop_name} - {self.amount}"


class VendorBalance(models.Model):
    """
    Track vendor balance with hold period for refund protection.
    
    Balance from order is held for HOLD_DAYS before becoming available for payout.
    This protects against refund requests after vendor has already been paid.
    """
    
    class Status(models.TextChoices):
        HELD = 'held', 'Held (Pending Release)'
        AVAILABLE = 'available', 'Available for Payout'
        PAID_OUT = 'paid_out', 'Paid Out'
        REFUNDED = 'refunded', 'Refunded to Customer'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='balance_entries')
    order_item = models.OneToOneField(
        'orders.OrderItem',
        on_delete=models.CASCADE,
        related_name='vendor_balance'
    )
    
    # Amount after platform commission
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.HELD)
    
    # Hold period - balance becomes available after this date
    created_at = models.DateTimeField(auto_now_add=True)
    available_at = models.DateTimeField(help_text='Date when balance becomes available for payout')
    released_at = models.DateTimeField(null=True, blank=True)
    
    # Link to payout if paid
    payout = models.ForeignKey(
        VendorPayout, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='balance_entries'
    )
    
    class Meta:
        db_table = 'vendor_balances'
        verbose_name = 'Vendor Balance'
        verbose_name_plural = 'Vendor Balances'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.vendor.shop_name} - {self.net_amount} ({self.status})"
    
    @classmethod
    def create_from_order_item(cls, order_item, hold_days=7):
        """
        Create a held balance entry from a delivered order item.
        
        Args:
            order_item: The OrderItem that was delivered
            hold_days: Number of days to hold balance before release (default: 7)
        """
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal
        
        # Use total_price (not subtotal - OrderItem doesn't have subtotal field)
        gross_amount = order_item.total_price.amount
        commission_rate = order_item.commission_rate or order_item.vendor.commission_rate
        commission_amount = gross_amount * (Decimal(str(commission_rate)) / Decimal('100'))
        net_amount = gross_amount - commission_amount
        
        return cls.objects.create(
            vendor=order_item.vendor,
            order_item=order_item,
            gross_amount=gross_amount,
            commission_amount=commission_amount,
            net_amount=net_amount,
            status=cls.Status.HELD,
            available_at=timezone.now() + timedelta(days=hold_days)
        )
