"""
Celery tasks for order management.
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import F
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
    
    # Orders pending for more than 30 minutes
    expiration_time = timezone.now() - timedelta(minutes=30)
    
    expired_orders = Order.objects.filter(
        status='pending',
        payment_status='pending',
        created_at__lt=expiration_time
    ).select_related('user').prefetch_related('items__product', 'items__variant')
    
    cancelled_count = 0
    
    for order in expired_orders:
        try:
            with transaction.atomic():
                # Release reserved inventory for each order item
                for item in order.items.all():
                    # Find the corresponding inventory
                    if item.variant:
                        inventory = Inventory.objects.filter(
                            variant=item.variant
                        ).select_for_update().first()
                    else:
                        inventory = Inventory.objects.filter(
                            product=item.product
                        ).select_for_update().first()
                    
                    if inventory:
                        # Release the reserved quantity
                        Inventory.objects.filter(pk=inventory.pk).update(
                            reserved_quantity=F('reserved_quantity') - item.quantity
                        )
                        
                        # Log the inventory movement
                        InventoryMovement.objects.create(
                            inventory=inventory,
                            movement_type='released',
                            quantity=item.quantity,
                            reference_type='order_expired',
                            reference_id=str(order.id),
                            note=f'Auto-released from expired order {order.order_number}'
                        )
                
                # Update order status
                order.status = 'cancelled'
                order.cancelled_at = timezone.now()
                order.note = 'Auto-cancelled due to payment timeout (30 minutes)'
                order.save()
                
                # Update all items
                order.items.update(status='cancelled')
                
                # Create status history
                OrderStatusHistory.objects.create(
                    order=order,
                    status='cancelled',
                    note='Auto-cancelled: Payment not received within 30 minutes'
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
