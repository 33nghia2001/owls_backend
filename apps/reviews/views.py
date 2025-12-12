from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F

from .models import Review, ReviewHelpful, VendorReview
from .serializers import (
    ReviewSerializer, CreateReviewSerializer,
    VendorReviewSerializer, CreateVendorReviewSerializer
)


class ReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for product reviews."""
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product', 'rating']
    ordering_fields = ['created_at', 'rating', 'helpful_count']
    
    def get_queryset(self):
        queryset = Review.objects.filter(is_approved=True).select_related('user')
        
        # SECURITY: For mutation operations, only allow users to modify their own reviews
        if self.action in ['update', 'partial_update', 'destroy']:
            if self.request.user.is_authenticated:
                queryset = queryset.filter(user=self.request.user)
            else:
                queryset = queryset.none()
        
        # Filter by product if specified
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateReviewSerializer
        return ReviewSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'mark_helpful']:
            return [IsAuthenticated()]
        return [AllowAny()]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=True, methods=['post'])
    def mark_helpful(self, request, pk=None):
        """Mark review as helpful."""
        review = self.get_object()
        user = request.user
        
        helpful, created = ReviewHelpful.objects.get_or_create(
            review=review,
            user=user
        )
        
        if created:
            Review.objects.filter(pk=review.pk).update(helpful_count=F('helpful_count') + 1)
            return Response({'message': 'Marked as helpful.'})
        else:
            helpful.delete()
            Review.objects.filter(pk=review.pk).update(helpful_count=F('helpful_count') - 1)
            return Response({'message': 'Removed helpful mark.'})
    
    @action(detail=False, methods=['get'])
    def my_reviews(self, request):
        """Get current user's reviews."""
        reviews = Review.objects.filter(user=request.user)
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def product_stats(self, request):
        """Get review statistics for a product."""
        product_id = request.query_params.get('product')
        if not product_id:
            return Response(
                {'error': 'Product ID required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reviews = Review.objects.filter(product_id=product_id, is_approved=True)
        
        # Calculate rating distribution
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            distribution[review.rating] += 1
        
        total = reviews.count()
        
        return Response({
            'total_reviews': total,
            'rating_distribution': distribution,
            'average_rating': sum(r * c for r, c in distribution.items()) / total if total else 0
        })


class VendorReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor reviews."""
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['vendor', 'rating']
    ordering_fields = ['created_at', 'rating']
    
    def get_queryset(self):
        queryset = VendorReview.objects.filter(is_approved=True).select_related('user')
        
        # SECURITY: For mutation operations, only allow users to modify their own reviews
        if self.action in ['update', 'partial_update', 'destroy']:
            if self.request.user.is_authenticated:
                queryset = queryset.filter(user=self.request.user)
            else:
                queryset = queryset.none()
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateVendorReviewSerializer
        return VendorReviewSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]
