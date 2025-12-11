"""
Celery tasks for order management.
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from django.conf import settings
from datetime import timedelta
import logging

from .models import Order, OrderStatusHistory

logger = logging.getLogger(__name__)


@shared_task
def cancel_expired_pending_orders():
    """
    Cancel orders that have been pending for too long without payment.
    This prevents inventory from being held indefinitely.
    
    Should be scheduled to run every 5-10 minutes via Celery Beat.
    """
    from apps.inventory.models import Inventory, InventoryMovement
    
    # Use configurable timeout (default 15 minutes to reduce DoI attack window)
    timeout_minutes = getattr(settings, 'PENDING_ORDER_TIMEOUT_MINUTES', 15)
    expiration_time = timezone.now() - timedelta(minutes=timeout_minutes)
    
    expired_orders = Order.objects.filter(
        status='pending',
        payment_status='pending',
        created_at__lt=expiration_time
    ).select_related('user').prefetch_related('items__product', 'items__variant')
    
    cancelled_count = 0
    
    for order in expired_orders:
        try:
            with transaction.atomic():
                # CRITICAL: Lock and re-fetch order to prevent race condition
                # If payment was just processed, status will no longer be 'pending'
                current_order = Order.objects.select_for_update().get(id=order.id)
                
                # Skip if order was already processed (e.g., payment just completed)
                if current_order.status != 'pending' or current_order.payment_status != 'pending':
                    logger.info(f"Skipping order {order.order_number} - already processed")
                    continue
                
                # Release reserved inventory for each order item
                # IMPORTANT: Sort items by inventory pk to prevent deadlock
                order_items = list(current_order.items.select_related('product', 'variant').all())
                
                # Get all inventories first and sort by pk
                item_inventory_pairs = []
                for item in order_items:
                    if item.variant:
                        inventory = Inventory.objects.filter(variant=item.variant).first()
                    else:
                        inventory = Inventory.objects.filter(product=item.product).first()
                    if inventory:
                        item_inventory_pairs.append((item, inventory))
                
                # Sort by inventory pk to ensure consistent locking order
                item_inventory_pairs.sort(key=lambda x: x[1].pk)
                
                for item, inventory in item_inventory_pairs:
                    # Lock inventory in consistent order
                    locked_inventory = Inventory.objects.select_for_update().get(pk=inventory.pk)
                    
                for item, inventory in item_inventory_pairs:
                    # Lock inventory in consistent order
                    locked_inventory = Inventory.objects.select_for_update().get(pk=inventory.pk)
                    
                    # Release the reserved quantity
                    Inventory.objects.filter(pk=locked_inventory.pk).update(
                        reserved_quantity=F('reserved_quantity') - item.quantity
                    )
                    
                    # Log the inventory movement
                    InventoryMovement.objects.create(
                        inventory=locked_inventory,
                        movement_type='released',
                        quantity=item.quantity,
                        reference_type='order_expired',
                        reference_id=str(current_order.id),
                        note=f'Auto-released from expired order {current_order.order_number}'
                    )
                
                # Update order status
                current_order.status = 'cancelled'
                current_order.cancelled_at = timezone.now()
                current_order.note = f'Auto-cancelled due to payment timeout ({timeout_minutes} minutes)'
                current_order.save()
                
                # Update all items
                current_order.items.update(status='cancelled')
                
                # Create status history
                OrderStatusHistory.objects.create(
                    order=current_order,
                    status='cancelled',
                    note=f'Auto-cancelled: Payment not received within {timeout_minutes} minutes'
                )
                
                cancelled_count += 1
                logger.info(f"Auto-cancelled expired order: {order.order_number}")
                
        except Exception as e:
            logger.error(f"Failed to cancel expired order {order.id}: {str(e)}")
    
    return f"Cancelled {cancelled_count} expired orders"


@shared_task
def send_order_confirmation_email(order_id):
    """
    Send order confirmation email to customer.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    
    try:
        order = Order.objects.select_related('user').get(id=order_id)
        
        subject = f'Xác nhận đơn hàng #{order.order_number}'
        message = f"""
Xin chào {order.shipping_name},

Cảm ơn bạn đã đặt hàng tại OWLS Marketplace!

Mã đơn hàng: {order.order_number}
Tổng tiền: {order.total}
Trạng thái: Đang chờ xử lý

Chúng tôi sẽ thông báo khi đơn hàng được xác nhận và vận chuyển.

Trân trọng,
OWLS Marketplace
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False
        )
        
        logger.info(f"Sent confirmation email for order: {order.order_number}")
        return f"Email sent for order {order.order_number}"
        
    except Order.DoesNotExist:
        logger.error(f"Order not found: {order_id}")
        return f"Order {order_id} not found"
    except Exception as e:
        logger.error(f"Failed to send email for order {order_id}: {str(e)}")
        raise


@shared_task
def update_order_statistics():
    """
    Update aggregated order statistics for analytics.
    Should be scheduled to run daily.
    """
    from apps.analytics.models import PlatformStats
    from django.db.models import Sum, Count
    
    today = timezone.now().date()
    
    # Get today's orders
    today_orders = Order.objects.filter(created_at__date=today)
    
    stats, created = PlatformStats.objects.get_or_create(date=today)
    stats.orders_count = today_orders.count()
    stats.orders_revenue = today_orders.filter(
        payment_status='paid'
    ).aggregate(total=Sum('total'))['total'] or 0
    stats.save()
    
    logger.info(f"Updated platform stats for {today}")
    return f"Stats updated for {today}"
