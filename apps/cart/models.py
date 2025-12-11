from django.db import models
from django.conf import settings
from djmoney.models.fields import MoneyField
import uuid


class Cart(models.Model):
    """Shopping cart for users."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
        null=True,
        blank=True
    )
    session_key = models.CharField(max_length=40, blank=True, null=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'carts'
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'
    
    def __str__(self):
        if self.user:
            return f"Cart - {self.user.email}"
        return f"Cart - Session {self.session_key}"
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())
    
    @property
    def subtotal(self):
        return sum(item.total_price for item in self.items.all())
    
    def clear(self):
        """Remove all items from cart."""
        self.items.all().delete()


class CartItem(models.Model):
    """Individual items in a shopping cart."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart_items'
    )
    
    quantity = models.PositiveIntegerField(default=1)
    
    # Store price at time of adding (prices may change)
    unit_price = MoneyField(max_digits=12, decimal_places=2, default_currency='VND')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_items'
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        unique_together = ['cart', 'product', 'variant']
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    @property
    def total_price(self):
        return self.unit_price.amount * self.quantity
    
    def save(self, *args, **kwargs):
        # Set unit price from product/variant if not set
        if not self.unit_price:
            if self.variant and self.variant.price:
                self.unit_price = self.variant.price
            else:
                self.unit_price = self.product.price
        super().save(*args, **kwargs)
