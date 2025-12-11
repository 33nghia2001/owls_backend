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
    
    def get_cart(self, request):
        """Get or create cart for user or session."""
        if request.user.is_authenticated:
            cart, created = Cart.objects.prefetch_related(
                'items__product__vendor',
                'items__product__images',
                'items__variant'
            ).get_or_create(user=request.user)
            # Merge session cart if exists
            session_key = request.session.session_key
            if session_key:
                try:
                    session_cart = Cart.objects.get(session_key=session_key, user__isnull=True)
                    # Merge items
                    for item in session_cart.items.select_related('product', 'variant').all():
                        existing = cart.items.filter(
                            product=item.product, 
                            variant=item.variant
                        ).first()
                        if existing:
                            existing.quantity += item.quantity
                            existing.save()
                        else:
                            item.cart = cart
                            item.save()
                    session_cart.delete()
                except Cart.DoesNotExist:
                    pass
        else:
            if not request.session.session_key:
                request.session.create()
            cart, created = Cart.objects.prefetch_related(
                'items__product__vendor',
                'items__product__images',
                'items__variant'
            ).get_or_create(
                session_key=request.session.session_key,
                user__isnull=True
            )
        return cart
    
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
