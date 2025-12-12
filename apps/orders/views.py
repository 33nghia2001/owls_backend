from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from django.conf import settings

from .models import Order, OrderItem, OrderStatusHistory
from .serializers import (
    OrderListSerializer, OrderDetailSerializer, CreateOrderSerializer,
    UpdateOrderStatusSerializer, VendorOrderItemSerializer
)
from apps.cart.models import Cart
from apps.coupons.models import Coupon, CouponUsage
from apps.vendors.permissions import IsApprovedVendor
from apps.inventory.models import Inventory, InventoryMovement


class SensitiveRateThrottle(ScopedRateThrottle):
    """Custom throttle for sensitive operations like order creation."""
    scope = 'sensitive'


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for customer orders."""
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_status']
    ordering_fields = ['created_at', 'total']
    
    def get_permissions(self):
        """
        - create: Allow guest checkout (AllowAny)
        - list, retrieve, update, destroy: Require authentication
        """
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        if self.action == 'create':
            return CreateOrderSerializer
        return OrderDetailSerializer
    
    def get_queryset(self):
        # Optimized query with select_related and prefetch_related
        # Only authenticated users can list their orders
        if not self.request.user.is_authenticated:
            return Order.objects.none()
        
        return Order.objects.filter(
            user=self.request.user
        ).select_related(
            'user',
            'coupon'
        ).prefetch_related(
            'items__product__vendor',
            'items__product__images',
            'items__variant',
            'status_history'
        ).order_by('-created_at')
    
    def get_throttles(self):
        """Apply stricter throttling for order creation."""
        if self.action == 'create':
            return [SensitiveRateThrottle()]
        return super().get_throttles()
    
    @transaction.atomic
    def create(self, request):
        """Create order from cart. Supports both authenticated users and guests."""
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        # Get cart - for authenticated user or guest via session_key
        cart = None
        user = request.user if request.user.is_authenticated else None
        guest_cart_id = data.get('guest_cart_id') or request.data.get('guest_cart_id')
        
        if user:
            # Authenticated user
            try:
                cart = Cart.objects.get(user=user)
            except Cart.DoesNotExist:
                pass
        
        if not cart and guest_cart_id:
            # Guest checkout with cart ID
            try:
                cart = Cart.objects.get(session_key=guest_cart_id, user__isnull=True)
            except Cart.DoesNotExist:
                pass
        
        if not cart:
            return Response(
                {'error': 'Giỏ hàng trống hoặc không tìm thấy.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not cart.items.exists():
            return Response(
                {'error': 'Giỏ hàng trống.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get cart items with optimized query
        # Sort by product_id and variant_id to prevent deadlock when using select_for_update
        cart_items = cart.items.select_related(
            'product__vendor',
            'variant'
        ).order_by('product__id', 'variant__id')
        
        # Check limit on pending orders per user to prevent Denial of Inventory attack
        # For guests, use guest email or skip this check (handled by rate limiting)
        if user:
            pending_order_count = Order.objects.filter(
                user=user,
                status='pending',
                payment_status='pending'
            ).count()
            max_pending_orders = getattr(settings, 'MAX_PENDING_ORDERS_PER_USER', 3)
            if pending_order_count >= max_pending_orders:
                return Response(
                    {'error': f'Bạn đã có {pending_order_count} đơn hàng chưa thanh toán. Vui lòng thanh toán hoặc hủy trước khi đặt đơn mới.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
        
        # 1. CHECK INVENTORY AND VALIDATE PRICES BEFORE CREATING ORDER
        inventory_updates = []  # Store inventory objects to update later
        price_changes = []  # Track any price changes for user notification
        
        for item in cart_items:
            # Get inventory for variant or product
            if item.variant:
                inventory = Inventory.objects.filter(variant=item.variant).select_for_update().first()
                current_price = item.variant.price
            else:
                inventory = Inventory.objects.filter(product=item.product).select_for_update().first()
                current_price = item.product.price
            
            if not inventory:
                return Response(
                    {'error': f'Sản phẩm "{item.product.name}" chưa được thiết lập kho.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if inventory.available_quantity < item.quantity:
                return Response(
                    {'error': f'Sản phẩm "{item.product.name}" không đủ số lượng tồn kho. Còn lại: {inventory.available_quantity}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # SECURITY: Block order if price changed - require user confirmation
            # This prevents "price slippage" where user pays more than expected
            if item.unit_price != current_price:
                price_changes.append({
                    'product': item.product.name,
                    'old_price': str(item.unit_price),
                    'new_price': str(current_price)
                })
            
            inventory_updates.append((item, inventory))
        
        # If any prices changed, return 409 Conflict requiring user to refresh cart
        if price_changes:
            return Response(
                {
                    'error': 'Giá một số sản phẩm đã thay đổi. Vui lòng cập nhật giỏ hàng.',
                    'price_changes': price_changes,
                    'action_required': 'refresh_cart'
                },
                status=status.HTTP_409_CONFLICT
            )
        
        # Recalculate cart subtotal after price updates
        cart.refresh_from_db()
        subtotal = cart.subtotal
        
        shipping_cost = getattr(settings, 'DEFAULT_SHIPPING_COST', 30000)
        # Free shipping for orders over threshold (if configured)
        free_shipping_threshold = getattr(settings, 'FREE_SHIPPING_THRESHOLD', None)
        if free_shipping_threshold and subtotal >= free_shipping_threshold:
            shipping_cost = 0
        discount_amount = 0
        
        # Apply coupon if provided
        coupon = None
        coupon_code = data.get('coupon_code')
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code, is_active=True)
                if coupon.is_valid():
                    # Handle free_shipping coupon type
                    if coupon.discount_type == 'free_shipping':
                        shipping_cost = 0
                    else:
                        discount_amount = coupon.calculate_discount(subtotal)
                else:
                    # Coupon exists but is not valid (expired, usage limit, etc.)
                    return Response(
                        {'error': 'Mã giảm giá đã hết hạn hoặc không còn hiệu lực.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Coupon.DoesNotExist:
                # Coupon code not found - inform user instead of silently ignoring
                return Response(
                    {'error': 'Mã giảm giá không tồn tại.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        total = subtotal + shipping_cost - discount_amount
        
        # Create order (user can be None for guest checkout)
        order = Order.objects.create(
            user=user,  # Can be None for guest orders
            guest_email=data.get('guest_email') if not user else None,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            discount_amount=discount_amount,
            total=total,
            shipping_name=data['shipping_name'],
            shipping_phone=data['shipping_phone'],
            shipping_address=data['shipping_address'],
            shipping_province=data['shipping_province'],
            shipping_ward=data['shipping_ward'],
            shipping_country=data.get('shipping_country', 'Vietnam'),
            shipping_postal_code=data.get('shipping_postal_code', ''),
            coupon=coupon,
            customer_note=data.get('customer_note', '')
        )
        
        # Copy billing address if different
        if not data.get('same_as_shipping', True):
            order.billing_name = data.get('billing_name', '')
            order.billing_phone = data.get('billing_phone', '')
            order.billing_address = data.get('billing_address', '')
            order.billing_province = data.get('billing_province', '')
            order.billing_ward = data.get('billing_ward', '')
            order.billing_country = data.get('billing_country', '')
            order.billing_postal_code = data.get('billing_postal_code', '')
            order.save()
        
        # 2. CREATE ORDER ITEMS AND RESERVE INVENTORY
        for cart_item, inventory in inventory_updates:
            # Create order item
            OrderItem.objects.create(
                order=order,
                vendor=cart_item.product.vendor,
                product=cart_item.product,
                variant=cart_item.variant,
                product_name=cart_item.product.name,
                product_sku=cart_item.product.sku or '',
                variant_name=cart_item.variant.name if cart_item.variant else '',
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price,
                commission_rate=cart_item.product.vendor.commission_rate
            )
            
            # Reserve inventory (using F() to avoid race conditions)
            Inventory.objects.filter(pk=inventory.pk).update(
                reserved_quantity=F('reserved_quantity') + cart_item.quantity
            )
            
            # Log inventory movement (created_by can be None for guest orders)
            InventoryMovement.objects.create(
                inventory=inventory,
                movement_type='reserved',
                quantity=cart_item.quantity,
                reference_type='order',
                reference_id=str(order.id),
                note=f'Reserved for order {order.order_number}',
                created_by=user  # Use user variable (can be None for guests)
            )
        
        # Create status history (created_by can be None for guest orders)
        OrderStatusHistory.objects.create(
            order=order,
            status='pending',
            note='Order created',
            created_by=user  # Use user variable (can be None for guests)
        )
        
        # Clear cart
        cart.clear()
        
        # Increment coupon usage with race condition protection
        if coupon:
            # Atomic update with usage_limit check
            if coupon.usage_limit:
                updated = Coupon.objects.filter(
                    id=coupon.id,
                    used_count__lt=F('usage_limit')
                ).update(used_count=F('used_count') + 1)
                
                if updated == 0:
                    # Coupon usage limit exceeded - raise ValidationError to trigger transaction rollback
                    raise ValidationError({'coupon_code': 'Mã giảm giá đã hết lượt sử dụng.'})
            else:
                Coupon.objects.filter(id=coupon.id).update(used_count=F('used_count') + 1)
            
            # Create CouponUsage record for tracking (user can be None for guests)
            CouponUsage.objects.create(
                coupon=coupon,
                user=user,  # Can be None for guest checkout
                order=order,
                discount_applied=order.discount_amount
            )
        
        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def cancel(self, request, pk=None):
        """Cancel an order and release reserved inventory."""
        order = self.get_object()
        
        if order.status not in ['pending', 'confirmed']:
            return Response(
                {'error': 'Cannot cancel order in current status.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 1. Release reserved inventory for each order item
        for item in order.items.select_related('product', 'variant').all():
            # Find the corresponding inventory
            if item.variant:
                inventory = Inventory.objects.filter(variant=item.variant).select_for_update().first()
            else:
                inventory = Inventory.objects.filter(product=item.product).select_for_update().first()
            
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
                    reference_type='order_cancellation',
                    reference_id=str(order.id),
                    note=f'Released stock from cancelled order {order.order_number}',
                    created_by=request.user
                )
        
        # 2. Update order status
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.save()
        
        # Update all items
        order.items.update(status='cancelled')
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='cancelled',
            note='Cancelled by customer',
            created_by=request.user
        )
        
        return Response(OrderDetailSerializer(order).data)


class VendorOrderViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for vendor to manage their order items."""
    serializer_class = VendorOrderItemSerializer
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        # Optimized query to avoid N+1
        return OrderItem.objects.filter(
            vendor=self.request.user.vendor_profile
        ).select_related(
            'order__user',
            'product__category',
            'variant'
        ).prefetch_related(
            'product__images'
        ).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def update_status(self, request, pk=None):
        """Update order item status with proper inventory handling."""
        item = self.get_object()
        serializer = UpdateOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        old_status = item.status
        
        # Validate status transition
        valid_transitions = {
            'pending': ['confirmed', 'cancelled'],
            'confirmed': ['processing', 'cancelled'],
            'processing': ['shipped', 'cancelled'],
            'shipped': ['delivered'],
            'delivered': [],
            'cancelled': [],
        }
        
        if new_status not in valid_transitions.get(item.status, []):
            return Response(
                {'error': f'Cannot change status from {item.status} to {new_status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Handle inventory changes based on status transition
        self._handle_inventory_for_status_change(item, old_status, new_status, request.user)
        
        item.status = new_status
        item.save()
        
        # Create status history for order
        OrderStatusHistory.objects.create(
            order=item.order,
            status=f"Item {item.product_name}: {new_status}",
            note=serializer.validated_data.get('note', ''),
            created_by=request.user
        )
        
        # Create vendor balance when item is delivered
        if new_status == 'delivered':
            self._create_vendor_balance(item)
        
        return Response(VendorOrderItemSerializer(item).data)
    
    def _handle_inventory_for_status_change(self, item, old_status, new_status, user):
        """
        Handle inventory updates when order item status changes.
        
        Flow:
        - pending -> confirmed/processing: No change (still reserved)
        - processing -> shipped: Deduct from quantity, release from reserved
        - any -> cancelled: Release from reserved (return to available)
        """
        # Get inventory
        if item.variant:
            inventory = Inventory.objects.filter(variant=item.variant).select_for_update().first()
        else:
            inventory = Inventory.objects.filter(product=item.product).select_for_update().first()
        
        if not inventory:
            return
        
        if new_status == 'shipped' and old_status in ['confirmed', 'processing']:
            # Item is being shipped - deduct from total quantity and release reservation
            Inventory.objects.filter(pk=inventory.pk).update(
                quantity=F('quantity') - item.quantity,
                reserved_quantity=F('reserved_quantity') - item.quantity
            )
            
            # Log inventory movement
            InventoryMovement.objects.create(
                inventory=inventory,
                movement_type='out',
                quantity=item.quantity,
                reference_type='order_shipped',
                reference_id=str(item.order.id),
                note=f'Shipped for order {item.order.order_number}',
                created_by=user
            )
        
        elif new_status == 'cancelled' and old_status in ['pending', 'confirmed', 'processing']:
            # Order cancelled - release reserved quantity back to available
            Inventory.objects.filter(pk=inventory.pk).update(
                reserved_quantity=F('reserved_quantity') - item.quantity
            )
            
            # Log inventory movement
            InventoryMovement.objects.create(
                inventory=inventory,
                movement_type='released',
                quantity=item.quantity,
                reference_type='order_cancelled_vendor',
                reference_id=str(item.order.id),
                note=f'Released from cancelled order {item.order.order_number} (vendor)',
                created_by=user
            )
    
    def _create_vendor_balance(self, item):
        """Create vendor balance entry when item is delivered."""
        from apps.vendors.models import VendorBalance
        from django.conf import settings
        
        # Check if balance already exists
        if hasattr(item, 'vendor_balance'):
            return
        
        hold_days = getattr(settings, 'VENDOR_PAYOUT_HOLD_DAYS', 7)
        VendorBalance.create_from_order_item(item, hold_days=hold_days)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get order statistics for vendor."""
        vendor = request.user.vendor_profile
        items = OrderItem.objects.filter(vendor=vendor)
        
        return Response({
            'total_orders': items.values('order').distinct().count(),
            'pending': items.filter(status='pending').count(),
            'processing': items.filter(status='processing').count(),
            'shipped': items.filter(status='shipped').count(),
            'delivered': items.filter(status='delivered').count(),
            'cancelled': items.filter(status='cancelled').count(),
        })