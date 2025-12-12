import django_filters
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import F
from .models import Product


class ProductFilter(django_filters.FilterSet):
    """
    Filter for products with PostgreSQL Full-Text Search support.
    
    The 'q' parameter uses SearchVector for efficient full-text search,
    falling back to icontains for simple queries.
    """
    
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    category = django_filters.UUIDFilter(field_name='category__id')
    category_slug = django_filters.CharFilter(field_name='category__slug')
    brand = django_filters.UUIDFilter(field_name='brand__id')
    brand_slug = django_filters.CharFilter(field_name='brand__slug')
    vendor = django_filters.UUIDFilter(field_name='vendor__id')
    vendor_slug = django_filters.CharFilter(field_name='vendor__slug')
    is_featured = django_filters.BooleanFilter()
    is_on_sale = django_filters.BooleanFilter(method='filter_on_sale')
    min_rating = django_filters.NumberFilter(field_name='rating', lookup_expr='gte')
    
    # Full-text search parameter
    q = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Product
        fields = [
            'category', 'category_slug', 'brand', 'brand_slug',
            'vendor', 'vendor_slug', 'is_featured', 'status'
        ]
    
    def filter_on_sale(self, queryset, name, value):
        if value:
            return queryset.filter(compare_price__isnull=False).exclude(compare_price=0)
        return queryset
    
    def filter_search(self, queryset, name, value):
        """
        Full-text search using PostgreSQL SearchVector.
        
        Uses pre-computed search_vector if available,
        otherwise falls back to dynamic SearchVector on name + description.
        This is MUCH faster than icontains for large datasets.
        
        Search ranking prioritizes:
        - Name matches (weight A)
        - Description matches (weight B)
        - SKU exact matches (weight A)
        """
        if not value or len(value) < 2:
            return queryset
        
        # Clean and prepare search query
        search_term = value.strip()
        
        # Try PostgreSQL Full-Text Search first
        try:
            # Create search query - supports Vietnamese through unaccent
            # Use 'simple' config for better Vietnamese support
            search_query = SearchQuery(search_term, config='simple')
            
            # Check if search_vector is populated
            if queryset.filter(search_vector__isnull=False).exists():
                # Use pre-computed search vector (fastest)
                return queryset.filter(
                    search_vector=search_query
                ).annotate(
                    search_rank=SearchRank(F('search_vector'), search_query)
                ).order_by('-search_rank', '-sold_count')
            else:
                # Fallback: compute SearchVector dynamically
                # Still faster than icontains for large datasets
                search_vector = SearchVector('name', weight='A') + \
                               SearchVector('description', weight='B') + \
                               SearchVector('sku', weight='A')
                
                return queryset.annotate(
                    search_vector=search_vector,
                    search_rank=SearchRank(search_vector, search_query)
                ).filter(
                    search_vector=search_query
                ).order_by('-search_rank', '-sold_count')
                
        except Exception:
            # Final fallback: simple icontains (works without PostgreSQL)
            return queryset.filter(
                models.Q(name__icontains=search_term) |
                models.Q(description__icontains=search_term) |
                models.Q(sku__icontains=search_term)
            )


# Import models for Q lookup in fallback
from django.db import models
