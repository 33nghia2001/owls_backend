from django.db import models
from django.conf import settings
from djmoney.models.fields import MoneyField
import uuid


class ProductView(models.Model):
    """Track product views."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='view_analytics'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    session_key = models.CharField(max_length=40, blank=True)
    
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True)
    
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_views'
        verbose_name = 'Product View'
        verbose_name_plural = 'Product Views'
        ordering = ['-viewed_at']


class SearchQuery(models.Model):
    """Track search queries."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.CharField(max_length=255, db_index=True)
    results_count = models.PositiveIntegerField(default=0)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    session_key = models.CharField(max_length=40, blank=True)
    
    searched_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'search_queries'
        verbose_name = 'Search Query'
        verbose_name_plural = 'Search Queries'
        ordering = ['-searched_at']


class VendorStats(models.Model):
    """Daily vendor statistics snapshot."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        related_name='daily_stats'
    )
    date = models.DateField(db_index=True)
    
    # Orders
    orders_count = models.PositiveIntegerField(default=0)
    orders_revenue = MoneyField(max_digits=12, decimal_places=2, default_currency='VND', default=0)
    
    # Products
    products_sold = models.PositiveIntegerField(default=0)
    product_views = models.PositiveIntegerField(default=0)
    
    # Engagement
    new_reviews = models.PositiveIntegerField(default=0)
    messages_received = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'vendor_stats'
        verbose_name = 'Vendor Stats'
        verbose_name_plural = 'Vendor Stats'
        unique_together = ['vendor', 'date']
        ordering = ['-date']


class PlatformStats(models.Model):
    """Daily platform-wide statistics."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True, db_index=True)
    
    # Users
    new_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    
    # Vendors
    new_vendors = models.PositiveIntegerField(default=0)
    active_vendors = models.PositiveIntegerField(default=0)
    
    # Orders
    orders_count = models.PositiveIntegerField(default=0)
    orders_revenue = MoneyField(max_digits=14, decimal_places=2, default_currency='VND', default=0)
    
    # Products
    new_products = models.PositiveIntegerField(default=0)
    product_views = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'platform_stats'
        verbose_name = 'Platform Stats'
        verbose_name_plural = 'Platform Stats'
        ordering = ['-date']
