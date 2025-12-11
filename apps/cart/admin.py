from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('unit_price', 'total_price')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'total_items', 'subtotal', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'session_key')
    inlines = [CartItemInline]
    readonly_fields = ('total_items', 'subtotal')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'variant', 'quantity', 'unit_price', 'total_price')
    list_filter = ('created_at',)
    search_fields = ('product__name',)
