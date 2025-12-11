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
        """Approve vendors and update their user role."""
        for vendor in queryset:
            vendor.status = 'approved'
            vendor.approved_at = timezone.now()
            vendor.save()
            
            # Update user role to vendor when approved
            vendor.user.role = 'vendor'
            vendor.user.save(update_fields=['role'])
        
        self.message_user(request, f"{queryset.count()} vendor(s) approved successfully.")
    approve_vendors.short_description = "Approve selected vendors"
    
    def suspend_vendors(self, request, queryset):
        """Suspend vendors and revert their user role."""
        for vendor in queryset:
            vendor.status = 'suspended'
            vendor.save()
            
            # Revert user role to customer when suspended
            vendor.user.role = 'customer'
            vendor.user.save(update_fields=['role'])
        
        self.message_user(request, f"{queryset.count()} vendor(s) suspended.")
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
