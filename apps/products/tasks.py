"""
Celery tasks for product management.
"""
from celery import shared_task
from django.core.cache import cache
from django.db.models import F
import logging

from .models import Product

logger = logging.getLogger(__name__)

# Redis key prefix for view counts
VIEW_COUNT_PREFIX = 'product_view_count:'


def increment_view_count(product_id):
    """
    Increment product view count in Redis (fast, non-blocking).
    
    This function should be called from the view instead of direct DB update.
    The actual DB sync happens via Celery task periodically.
    """
    cache_key = f"{VIEW_COUNT_PREFIX}{product_id}"
    try:
        # Use Redis INCR for atomic increment
        # If key doesn't exist, it will be created with value 1
        current = cache.get(cache_key, 0)
        cache.set(cache_key, current + 1, timeout=None)  # No expiry, we'll clean up after sync
        return True
    except Exception as e:
        logger.warning(f"Failed to increment view count in Redis for product {product_id}: {e}")
        return False


def get_view_count_from_cache(product_id):
    """
    Get the pending view count increment from Redis.
    """
    cache_key = f"{VIEW_COUNT_PREFIX}{product_id}"
    return cache.get(cache_key, 0)


@shared_task
def sync_view_counts_to_db():
    """
    Sync view counts from Redis to Database.
    
    This task runs periodically (every 10 minutes) to:
    1. Read all pending view counts from Redis
    2. Update the database in bulk
    3. Clear the Redis counters
    
    This approach reduces database writes from potentially thousands per minute
    to a single batch update every 10 minutes.
    """
    from django.core.cache import cache as django_cache
    
    # Get all product view count keys from Redis
    # Note: This requires redis-py client access for SCAN
    try:
        # Get the underlying Redis client
        redis_client = django_cache.client.get_client()
        
        # Find all view count keys
        pattern = f"{VIEW_COUNT_PREFIX}*"
        keys = []
        cursor = 0
        
        # Use SCAN to iterate through keys (production-safe)
        while True:
            cursor, partial_keys = redis_client.scan(cursor, match=pattern, count=100)
            keys.extend(partial_keys)
            if cursor == 0:
                break
        
        if not keys:
            logger.info("No view counts to sync")
            return "No view counts to sync"
        
        # Process in batches
        synced_count = 0
        
        for key in keys:
            try:
                # Get and delete atomically using GETDEL (Redis 6.2+) or GET + DEL
                if hasattr(redis_client, 'getdel'):
                    count = redis_client.getdel(key)
                else:
                    count = redis_client.get(key)
                    if count:
                        redis_client.delete(key)
                
                if count:
                    count = int(count)
                    # Extract product_id from key
                    product_id = key.decode() if isinstance(key, bytes) else key
                    product_id = product_id.replace(VIEW_COUNT_PREFIX, '')
                    
                    # Update database
                    updated = Product.objects.filter(id=product_id).update(
                        view_count=F('view_count') + count
                    )
                    
                    if updated:
                        synced_count += 1
                        logger.debug(f"Synced {count} views for product {product_id}")
                        
            except Exception as e:
                logger.error(f"Failed to sync view count for key {key}: {e}")
        
        logger.info(f"Synced view counts for {synced_count} products")
        return f"Synced view counts for {synced_count} products"
        
    except Exception as e:
        logger.error(f"Failed to sync view counts: {e}")
        # Fallback: try direct cache approach
        return _sync_view_counts_fallback()


def _sync_view_counts_fallback():
    """
    Fallback sync method when direct Redis access is not available.
    
    This method queries all products and checks for cached view counts.
    Less efficient but works with any cache backend.
    """
    from .models import Product
    
    synced_count = 0
    
    # Get all product IDs (only active products to reduce load)
    product_ids = Product.objects.filter(is_active=True).values_list('id', flat=True)
    
    for product_id in product_ids:
        cache_key = f"{VIEW_COUNT_PREFIX}{product_id}"
        count = cache.get(cache_key)
        
        if count and count > 0:
            try:
                Product.objects.filter(id=product_id).update(
                    view_count=F('view_count') + count
                )
                cache.delete(cache_key)
                synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync view count for product {product_id}: {e}")
    
    logger.info(f"[Fallback] Synced view counts for {synced_count} products")
    return f"[Fallback] Synced view counts for {synced_count} products"
