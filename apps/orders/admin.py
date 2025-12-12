from django.contrib import admin
from .models import Order, OrderItem, OrderStatusHistory, SubOrder, SubOrderStatusHistory, RefundRequest


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('total_price', 'commission_amount')


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('created_at',)


class SubOrderInline(admin.TabularInline):
    model = SubOrder
    extra = 0
    readonly_fields = ('sub_order_number', 'subtotal', 'total', 'commission_amount', 'created_at')
    fields = ('sub_order_number', 'vendor', 'status', 'subtotal', 'shipping_cost', 'total', 'tracking_number')


class SubOrderStatusHistoryInline(admin.TabularInline):
    model = SubOrderStatusHistory
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
    inlines = [OrderItemInline, SubOrderInline, OrderStatusHistoryInline]
    
    fieldsets = (
        (None, {'fields': ('order_number', 'user', 'status', 'payment_status')}),
        ('Pricing', {'fields': ('subtotal', 'shipping_cost', 'discount_amount', 'tax_amount', 'total')}),
        ('Shipping Address', {'fields': (
            'shipping_name', 'shipping_phone', 'shipping_address',
            'shipping_province', 'shipping_ward', 'shipping_country', 'shipping_postal_code'
        )}),
        ('Billing Address', {'fields': (
            'billing_name', 'billing_phone', 'billing_address',
            'billing_province', 'billing_ward', 'billing_country', 'billing_postal_code'
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


@admin.register(SubOrder)
class SubOrderAdmin(admin.ModelAdmin):
    list_display = (
        'sub_order_number', 'order', 'vendor', 'status',
        'subtotal', 'shipping_cost', 'total', 'created_at'
    )
    list_filter = ('status', 'vendor', 'created_at')
    search_fields = ('sub_order_number', 'order__order_number', 'vendor__business_name')
    readonly_fields = ('sub_order_number', 'subtotal', 'total', 'commission_amount', 'created_at', 'updated_at')
    inlines = [SubOrderStatusHistoryInline]
    
    fieldsets = (
        (None, {'fields': ('sub_order_number', 'order', 'vendor', 'status')}),
        ('Pricing', {'fields': ('subtotal', 'shipping_cost', 'total', 'commission_rate', 'commission_amount')}),
        ('Shipping', {'fields': ('shipping_method', 'tracking_number', 'carrier_name')}),
        ('Notes', {'fields': ('vendor_note',)}),
        ('Timestamps', {'fields': (
            'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at', 'cancelled_at'
        ), 'classes': ('collapse',)}),
    )


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'order', 'reason', 'status', 'requested_amount', 
        'approved_amount', 'created_at', 'reviewed_at'
    )
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('order__order_number', 'description')
    readonly_fields = (
        'order', 'item', 'requested_amount', 'created_at', 'updated_at',
        'refund_transaction_id', 'refunded_at'
    )
    raw_id_fields = ('reviewed_by',)
    
    fieldsets = (
        (None, {'fields': ('order', 'item', 'reason', 'description')}),
        ('Amount', {'fields': ('requested_amount', 'approved_amount')}),
        ('Status', {'fields': ('status',)}),
        ('Evidence', {'fields': ('evidence_images',)}),
        ('Review', {'fields': ('reviewed_by', 'review_note', 'reviewed_at')}),
        ('Refund Info', {'fields': ('refund_transaction_id', 'refunded_at'), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def has_add_permission(self, request):
        # Refund requests should be created by users, not in admin
        return False