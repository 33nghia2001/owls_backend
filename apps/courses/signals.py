"""
Django signals for cache invalidation.

SECURITY: Optimized to prevent DoS attacks via expensive Redis KEYS/SCAN operations.
Uses cache versioning and targeted key deletion instead of pattern matching.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Course, Category


# Cache version keys - increment to invalidate entire namespace
COURSE_LIST_VERSION_KEY = 'cache_version:course_list'
CATEGORY_LIST_VERSION_KEY = 'cache_version:category_list'


@receiver([post_save, post_delete], sender=Course)
def invalidate_course_cache(sender, instance, **kwargs):
    """
    Clear course-related cache when a course is created/updated/deleted.
    
    SECURITY: Uses cache versioning to avoid expensive delete_pattern() operations
    which can cause Redis DoS via KEYS * or SCAN commands (O(N) complexity).
    Version increment is O(1) and much safer for production.
    """
    # Method 1: Increment version to invalidate all course list caches (O(1))
    current_version = cache.get(COURSE_LIST_VERSION_KEY, 0)
    cache.set(COURSE_LIST_VERSION_KEY, current_version + 1, timeout=None)
    
    # Method 2: Delete specific course detail cache (known key, O(1))
    cache.delete(f'course_detail_{instance.slug}')
    
    # Also invalidate related category cache since courses affect category counts
    current_cat_version = cache.get(CATEGORY_LIST_VERSION_KEY, 0)
    cache.set(CATEGORY_LIST_VERSION_KEY, current_cat_version + 1, timeout=None)


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_cache(sender, instance, **kwargs):
    """
    Clear category cache when a category is created/updated/deleted.
    
    SECURITY: Uses O(1) version increment instead of expensive pattern matching.
    """
    current_version = cache.get(CATEGORY_LIST_VERSION_KEY, 0)
    cache.set(CATEGORY_LIST_VERSION_KEY, current_version + 1, timeout=None)
