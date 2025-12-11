from django.contrib import admin
from django.utils.html import format_html
from mptt.admin import DraggableMPTTAdmin
from .models import (
    Category, Brand, Product, ProductImage, ProductAttribute,
    ProductAttributeValue, ProductVariant, ProductVariantAttribute, ProductTag
)


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    list_display = ('tree_actions', 'indented_title', 'slug', 'is_active', 'order')
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    readonly_fields = ('sku',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'category', 'price', 'status', 'is_featured', 'rating', 'sold_count')
    list_filter = ('status', 'is_featured', 'category', 'vendor')
    search_fields = ('name', 'sku', 'vendor__shop_name')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('rating', 'review_count', 'sold_count', 'view_count', 'created_at', 'updated_at')
    inlines = [ProductImageInline, ProductVariantInline]
    
    fieldsets = (
        (None, {'fields': ('vendor', 'name', 'slug', 'sku', 'category', 'brand')}),
        ('Description', {'fields': ('short_description', 'description')}),
        ('Pricing', {'fields': ('price', 'compare_price', 'cost_price')}),
        ('Status', {'fields': ('status', 'is_featured', 'is_digital')}),
        ('SEO', {'fields': ('meta_title', 'meta_description'), 'classes': ('collapse',)}),
        ('Metrics', {'fields': ('rating', 'review_count', 'sold_count', 'view_count'), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at', 'published_at'), 'classes': ('collapse',)}),
    )


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(admin.ModelAdmin):
    list_display = ('attribute', 'value', 'color_preview')
    list_filter = ('attribute',)
    
    def color_preview(self, obj):
        if obj.color_code:
            return format_html(
                '<span style="background-color: {}; padding: 5px 15px; border-radius: 3px;">&nbsp;</span>',
                obj.color_code
            )
        return '-'
    color_preview.short_description = 'Color'


@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
