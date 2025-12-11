from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404

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
                existing.quantity += item.quantity
                existing.save()
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
            existing_item.quantity += serializer.validated_data['quantity']
            existing_item.save()
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
    
    @action(detail=False, methods=['put'], url_path='items/(?P<item_id>[^/.]+)')
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
