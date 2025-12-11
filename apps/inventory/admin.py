from django.contrib import admin
from .models import Inventory, InventoryMovement


class InventoryMovementInline(admin.TabularInline):
    model = InventoryMovement
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'variant', 'quantity', 'reserved_quantity',
        'available_quantity', 'is_low_stock', 'warehouse_location'
    )
    list_filter = ('updated_at',)
    search_fields = ('product__name', 'variant__product__name')
    inlines = [InventoryMovementInline]


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ('inventory', 'movement_type', 'quantity', 'created_by', 'created_at')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('inventory__product__name', 'reference_id')
