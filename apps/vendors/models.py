from django.db import models
from django.conf import settings
from django.utils.text import slugify
from phonenumber_field.modelfields import PhoneNumberField
import uuid


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
        on_delete=models.CASCADE,
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
            self.slug = slugify(self.shop_name)
        super().save(*args, **kwargs)


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
