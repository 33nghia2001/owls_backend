from django.contrib import admin
from .models import Coupon, CouponUsage


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'used_count', 'is_active', 'end_date')
    list_filter = ('discount_type', 'is_active', 'is_public')
    search_fields = ('code', 'description')
    filter_horizontal = ('categories', 'products', 'eligible_users')
    readonly_fields = ('used_count', 'created_at', 'updated_at')


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'user', 'order', 'discount_applied', 'used_at')
    list_filter = ('used_at',)
    search_fields = ('coupon__code', 'user__email')
