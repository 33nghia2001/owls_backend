from django.db import models
from django.conf import settings
import uuid


class Wishlist(models.Model):
    """User's wishlist for products."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlists'
    )
    name = models.CharField(max_length=100, default='My Wishlist')
    is_public = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wishlists'
        verbose_name = 'Wishlist'
        verbose_name_plural = 'Wishlists'
    
    def __str__(self):
        return f"{self.user.email} - {self.name}"


class WishlistItem(models.Model):
    """Items in a wishlist."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    
    added_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'wishlist_items'
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
        unique_together = ['wishlist', 'product']
    
    def __str__(self):
        return f"{self.wishlist.name} - {self.product.name}"
