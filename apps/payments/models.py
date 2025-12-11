from django.db import models
from django.conf import settings
from djmoney.models.fields import MoneyField
import uuid


class Payment(models.Model):
    """Payment records for orders."""
    
    class Method(models.TextChoices):
        COD = 'cod', 'Cash on Delivery'
        STRIPE = 'stripe', 'Stripe'
        VNPAY = 'vnpay', 'VNPay'
        MOMO = 'momo', 'MoMo'
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payment'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payments'
    )
    
    method = models.CharField(max_length=20, choices=Method.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    amount = MoneyField(max_digits=12, decimal_places=2, default_currency='VND')
    
    # Payment gateway info
    transaction_id = models.CharField(max_length=255, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    
    # For refunds
    refund_amount = MoneyField(
        max_digits=12, decimal_places=2, default_currency='VND',
        blank=True, null=True
    )
    refund_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order.order_number} - {self.method} - {self.status}"


class PaymentLog(models.Model):
    """Log all payment gateway interactions."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='logs')
    
    action = models.CharField(max_length=50)  # e.g., 'create', 'callback', 'refund'
    request_data = models.JSONField(default=dict)
    response_data = models.JSONField(default=dict)
    
    is_success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'payment_logs'
        verbose_name = 'Payment Log'
        verbose_name_plural = 'Payment Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.payment} - {self.action}"
