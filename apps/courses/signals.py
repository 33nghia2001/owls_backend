"""
Django signals for cache invalidation
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Course, Category


@receiver([post_save, post_delete], sender=Course)
def invalidate_course_cache(sender, instance, **kwargs):
    """
    Invalidate course cache when course is updated or deleted.
    Ensures users always see fresh data after changes.
    """
    # Invalidate list cache
    cache.delete_pattern('views.decorators.cache.cache_page.*course*')
    
    # Invalidate specific course detail cache
    cache_key = f'course_detail_{instance.slug}'
    cache.delete(cache_key)


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_cache(sender, instance, **kwargs):
    """
    Invalidate category cache when category is updated.
    """
    cache.delete_pattern('views.decorators.cache.cache_page.*category*')
