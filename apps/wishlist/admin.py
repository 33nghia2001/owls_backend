from django.contrib import admin
from .models import Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'is_public', 'created_at')
    list_filter = ('is_public', 'created_at')
    search_fields = ('user__email', 'name')
    inlines = [WishlistItemInline]


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('wishlist', 'product', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('product__name',)
