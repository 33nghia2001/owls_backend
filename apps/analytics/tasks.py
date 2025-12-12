"""
Celery tasks for analytics data aggregation.
Run daily via Celery beat to populate VendorStats and PlatformStats.
"""

from celery import shared_task
from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import ProductView, VendorStats, PlatformStats


@shared_task(name='analytics.populate_vendor_stats')
def populate_vendor_stats(date_str=None):
    """
    Populate daily vendor statistics.
    
    Args:
        date_str: Date in 'YYYY-MM-DD' format, defaults to yesterday
    """
    from apps.vendors.models import Vendor
    from apps.orders.models import Order, OrderItem
    from apps.reviews.models import Review
    from apps.messaging.models import Message
    
    if date_str:
        from datetime import datetime
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        target_date = timezone.now().date() - timedelta(days=1)
    
    # Get date range for the target date
    start_datetime = timezone.make_aware(
        timezone.datetime.combine(target_date, timezone.datetime.min.time())
    )
    end_datetime = timezone.make_aware(
        timezone.datetime.combine(target_date, timezone.datetime.max.time())
    )
    
    vendors = Vendor.objects.filter(status='approved')
    stats_created = 0
    stats_updated = 0
    
    for vendor in vendors:
        # Calculate orders stats
        vendor_orders = Order.objects.filter(
            items__product__vendor=vendor,
            created_at__range=(start_datetime, end_datetime)
        ).distinct()
        
        orders_count = vendor_orders.count()
        
        # Calculate revenue from order items belonging to this vendor
        revenue = OrderItem.objects.filter(
            order__in=vendor_orders,
            product__vendor=vendor
        ).aggregate(
            total=Sum(models.F('price') * models.F('quantity'))
        )['total'] or Decimal('0')
        
        # Products sold
        products_sold = OrderItem.objects.filter(
            order__in=vendor_orders,
            product__vendor=vendor,
            order__status__in=['confirmed', 'processing', 'shipped', 'delivered']
        ).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        # Product views
        product_views = ProductView.objects.filter(
            product__vendor=vendor,
            viewed_at__range=(start_datetime, end_datetime)
        ).count()
        
        # New reviews
        new_reviews = Review.objects.filter(
            product__vendor=vendor,
            created_at__range=(start_datetime, end_datetime)
        ).count()
        
        # Messages received (conversations where vendor received messages)
        messages_received = Message.objects.filter(
            conversation__vendor=vendor,
            created_at__range=(start_datetime, end_datetime)
        ).exclude(sender=vendor.user).count()
        
        # Create or update stats
        stats, created = VendorStats.objects.update_or_create(
            vendor=vendor,
            date=target_date,
            defaults={
                'orders_count': orders_count,
                'orders_revenue': revenue,
                'products_sold': products_sold,
                'product_views': product_views,
                'new_reviews': new_reviews,
                'messages_received': messages_received,
            }
        )
        
        if created:
            stats_created += 1
        else:
            stats_updated += 1
    
    return {
        'date': str(target_date),
        'vendors_processed': vendors.count(),
        'stats_created': stats_created,
        'stats_updated': stats_updated,
    }


