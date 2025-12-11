from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Wishlist, WishlistItem
from .serializers import WishlistSerializer, WishlistItemSerializer
from apps.products.models import Product


class WishlistViewSet(viewsets.ModelViewSet):
    """ViewSet for wishlists."""
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).prefetch_related('items__product')
    
    @action(detail=False, methods=['get', 'post'])
    def default(self, request):
        """Get or create default wishlist."""
        wishlist, created = Wishlist.objects.get_or_create(
            user=request.user,
            defaults={'name': 'My Wishlist'}
        )
        
        if request.method == 'POST':
            # Add product to default wishlist
            product_id = request.data.get('product_id')
            if not product_id:
                return Response(
                    {'error': 'Product ID required.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            product = get_object_or_404(Product, id=product_id)
            
            item, created = WishlistItem.objects.get_or_create(
                wishlist=wishlist,
                product=product,
                defaults={'note': request.data.get('note', '')}
            )
            
            if not created:
                return Response(
                    {'message': 'Product already in wishlist.'},
                    status=status.HTTP_200_OK
                )
            
            return Response(
                WishlistItemSerializer(item).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(WishlistSerializer(wishlist).data)
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """Add item to wishlist."""
        wishlist = self.get_object()
        
        product_id = request.data.get('product_id')
        if not product_id:
            return Response(
                {'error': 'Product ID required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        product = get_object_or_404(Product, id=product_id)
        
        item, created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            product=product,
            defaults={'note': request.data.get('note', '')}
        )
        
        return Response(
            WishlistSerializer(wishlist).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['delete'], url_path='items/(?P<item_id>[^/.]+)')
    def remove_item(self, request, pk=None, item_id=None):
        """Remove item from wishlist."""
        wishlist = self.get_object()
        item = get_object_or_404(WishlistItem, id=item_id, wishlist=wishlist)
        item.delete()
        return Response(WishlistSerializer(wishlist).data)
    
    @action(detail=False, methods=['delete'], url_path='product/(?P<product_id>[^/.]+)')
    def remove_product(self, request, product_id=None):
        """Remove product from all wishlists."""
        WishlistItem.objects.filter(
            wishlist__user=request.user,
            product_id=product_id
        ).delete()
        return Response({'message': 'Product removed from wishlists.'})
    
    @action(detail=False, methods=['get'])
    def check(self, request):
        """Check if product is in any wishlist."""
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({'error': 'Product ID required.'}, status=400)
        
        exists = WishlistItem.objects.filter(
            wishlist__user=request.user,
            product_id=product_id
        ).exists()
        
        return Response({'in_wishlist': exists})
