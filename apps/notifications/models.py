from django.db import models
from django.conf import settings
import uuid


class Notification(models.Model):
    """User notifications."""
    
    class NotificationType(models.TextChoices):
        ORDER = 'order', 'Order'
        PAYMENT = 'payment', 'Payment'
        SHIPPING = 'shipping', 'Shipping'
        REVIEW = 'review', 'Review'
        PROMOTION = 'promotion', 'Promotion'
        SYSTEM = 'system', 'System'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Link to related object
    link = models.CharField(max_length=500, blank=True)
    data = models.JSONField(default=dict, blank=True)
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"


class NotificationPreference(models.Model):
    """User notification preferences."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Email notifications
    email_orders = models.BooleanField(default=True)
    email_promotions = models.BooleanField(default=True)
    email_reviews = models.BooleanField(default=True)
    email_newsletter = models.BooleanField(default=True)
    
    # Push notifications
    push_orders = models.BooleanField(default=True)
    push_promotions = models.BooleanField(default=True)
    push_reviews = models.BooleanField(default=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
