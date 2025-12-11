from django.contrib import admin
from django.utils import timezone
from .models import Vendor, VendorBankAccount, VendorPayout


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('shop_name', 'user', 'status', 'rating', 'total_sales', 'is_featured', 'created_at')
    list_filter = ('status', 'is_featured', 'country')
    search_fields = ('shop_name', 'user__email', 'business_email')
    prepopulated_fields = {'slug': ('shop_name',)}
    readonly_fields = ('rating', 'total_sales', 'total_products', 'created_at', 'updated_at')
    
    actions = ['approve_vendors', 'suspend_vendors']
    
    def approve_vendors(self, request, queryset):
        queryset.update(status='approved', approved_at=timezone.now())
    approve_vendors.short_description = "Approve selected vendors"
    
    def suspend_vendors(self, request, queryset):
        queryset.update(status='suspended')
    suspend_vendors.short_description = "Suspend selected vendors"


@admin.register(VendorBankAccount)
class VendorBankAccountAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'bank_name', 'account_name', 'is_primary')
    list_filter = ('is_primary', 'bank_name')
    search_fields = ('vendor__shop_name', 'account_name')


@admin.register(VendorPayout)
class VendorPayoutAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'amount', 'net_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('vendor__shop_name', 'reference_id')
    readonly_fields = ('created_at',)
