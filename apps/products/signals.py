"""
Django signals for products app.

Handles automatic updates like search vector generation.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.postgres.search import SearchVector
from django.db import transaction


@receiver(post_save, sender='products.Product')
def update_product_search_vector(sender, instance, created, **kwargs):
    """
    Update search vector when product is saved.
    
    Uses transaction.on_commit to avoid issues with unsaved related objects
    and to batch the update if multiple saves happen in same transaction.
    """
    def do_update():
        from .models import Product
        
        # Skip if called during migration or if instance was deleted
        if not instance.pk:
            return
        
        try:
            # Update search vector using raw SQL for performance
            # This avoids re-triggering the signal
            search_vector = SearchVector('name', weight='A', config='simple') + \
                           SearchVector('description', weight='B', config='simple') + \
                           SearchVector('sku', weight='A', config='simple')
            
            Product.objects.filter(pk=instance.pk).update(
                search_vector=search_vector
            )
        except Exception:
            # Silently fail - search will still work with fallback
            pass
    
    # Schedule update after transaction commits
    transaction.on_commit(do_update)
