"""
Notification helper functions for creating notifications throughout the app.

Usage:
    from apps.notifications.helpers import notify_order_status_changed
    notify_order_status_changed(order, old_status, new_status)
"""
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from .models import Notification, NotificationPreference

logger = logging.getLogger(__name__)


def send_realtime_notification(user_id: str, notification_data: dict):
    """
    Send notification via WebSocket to user.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"notifications_{user_id}",
                {
                    "type": "notification.message",
                    "notification": notification_data,
                }
            )
    except Exception as e:
        logger.warning(f"Failed to send realtime notification: {e}")


def create_notification(
    user,
    notification_type: str,
    title: str,
    message: str,
    link: str = "",
    data: dict = None,
    send_realtime: bool = True,
) -> Notification | None:
    """
    Create a notification for a user and optionally send via WebSocket.
    
    Args:
        user: User instance to notify
        notification_type: One of Notification.NotificationType choices
        title: Notification title
        message: Notification message/body
        link: Optional link (e.g., /account/orders/xxx)
        data: Optional JSON data
        send_realtime: Whether to push via WebSocket
        
    Returns:
        Created Notification instance or None if user has disabled this type
    """
    if data is None:
        data = {}
    
    # Check user preferences
    try:
        prefs = NotificationPreference.objects.get(user=user)
        
        # Check if user wants this type of notification (in-app)
        pref_mapping = {
            'order': 'push_orders',
            'payment': 'push_orders',  # Payment notifications fall under orders
            'shipping': 'push_orders',  # Shipping notifications fall under orders
            'review': 'push_marketing',  # Review notifications
            'promotion': 'push_marketing',
            'system': True,  # Always show system notifications
        }
        
        pref_field = pref_mapping.get(notification_type, True)
        if isinstance(pref_field, str) and not getattr(prefs, pref_field, True):
            logger.debug(f"User {user.email} has disabled {notification_type} notifications")
            return None
            
    except NotificationPreference.DoesNotExist:
        # No preferences set, use defaults (all enabled)
        pass
    
    # Create notification
    notification = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
        data=data,
    )
    
    # Send via WebSocket
    if send_realtime:
        send_realtime_notification(
            str(user.id),
            {
                "id": str(notification.id),
                "type": notification.notification_type,
                "title": notification.title,
                "message": notification.message,
                "link": notification.link,
                "data": notification.data,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat(),
            }
        )
    
    return notification


# ==========================================
# Order Notifications
# ==========================================

def notify_order_created(order):
    """Notify customer that their order was created."""
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.ORDER,
        title="Đơn hàng đã được tạo",
        message=f"Đơn hàng #{order.order_number} đã được tạo thành công. Vui lòng hoàn tất thanh toán.",
        link=f"/account/orders/{order.id}",
        data={"order_id": str(order.id), "order_number": order.order_number},
    )


def notify_order_confirmed(order):
    """Notify customer that their order was confirmed."""
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.ORDER,
        title="Đơn hàng đã được xác nhận",
        message=f"Đơn hàng #{order.order_number} đã được xác nhận và đang được xử lý.",
        link=f"/account/orders/{order.id}",
        data={"order_id": str(order.id), "order_number": order.order_number},
    )


def notify_order_processing(order):
    """Notify customer that their order is being processed."""
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.ORDER,
        title="Đơn hàng đang được xử lý",
        message=f"Đơn hàng #{order.order_number} đang được đóng gói và chuẩn bị giao.",
        link=f"/account/orders/{order.id}",
        data={"order_id": str(order.id), "order_number": order.order_number},
    )


def notify_order_shipped(order):
    """Notify customer that their order has been shipped."""
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.SHIPPING,
        title="Đơn hàng đang được giao",
        message=f"Đơn hàng #{order.order_number} đã được giao cho đơn vị vận chuyển.",
        link=f"/account/orders/{order.id}",
        data={"order_id": str(order.id), "order_number": order.order_number},
    )


def notify_order_delivered(order):
    """Notify customer that their order was delivered."""
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.ORDER,
        title="Đơn hàng đã giao thành công",
        message=f"Đơn hàng #{order.order_number} đã được giao thành công. Cảm ơn bạn đã mua hàng!",
        link=f"/account/orders/{order.id}",
        data={"order_id": str(order.id), "order_number": order.order_number},
    )


def notify_order_cancelled(order, reason: str = ""):
    """Notify customer that their order was cancelled."""
    message = f"Đơn hàng #{order.order_number} đã bị hủy."
    if reason:
        message += f" Lý do: {reason}"
    
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.ORDER,
        title="Đơn hàng đã bị hủy",
        message=message,
        link=f"/account/orders/{order.id}",
        data={"order_id": str(order.id), "order_number": order.order_number, "reason": reason},
    )


def notify_order_status_changed(order, old_status: str, new_status: str):
    """
    Main entry point for order status change notifications.
    Routes to the appropriate specific notification function.
    """
    status_handlers = {
        'confirmed': notify_order_confirmed,
        'processing': notify_order_processing,
        'shipped': notify_order_shipped,
        'delivered': notify_order_delivered,
        'cancelled': notify_order_cancelled,
    }
    
    handler = status_handlers.get(new_status)
    if handler:
        handler(order)


# ==========================================
# Vendor Order Notifications
# ==========================================

def notify_vendor_new_order(vendor_order):
    """Notify vendor about a new order."""
    vendor = vendor_order.vendor
    if not vendor.user:
        return
    
    create_notification(
        user=vendor.user,
        notification_type=Notification.NotificationType.ORDER,
        title="Đơn hàng mới",
        message=f"Bạn có đơn hàng mới #{vendor_order.order.order_number} với {vendor_order.items.count()} sản phẩm.",
        link=f"/seller/orders/{vendor_order.id}",
        data={
            "vendor_order_id": str(vendor_order.id),
            "order_number": vendor_order.order.order_number,
        },
    )


def notify_vendor_order_cancelled(vendor_order, reason: str = ""):
    """Notify vendor that an order was cancelled."""
    vendor = vendor_order.vendor
    if not vendor.user:
        return
    
    message = f"Đơn hàng #{vendor_order.order.order_number} đã bị hủy bởi khách hàng."
    if reason:
        message += f" Lý do: {reason}"
    
    create_notification(
        user=vendor.user,
        notification_type=Notification.NotificationType.ORDER,
        title="Đơn hàng đã bị hủy",
        message=message,
        link=f"/seller/orders/{vendor_order.id}",
        data={
            "vendor_order_id": str(vendor_order.id),
            "order_number": vendor_order.order.order_number,
            "reason": reason,
        },
    )


# ==========================================
# Payment Notifications
# ==========================================

def notify_payment_successful(payment):
    """Notify customer that payment was successful."""
    order = payment.order
    if not order.user:
        return
    
    amount_display = f"{int(payment.amount):,}".replace(",", ".") + "₫"
    
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.PAYMENT,
        title="Thanh toán thành công",
        message=f"Thanh toán {amount_display} cho đơn hàng #{order.order_number} đã được xác nhận.",
        link=f"/account/orders/{order.id}",
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "payment_id": str(payment.id),
            "amount": str(payment.amount),
        },
    )


def notify_payment_failed(payment, reason: str = ""):
    """Notify customer that payment failed."""
    order = payment.order
    if not order.user:
        return
    
    message = f"Thanh toán cho đơn hàng #{order.order_number} không thành công."
    if reason:
        message += f" Lý do: {reason}"
    message += " Vui lòng thử lại hoặc chọn phương thức thanh toán khác."
    
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.PAYMENT,
        title="Thanh toán thất bại",
        message=message,
        link=f"/account/orders/{order.id}",
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "reason": reason,
        },
    )


def notify_refund_approved(refund_request):
    """Notify customer that their refund was approved."""
    order = refund_request.order
    if not order.user:
        return
    
    amount_display = f"{int(refund_request.amount):,}".replace(",", ".") + "₫"
    
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.PAYMENT,
        title="Yêu cầu hoàn tiền đã được duyệt",
        message=f"Yêu cầu hoàn tiền {amount_display} cho đơn hàng #{order.order_number} đã được duyệt. Tiền sẽ được hoàn trong 3-5 ngày làm việc.",
        link=f"/account/orders/{order.id}",
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "refund_amount": str(refund_request.amount),
        },
    )


def notify_refund_rejected(refund_request, reason: str = ""):
    """Notify customer that their refund was rejected."""
    order = refund_request.order
    if not order.user:
        return
    
    message = f"Yêu cầu hoàn tiền cho đơn hàng #{order.order_number} đã bị từ chối."
    if reason:
        message += f" Lý do: {reason}"
    
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.PAYMENT,
        title="Yêu cầu hoàn tiền bị từ chối",
        message=message,
        link=f"/account/orders/{order.id}",
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "reason": reason,
        },
    )


def notify_refund_completed(refund_request):
    """Notify customer that refund has been processed."""
    order = refund_request.order
    if not order.user:
        return
    
    amount_display = f"{int(refund_request.amount):,}".replace(",", ".") + "₫"
    
    create_notification(
        user=order.user,
        notification_type=Notification.NotificationType.PAYMENT,
        title="Hoàn tiền đã hoàn tất",
        message=f"Số tiền {amount_display} cho đơn hàng #{order.order_number} đã được hoàn về tài khoản/ví của bạn.",
        link=f"/account/orders/{order.id}",
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "refund_amount": str(refund_request.amount),
        },
    )


# ==========================================
# Review Notifications
# ==========================================

def notify_review_reply(review, reply_by):
    """Notify customer that their review received a reply."""
    if not review.user:
        return
    
    create_notification(
        user=review.user,
        notification_type=Notification.NotificationType.REVIEW,
        title="Đánh giá của bạn đã được phản hồi",
        message=f"{reply_by} đã phản hồi đánh giá của bạn cho sản phẩm {review.product.name}.",
        link=f"/products/{review.product.slug}#reviews",
        data={
            "product_id": str(review.product.id),
            "product_slug": review.product.slug,
            "review_id": str(review.id),
        },
    )


def notify_review_helpful(review, helpful_count: int):
    """Notify customer that their review was marked helpful."""
    if not review.user:
        return
    
    # Only notify at certain milestones
    if helpful_count not in [1, 5, 10, 25, 50, 100]:
        return
    
    create_notification(
        user=review.user,
        notification_type=Notification.NotificationType.REVIEW,
        title="Đánh giá của bạn hữu ích!",
        message=f"{helpful_count} người thấy đánh giá của bạn cho sản phẩm {review.product.name} hữu ích.",
        link=f"/products/{review.product.slug}#reviews",
        data={
            "product_id": str(review.product.id),
            "review_id": str(review.id),
            "helpful_count": helpful_count,
        },
    )


# ==========================================
# Vendor Status Notifications
# ==========================================

def notify_vendor_approved(vendor):
    """Notify vendor that their application was approved."""
    if not vendor.user:
        return
    
    create_notification(
        user=vendor.user,
        notification_type=Notification.NotificationType.SYSTEM,
        title="Chúc mừng! Shop đã được duyệt",
        message=f"Shop {vendor.store_name} của bạn đã được duyệt. Bạn có thể bắt đầu đăng bán sản phẩm ngay bây giờ!",
        link="/seller/products/new",
        data={"vendor_id": str(vendor.id), "store_name": vendor.store_name},
    )


def notify_vendor_rejected(vendor, reason: str = ""):
    """Notify vendor that their application was rejected."""
    if not vendor.user:
        return
    
    message = f"Đơn đăng ký shop {vendor.store_name} đã bị từ chối."
    if reason:
        message += f" Lý do: {reason}"
    message += " Bạn có thể chỉnh sửa thông tin và đăng ký lại."
    
    create_notification(
        user=vendor.user,
        notification_type=Notification.NotificationType.SYSTEM,
        title="Đơn đăng ký shop bị từ chối",
        message=message,
        link="/seller/register",
        data={"vendor_id": str(vendor.id), "reason": reason},
    )


def notify_vendor_suspended(vendor, reason: str = ""):
    """Notify vendor that their shop was suspended."""
    if not vendor.user:
        return
    
    message = f"Shop {vendor.store_name} của bạn đã bị tạm ngưng hoạt động."
    if reason:
        message += f" Lý do: {reason}"
    message += " Vui lòng liên hệ hỗ trợ để biết thêm chi tiết."
    
    create_notification(
        user=vendor.user,
        notification_type=Notification.NotificationType.SYSTEM,
        title="Shop bị tạm ngưng",
        message=message,
        link="/seller",
        data={"vendor_id": str(vendor.id), "reason": reason},
    )


# ==========================================
# Promotion Notifications
# ==========================================

def notify_flash_sale_starting(user, sale_name: str, start_time):
    """Notify user about an upcoming flash sale."""
    create_notification(
        user=user,
        notification_type=Notification.NotificationType.PROMOTION,
        title="Flash Sale sắp bắt đầu!",
        message=f"{sale_name} sẽ bắt đầu lúc {start_time.strftime('%H:%M')}. Đừng bỏ lỡ!",
        link="/deals",
        data={"sale_name": sale_name, "start_time": start_time.isoformat()},
    )


def notify_price_drop(user, product, old_price, new_price):
    """Notify user about a price drop on wishlist item."""
    discount_percent = int((1 - new_price / old_price) * 100)
    new_price_display = f"{int(new_price):,}".replace(",", ".") + "₫"
    
    create_notification(
        user=user,
        notification_type=Notification.NotificationType.PROMOTION,
        title=f"Giá giảm {discount_percent}%!",
        message=f"{product.name} trong danh sách yêu thích của bạn đang giảm giá còn {new_price_display}.",
        link=f"/products/{product.slug}",
        data={
            "product_id": str(product.id),
            "product_slug": product.slug,
            "old_price": str(old_price),
            "new_price": str(new_price),
            "discount_percent": discount_percent,
        },
    )


def notify_back_in_stock(user, product):
    """Notify user that a wishlist item is back in stock."""
    create_notification(
        user=user,
        notification_type=Notification.NotificationType.PROMOTION,
        title="Sản phẩm đã có hàng trở lại!",
        message=f"{product.name} trong danh sách yêu thích của bạn đã có hàng trở lại. Đặt hàng ngay!",
        link=f"/products/{product.slug}",
        data={
            "product_id": str(product.id),
            "product_slug": product.slug,
        },
    )
