from django.db import models
from djmoney.models.fields import MoneyField
import uuid


class ShippingMethod(models.Model):
    """Available shipping methods."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    # Base pricing
    base_cost = MoneyField(max_digits=10, decimal_places=2, default_currency='VND')
    cost_per_kg = MoneyField(max_digits=10, decimal_places=2, default_currency='VND', default=0)
    
    # Delivery time
    min_days = models.PositiveSmallIntegerField(default=1)
    max_days = models.PositiveSmallIntegerField(default=3)
    
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shipping_methods'
        verbose_name = 'Shipping Method'
        verbose_name_plural = 'Shipping Methods'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def calculate_cost(self, weight_kg=0):
        """Calculate shipping cost based on weight."""
        return self.base_cost.amount + (self.cost_per_kg.amount * weight_kg)


class ShippingZone(models.Model):
    """Shipping zones for regional pricing."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    countries = models.JSONField(default=list)  # List of country codes
    regions = models.JSONField(default=list)  # List of state/region names
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'shipping_zones'
        verbose_name = 'Shipping Zone'
        verbose_name_plural = 'Shipping Zones'
    
    def __str__(self):
        return self.name


class ShippingRate(models.Model):
    """Shipping rates for zone + method combinations."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(ShippingZone, on_delete=models.CASCADE, related_name='rates')
    method = models.ForeignKey(ShippingMethod, on_delete=models.CASCADE, related_name='zone_rates')
    
    cost = MoneyField(max_digits=10, decimal_places=2, default_currency='VND')
    min_order_amount = MoneyField(
        max_digits=12, decimal_places=2, default_currency='VND',
        blank=True, null=True
    )  # Free shipping above this amount
    
    class Meta:
        db_table = 'shipping_rates'
        verbose_name = 'Shipping Rate'
        verbose_name_plural = 'Shipping Rates'
        unique_together = ['zone', 'method']
    
    def __str__(self):
        return f"{self.zone.name} - {self.method.name}: {self.cost}"


class Shipment(models.Model):
    """Shipment tracking for orders."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PICKED_UP = 'picked_up', 'Picked Up'
        IN_TRANSIT = 'in_transit', 'In Transit'
        OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for Delivery'
        DELIVERED = 'delivered', 'Delivered'
        FAILED = 'failed', 'Delivery Failed'
        RETURNED = 'returned', 'Returned'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='shipments'
    )
    method = models.ForeignKey(ShippingMethod, on_delete=models.SET_NULL, null=True)
    
    tracking_number = models.CharField(max_length=100, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Weight & dimensions
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'shipments'
        verbose_name = 'Shipment'
        verbose_name_plural = 'Shipments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order.order_number} - {self.tracking_number or 'No tracking'}"


class ShipmentTracking(models.Model):
    """Tracking history for shipments."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_history')
    
    status = models.CharField(max_length=50)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shipment_tracking'
        verbose_name = 'Shipment Tracking'
        verbose_name_plural = 'Shipment Trackings'
        ordering = ['-timestamp']
