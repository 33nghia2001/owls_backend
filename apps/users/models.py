from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class UserManager(BaseUserManager):
    """Custom user manager for Users model."""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)


class Users(AbstractBaseUser, PermissionsMixin):
    """Custom User model for OWLS Marketplace."""
    
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        VENDOR = 'vendor', 'Vendor'
        ADMIN = 'admin', 'Admin'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=50, unique=True, blank=True, null=True)
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    phone = PhoneNumberField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    
    # Status fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(blank=True, null=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
    
    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Address(models.Model):
    """User shipping/billing addresses with Vietnam-specific fields."""
    
    class AddressType(models.TextChoices):
        SHIPPING = 'shipping', 'Shipping'
        BILLING = 'billing', 'Billing'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=20, choices=AddressType.choices, default=AddressType.SHIPPING)
    
    full_name = models.CharField(max_length=100)
    phone = PhoneNumberField()
    street_address = models.CharField(max_length=255)  # Số nhà, tên đường
    apartment = models.CharField(max_length=100, blank=True)  # Tòa nhà, căn hộ
    
    # Vietnam administrative divisions - aligned with GHN API
    province = models.CharField(max_length=100, verbose_name='Tỉnh/Thành phố')
    province_id = models.IntegerField(null=True, blank=True, verbose_name='GHN Province ID')
    district = models.CharField(max_length=100, verbose_name='Quận/Huyện')
    district_id = models.IntegerField(null=True, blank=True, verbose_name='GHN District ID')
    ward = models.CharField(max_length=100, verbose_name='Phường/Xã')
    ward_code = models.CharField(max_length=20, blank=True, verbose_name='GHN Ward Code')
    
    # Legacy fields - kept for backward compatibility, will be removed in future
    city = models.CharField(max_length=100, blank=True, editable=False)  # Deprecated, use province
    state = models.CharField(max_length=100, blank=True, editable=False)  # Deprecated, use district
    
    country = models.CharField(max_length=100, default='Vietnam')
    postal_code = models.CharField(max_length=20, blank=True)  # Optional in Vietnam
    
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'addresses'
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        return f"{self.full_name} - {self.street_address}, {self.ward}, {self.district}, {self.province}"
    
    @property
    def full_address(self):
        """Return formatted full address."""
        parts = [self.street_address]
        if self.apartment:
            parts.append(self.apartment)
        parts.extend([self.ward, self.district, self.province])
        return ', '.join(filter(None, parts))
    
    def save(self, *args, **kwargs):
        # Sync legacy fields for backward compatibility
        if self.province and not self.city:
            self.city = self.province
        if self.district and not self.state:
            self.state = self.district
            
        # Ensure only one default address per type per user
        if self.is_default:
            Address.objects.filter(
                user=self.user, 
                address_type=self.address_type, 
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
