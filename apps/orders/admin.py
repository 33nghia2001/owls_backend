from django.contrib import admin
from .models import Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('total_price', 'commission_amount')


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'user', 'status', 'payment_status',
        'total', 'created_at'
    )
    list_filter = ('status', 'payment_status', 'created_at')
    search_fields = ('order_number', 'user__email', 'shipping_name')
    readonly_fields = ('order_number', 'created_at', 'updated_at')
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    fieldsets = (
        (None, {'fields': ('order_number', 'user', 'status', 'payment_status')}),
        ('Pricing', {'fields': ('subtotal', 'shipping_cost', 'discount_amount', 'tax_amount', 'total')}),
        ('Shipping Address', {'fields': (
            'shipping_name', 'shipping_phone', 'shipping_address',
            'shipping_city', 'shipping_state', 'shipping_country', 'shipping_postal_code'
        )}),
        ('Billing Address', {'fields': (
            'billing_name', 'billing_phone', 'billing_address',
            'billing_city', 'billing_state', 'billing_country', 'billing_postal_code'
        ), 'classes': ('collapse',)}),
        ('Additional Info', {'fields': ('coupon', 'customer_note', 'admin_note')}),
        ('Timestamps', {'fields': (
            'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at', 'cancelled_at'
        ), 'classes': ('collapse',)}),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'order', 'vendor', 'product_name', 'quantity',
        'unit_price', 'total_price', 'status'
    )
    list_filter = ('status', 'vendor')
    search_fields = ('order__order_number', 'product_name')
