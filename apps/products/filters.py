import django_filters
from .models import Product


class ProductFilter(django_filters.FilterSet):
    """Filter for products."""
    
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
