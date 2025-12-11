from django.db import models
from django.conf import settings
import uuid


class Inventory(models.Model):
    """Inventory tracking for products and variants."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='inventory',
        null=True,
        blank=True
    )
    variant = models.OneToOneField(
        'products.ProductVariant',
        on_delete=models.CASCADE,
        related_name='inventory',
        null=True,
        blank=True
    )
    
    quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0)  # Reserved for pending orders
    
    # Stock alerts
    low_stock_threshold = models.PositiveIntegerField(default=10)
    
    # Location tracking
    warehouse_location = models.CharField(max_length=100, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'inventory'
        verbose_name = 'Inventory'
        verbose_name_plural = 'Inventories'
    
    def __str__(self):
        if self.product:
            return f"{self.product.name} - {self.quantity}"
        return f"{self.variant} - {self.quantity}"
    
    @property
    def available_quantity(self):
        """Get quantity available for sale."""
        return max(0, self.quantity - self.reserved_quantity)
    
    @property
    def is_in_stock(self):
        return self.available_quantity > 0
    
    @property
    def is_low_stock(self):
        return self.available_quantity <= self.low_stock_threshold


class InventoryMovement(models.Model):
    """Track all inventory changes."""
    
    class MovementType(models.TextChoices):
        IN = 'in', 'Stock In'
        OUT = 'out', 'Stock Out'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        RESERVED = 'reserved', 'Reserved'
        RELEASED = 'released', 'Released'
        RETURNED = 'returned', 'Returned'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name='movements'
    )
    
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity = models.IntegerField()  # Positive or negative
    
    # Reference to what caused this movement
    reference_type = models.CharField(max_length=50, blank=True)  # e.g., 'order', 'manual'
    reference_id = models.CharField(max_length=100, blank=True)
    
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'inventory_movements'
        verbose_name = 'Inventory Movement'
        verbose_name_plural = 'Inventory Movements'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.inventory} - {self.movement_type}: {self.quantity}"
    
    def save(self, *args, **kwargs):
        """
        Auto-update inventory quantity based on movement type.
        
        IMPORTANT: 'reserved' and 'released' movements do NOT affect total quantity.
        They only track intent - the actual quantity update is handled separately
        via reserved_quantity field in OrderViewSet to avoid double deduction.
        
        - in: Stock received → quantity increases
        - out: Stock shipped/sold → quantity decreases  
        - returned: Stock returned by customer → quantity increases
        - adjustment: Manual inventory correction → quantity set to specific value
        - reserved: Order placed, awaiting payment → NO quantity change (only reserved_quantity)
        - released: Order cancelled/expired → NO quantity change (only reserved_quantity)
        """
        if not self.pk:  # Only on create
            if self.movement_type in ['in', 'returned']:
                self.inventory.quantity += abs(self.quantity)
                self.inventory.save()
            elif self.movement_type == 'out':
                # Only deduct when actually shipping out (not when reserving)
                self.inventory.quantity -= abs(self.quantity)
                self.inventory.save()
            elif self.movement_type == 'adjustment':
                self.inventory.quantity = self.quantity
                self.inventory.save()
            # 'reserved' and 'released' do NOT modify quantity
            # They are handled via reserved_quantity in OrderViewSet
        
        super().save(*args, **kwargs)