@shared_task(name='analytics.populate_platform_stats')
def populate_platform_stats(date_str=None):
    """
    Populate daily platform-wide statistics.
    
    Args:
        date_str: Date in 'YYYY-MM-DD' format, defaults to yesterday
    """
    from apps.users.models import Users
    from apps.vendors.models import Vendor
    from apps.orders.models import Order
    from apps.products.models import Product
    
    if date_str:
        from datetime import datetime
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        target_date = timezone.now().date() - timedelta(days=1)
    
    # Get date range
    start_datetime = timezone.make_aware(
        timezone.datetime.combine(target_date, timezone.datetime.min.time())
    )
    end_datetime = timezone.make_aware(
        timezone.datetime.combine(target_date, timezone.datetime.max.time())
    )
    
    # Users stats
    new_users = Users.objects.filter(
        date_joined__range=(start_datetime, end_datetime)
    ).count()
    
    # Active users = users who placed orders or viewed products
    active_user_ids = set()
    
    # Users who placed orders
    order_users = Order.objects.filter(
        created_at__range=(start_datetime, end_datetime)
    ).values_list('user_id', flat=True)
    active_user_ids.update(order_users)
    
    # Users who viewed products
    view_users = ProductView.objects.filter(
        viewed_at__range=(start_datetime, end_datetime),
        user__isnull=False
    ).values_list('user_id', flat=True)
    active_user_ids.update(view_users)
    
    active_users = len(active_user_ids)
    
    # Vendors stats
    new_vendors = Vendor.objects.filter(
        created_at__range=(start_datetime, end_datetime),
        status='approved'
    ).count()
    
    # Active vendors = vendors with orders or product updates
    active_vendor_ids = set()
    
    vendor_with_orders = Order.objects.filter(
        created_at__range=(start_datetime, end_datetime)
    ).values_list('items__product__vendor_id', flat=True)
    active_vendor_ids.update(v for v in vendor_with_orders if v)
    
    active_vendors = len(active_vendor_ids)
    
    # Orders stats
    orders = Order.objects.filter(
        created_at__range=(start_datetime, end_datetime)
    )
    orders_count = orders.count()
    
    revenue = orders.filter(
        status__in=['confirmed', 'processing', 'shipped', 'delivered']
    ).aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')
    
    # Products stats
    new_products = Product.objects.filter(
        created_at__range=(start_datetime, end_datetime),
        status='active'
    ).count()
    
    product_views = ProductView.objects.filter(
        viewed_at__range=(start_datetime, end_datetime)
    ).count()
    
    # Create or update platform stats
    stats, created = PlatformStats.objects.update_or_create(
        date=target_date,
        defaults={
            'new_users': new_users,
            'active_users': active_users,
            'new_vendors': new_vendors,
            'active_vendors': active_vendors,
            'orders_count': orders_count,
            'orders_revenue': revenue,
            'new_products': new_products,
            'product_views': product_views,
        }
    )
    
    return {
        'date': str(target_date),
        'created': created,
        'stats': {
            'new_users': new_users,
            'active_users': active_users,
            'new_vendors': new_vendors,
            'active_vendors': active_vendors,
            'orders_count': orders_count,
            'orders_revenue': float(revenue),
            'new_products': new_products,
            'product_views': product_views,
        }
    }


@shared_task(name='analytics.cleanup_old_product_views')
def cleanup_old_product_views(days=90):
    """
    Delete old product view records to prevent database bloat.
    
    Args:
        days: Delete records older than this many days (default 90)
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    deleted_count, _ = ProductView.objects.filter(
        viewed_at__lt=cutoff_date
    ).delete()
    
    return {
        'deleted_count': deleted_count,
        'cutoff_date': str(cutoff_date.date()),
    }


@shared_task(name='analytics.populate_all_stats')
def populate_all_stats(date_str=None):
    """
    Convenience task to run both vendor and platform stats population.
    """
    vendor_result = populate_vendor_stats(date_str)
    platform_result = populate_platform_stats(date_str)
    
    return {
        'vendor_stats': vendor_result,
        'platform_stats': platform_result,
    }


@shared_task(name='analytics.backfill_stats')
def backfill_stats(days=30):
    """
    Backfill stats for the last N days.
    Useful when setting up analytics for the first time.
    
    Args:
        days: Number of days to backfill (default 30)
    """
    results = []
    today = timezone.now().date()
    
    for i in range(days, 0, -1):
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime('%Y-%m-%d')
        
        result = populate_all_stats(date_str)
        results.append({
            'date': date_str,
            'result': result
        })
    
    return {
        'days_processed': days,
        'results': results
    }
