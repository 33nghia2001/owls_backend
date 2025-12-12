from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import F

from .models import Cart, CartItem
from .serializers import (
    CartSerializer, CartItemSerializer, AddToCartSerializer, UpdateCartItemSerializer
)
from apps.products.models import Product, ProductVariant


class CartViewSet(viewsets.ViewSet):
    """ViewSet for shopping cart operations."""
    permission_classes = [AllowAny]
    
    def _get_guest_cart_id(self, request):
        """Extract guest_cart_id from request params or body."""
        # Check query params first, then body
        guest_cart_id = request.query_params.get('guest_cart_id')
        if not guest_cart_id and hasattr(request, 'data'):
            guest_cart_id = request.data.get('guest_cart_id')
        return guest_cart_id
    
    def get_cart(self, request, merge_guest_cart_id=None):
        """
        Get or create cart for user or session.
        
        For authenticated users: Returns user's cart, merges guest cart if provided.
        For guests: Uses guest_cart_id from frontend if available, 
                   falls back to session_key.
        """
        guest_cart_id = merge_guest_cart_id or self._get_guest_cart_id(request)
        
        if request.user.is_authenticated:
            cart, created = Cart.objects.prefetch_related(
                'items__product__vendor',
                'items__product__images',
                'items__variant'
            ).get_or_create(user=request.user)
            
            # Try to merge guest cart if guest_cart_id provided
            if guest_cart_id:
                try:
                    guest_cart = Cart.objects.get(session_key=guest_cart_id, user__isnull=True)
                    self._merge_carts(guest_cart, cart)
                except Cart.DoesNotExist:
                    pass
            
            # Also check session-based cart (cookie)
            session_key = request.session.session_key
            if session_key:
                try:
                    session_cart = Cart.objects.get(session_key=session_key, user__isnull=True)
                    self._merge_carts(session_cart, cart)
                except Cart.DoesNotExist:
                    pass
        else:
            # Guest user - prefer frontend's guest_cart_id, fallback to session
            cart_session_key = guest_cart_id
            
            if not cart_session_key:
                if not request.session.session_key:
                    request.session.create()
                cart_session_key = request.session.session_key
            
            cart, created = Cart.objects.prefetch_related(
                'items__product__vendor',
                'items__product__images',
                'items__variant'
            ).get_or_create(
                session_key=cart_session_key,
                user__isnull=True
            )
        return cart
    
    def _merge_carts(self, source_cart, target_cart):
        """Merge items from source cart into target cart, then delete source."""
        for item in source_cart.items.select_related('product', 'variant').all():
            existing = target_cart.items.filter(
                product=item.product, 
                variant=item.variant
            ).first()
            if existing:
                # Use F() expression to avoid race condition
                existing.quantity = F('quantity') + item.quantity
                existing.save(update_fields=['quantity'])
                existing.refresh_from_db()
            else:
                item.cart = target_cart
                item.save()
        source_cart.delete()
    
    def list(self, request):
        """Get current cart."""
        cart = self.get_cart(request)
        serializer = CartSerializer(cart)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def add(self, request):
        """Add item to cart."""
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        cart = self.get_cart(request)
        product = get_object_or_404(Product, id=serializer.validated_data['product_id'])
        
        variant = None
        variant_id = serializer.validated_data.get('variant_id')
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
        
        # Check if item already exists
        existing_item = cart.items.filter(product=product, variant=variant).first()
        
        if existing_item:
            # Use F() expression to avoid race condition when spam clicking
            existing_item.quantity = F('quantity') + serializer.validated_data['quantity']
            existing_item.save(update_fields=['quantity'])
            existing_item.refresh_from_db()  # Refresh to get actual value after F() expression
            item = existing_item
        else:
            # Get price
            if variant and variant.price:
                unit_price = variant.price
            else:
                unit_price = product.price
            
            item = CartItem.objects.create(
                cart=cart,
                product=product,
                variant=variant,
                quantity=serializer.validated_data['quantity'],
                unit_price=unit_price
            )
        
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['patch', 'put'], url_path='items/(?P<item_id>[^/.]+)')
    def update_item(self, request, item_id=None):
        """Update cart item quantity."""
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        cart = self.get_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        
        quantity = serializer.validated_data['quantity']
        if quantity == 0:
            item.delete()
        else:
            item.quantity = quantity
            item.save()
        
        return Response(CartSerializer(cart).data)
    
    @action(detail=False, methods=['delete'], url_path='items/(?P<item_id>[^/.]+)')
    def remove_item(self, request, item_id=None):
        """Remove item from cart."""
        cart = self.get_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()
        return Response(CartSerializer(cart).data)
    
    @action(detail=False, methods=['delete'])
    def clear(self, request):
        """Clear all items from cart."""
        cart = self.get_cart(request)
        cart.clear()
        return Response(CartSerializer(cart).data)
    
    @action(detail=False, methods=['post'])
    def apply_coupon(self, request):
        """Apply a coupon code to the cart."""
        from apps.coupons.models import Coupon
        from django.utils import timezone
        
        code = request.data.get('code')
        if not code:
            return Response(
                {'error': 'Mã giảm giá không được để trống'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cart = self.get_cart(request)
        
        try:
            coupon = Coupon.objects.get(
                code__iexact=code,
                is_active=True,
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now()
            )
            
            # Check usage limits
            if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
                return Response(
                    {'error': 'Mã giảm giá đã hết lượt sử dụng'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check minimum order amount
            if coupon.min_order_amount and cart.subtotal < coupon.min_order_amount.amount:
                return Response(
                    {'error': f'Đơn hàng tối thiểu {coupon.min_order_amount} để áp dụng mã này'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Calculate discount
            discount_amount = 0
            if coupon.discount_type == 'percentage':
                discount_amount = cart.subtotal * (coupon.discount_value / 100)
                if coupon.max_discount_amount:
                    discount_amount = min(discount_amount, coupon.max_discount_amount.amount)
            elif coupon.discount_type == 'fixed':
                discount_amount = coupon.discount_value
            
            # Return cart with coupon info
            cart_data = CartSerializer(cart).data
            cart_data['coupon'] = {
                'code': coupon.code,
                'discount_type': coupon.discount_type,
                'discount_value': str(coupon.discount_value),
                'discount_amount': str(discount_amount),
            }
            cart_data['discount_amount'] = str(discount_amount)
            
            return Response(cart_data)
            
        except Coupon.DoesNotExist:
            return Response(
                {'error': 'Mã giảm giá không hợp lệ hoặc đã hết hạn'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def remove_coupon(self, request):
        """Remove applied coupon from cart."""
        cart = self.get_cart(request)
        cart_data = CartSerializer(cart).data
        cart_data['coupon'] = None
        cart_data['discount_amount'] = '0'
        return Response(cart_data)
