from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F

from .models import (
    Category, Brand, Product, ProductImage, ProductAttribute,
    ProductAttributeValue, ProductVariant, ProductTag
)
from .serializers import (
    CategorySerializer, CategoryTreeSerializer, BrandSerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateUpdateSerializer,
    ProductImageSerializer, ProductAttributeSerializer, ProductVariantSerializer,
    ProductTagSerializer
)
from .filters import ProductFilter
from apps.vendors.permissions import IsApprovedVendor


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for product categories."""
    queryset = Category.objects.filter(is_active=True)
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_serializer_class(self):
        if self.action == 'tree':
            return CategoryTreeSerializer
        return CategorySerializer
    
    def get_queryset(self):
        if self.action == 'list':
            # Return only root categories
            return Category.objects.filter(is_active=True, parent=None)
        return Category.objects.filter(is_active=True)
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get all categories as flat list with full paths."""
        categories = Category.objects.filter(is_active=True)
        serializer = CategoryTreeSerializer(categories, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def products(self, request, slug=None):
        """Get products in category including subcategories."""
        category = self.get_object()
        descendants = category.get_descendants(include_self=True)
        products = Product.objects.filter(
            category__in=descendants,
            status='published'
        )
        
        # Apply filters
        filterset = ProductFilter(request.GET, queryset=products)
        serializer = ProductListSerializer(filterset.qs[:20], many=True)
        return Response(serializer.data)


class BrandViewSet(viewsets.ModelViewSet):
    """ViewSet for brands."""
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for products."""
    queryset = Product.objects.select_related('vendor', 'category', 'brand').prefetch_related('images')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['price', 'created_at', 'sold_count', 'rating']
    lookup_field = 'slug'
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'my_products']:
            return [IsAuthenticated(), IsApprovedVendor()]
        return [AllowAny()]
    
    def get_queryset(self):
        queryset = Product.objects.select_related('vendor', 'category', 'brand').prefetch_related('images')
        
        # Public read actions - show only published products
        if self.action in ['list', 'retrieve', 'featured', 'best_sellers', 'new_arrivals']:
            return queryset.filter(status='published')
        
        # Vendor-specific actions (create, update, delete, my_products, upload_images)
        # Only return products owned by the authenticated vendor to prevent IDOR
        if self.request.user.is_authenticated and hasattr(self.request.user, 'vendor_profile'):
            return queryset.filter(vendor=self.request.user.vendor_profile)
        
        # Default: return empty queryset for safety
        return queryset.none()
    
    def retrieve(self, request, *args, **kwargs):
        """Get product detail and increment view count (once per session/fingerprint)."""
        from .tasks import increment_view_count
        import hashlib
        
        instance = self.get_object()
        product_id = str(instance.pk)
        
        # SECURITY: Prevent DoS via view count spam
        # Generate a unique viewer identifier
        
        if request.session.session_key:
            # Primary: Use session key for browser users
            viewer_id = request.session.session_key
            viewed_products = request.session.get('viewed_products', [])
            
            if product_id not in viewed_products:
                increment_view_count(instance.pk)
                viewed_products.append(product_id)
                # Keep only last 100 viewed products in session
                request.session['viewed_products'] = viewed_products[-100:]
                request.session.modified = True
        else:
            # Fallback: For mobile apps/SPAs without session cookies
            # Use IP + User-Agent + Product ID hash to dedupe
            # Note: This is less accurate than session but prevents simple spam
            from django.core.cache import cache
            
            client_ip = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]  # Limit UA length
            
            # Create a fingerprint hash
            fingerprint = hashlib.sha256(
                f"{client_ip}:{user_agent}:{product_id}".encode()
            ).hexdigest()[:32]
            
            cache_key = f"product_view:{fingerprint}"
            
            # Check if already viewed in last 24 hours
            if not cache.get(cache_key):
                increment_view_count(instance.pk)
                cache.set(cache_key, 1, timeout=86400)  # 24 hours
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def _get_client_ip(self, request):
        """Extract client IP from request, handling proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take first IP if multiple (first is real client)
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    
    @action(detail=False, methods=['get'])
    def my_products(self, request):
        """Get current vendor's products."""
        queryset = self.get_queryset()
        serializer = ProductListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured products."""
        products = Product.objects.filter(
            status='published', 
            is_featured=True
        ).select_related('vendor', 'category').prefetch_related('images')[:12]
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def best_sellers(self, request):
        """Get best selling products."""
        products = Product.objects.filter(
            status='published'
        ).order_by('-sold_count').select_related('vendor', 'category').prefetch_related('images')[:12]
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def new_arrivals(self, request):
        """Get newest products."""
        products = Product.objects.filter(
            status='published'
        ).order_by('-created_at').select_related('vendor', 'category').prefetch_related('images')[:12]
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def upload_images(self, request, slug=None):
        """Upload additional images to product."""
        product = self.get_object()
        
        if product.vendor != request.user.vendor_profile:
            return Response(
                {'error': 'You can only upload images to your own products.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        images = request.FILES.getlist('images')
        if not images:
            return Response(
                {'error': 'No images provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_images = []
        max_order = product.images.count()
        
        for i, image in enumerate(images):
            img = ProductImage.objects.create(
                product=product,
                image=image,
                order=max_order + i
            )
            created_images.append(img)
        
        serializer = ProductImageSerializer(created_images, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProductImageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product images."""
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    
    def get_queryset(self):
        return ProductImage.objects.filter(
            product__vendor=self.request.user.vendor_profile
        )
    
    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Set image as primary."""
        image = self.get_object()
        image.is_primary = True
        image.save()
        return Response(ProductImageSerializer(image).data)


class ProductAttributeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for product attributes (read-only)."""
    queryset = ProductAttribute.objects.prefetch_related('values')
    serializer_class = ProductAttributeSerializer
    permission_classes = [AllowAny]


class ProductTagViewSet(viewsets.ModelViewSet):
    """ViewSet for product tags."""
    queryset = ProductTag.objects.all()
    serializer_class = ProductTagSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']
    
    def get_permissions(self):
        """
        - list, retrieve: Allow anyone to browse tags
        - create, update, destroy: Only approved vendors can manage tags
        """
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated(), IsApprovedVendor()]
