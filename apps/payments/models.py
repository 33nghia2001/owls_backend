from django.db import models
from django.conf import settings
from apps.courses.models import Course
import uuid


class Payment(models.Model):
    """Payment Transactions"""
    
    PAYMENT_METHODS = (
        ('vnpay', 'VNPay'),
        ('momo', 'MoMo'),
        ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('free', 'Free'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    )
    
    # Unique identifier
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Relationships
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='payments')
    discount = models.ForeignKey(
        'Discount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        help_text='Discount code used for this payment'
    )
    
    # Payment Details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='VND')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Gateway specific data
    gateway_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    
    # Metadata
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['gateway_transaction_id']),
        ]
    
    def __str__(self):
        return f"{self.transaction_id} - {self.user.username} - {self.course.title}"
    
    def mark_as_completed(self):
        """Mark payment as completed"""
        from django.utils import timezone
        self.status = 'completed'
        self.paid_at = timezone.now()
        self.save()


class VNPayTransaction(models.Model):
    """VNPay specific transaction details"""
    
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='vnpay_transaction')
    
    # VNPay Request Parameters
    vnp_TxnRef = models.CharField(max_length=100, unique=True)  # Order ID
    vnp_OrderInfo = models.CharField(max_length=255)
    vnp_OrderType = models.CharField(max_length=50, default='billpayment')
    vnp_Amount = models.BigIntegerField()  # Amount in VND * 100
    
    # VNPay Response Parameters
    vnp_ResponseCode = models.CharField(max_length=10, blank=True, null=True)
    vnp_TransactionNo = models.CharField(max_length=100, blank=True, null=True)
    vnp_BankCode = models.CharField(max_length=50, blank=True, null=True)
    vnp_BankTranNo = models.CharField(max_length=100, blank=True, null=True)
    vnp_CardType = models.CharField(max_length=50, blank=True, null=True)
    vnp_PayDate = models.CharField(max_length=14, blank=True, null=True)
    
    # Security
    vnp_SecureHash = models.CharField(max_length=255, blank=True, null=True)
    
    # Raw data
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vnpay_transactions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"VNPay - {self.vnp_TxnRef}"


class Refund(models.Model):
    """Refund Requests"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    )
    
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True)
    
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='refund_requests')
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_refunds')
    
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'refunds'
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Refund - {self.payment.transaction_id} - {self.amount}"


class Discount(models.Model):
    """Discount Codes / Coupons"""
    
    DISCOUNT_TYPES = (
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    )
    
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Limits
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    current_uses = models.PositiveIntegerField(default=0)
    max_uses_per_user = models.PositiveIntegerField(default=1)
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Applicability
    courses = models.ManyToManyField(Course, blank=True, related_name='discounts')
    all_courses = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'discounts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.discount_value}"
    
    def is_valid(self):
        """Check if discount is valid"""
        from django.utils import timezone
        now = timezone.now()
        
        if not self.is_active:
            return False
        
        if now < self.valid_from or now > self.valid_until:
            return False
        
        if self.max_uses and self.current_uses >= self.max_uses:
            return False
        
        return True


class DiscountUsage(models.Model):
    """Track discount code usage"""
    
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='discount_usages')
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='discount_usage')
    
    amount_saved = models.DecimalField(max_digits=10, decimal_places=2)
    
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'discount_usages'
        ordering = ['-used_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.discount.code}"
