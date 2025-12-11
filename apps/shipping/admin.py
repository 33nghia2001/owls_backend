from django.contrib import admin
from .models import ShippingMethod, ShippingZone, ShippingRate, Shipment, ShipmentTracking


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'base_cost', 'min_days', 'max_days', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')


@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = ('zone', 'method', 'cost')
    list_filter = ('zone', 'method')


class ShipmentTrackingInline(admin.TabularInline):
    model = ShipmentTracking
    extra = 0


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('order', 'tracking_number', 'carrier', 'status', 'created_at')
    list_filter = ('status', 'carrier')
    search_fields = ('order__order_number', 'tracking_number')
    inlines = [ShipmentTrackingInline]
