from django.contrib import admin
from .models import ProductView, SearchQuery, VendorStats, PlatformStats


@admin.register(ProductView)
class ProductViewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'ip_address', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('product__name', 'user__email')


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ('query', 'results_count', 'user', 'searched_at')
    list_filter = ('searched_at',)
    search_fields = ('query',)


@admin.register(VendorStats)
class VendorStatsAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'date', 'orders_count', 'orders_revenue', 'products_sold')
    list_filter = ('date', 'vendor')
    date_hierarchy = 'date'


@admin.register(PlatformStats)
class PlatformStatsAdmin(admin.ModelAdmin):
    list_display = ('date', 'new_users', 'orders_count', 'orders_revenue')
    list_filter = ('date',)
    date_hierarchy = 'date'
