from django.contrib import admin
from .models import Review, ReviewImage, VendorReview


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'rating', 'is_approved', 'is_featured', 'helpful_count', 'created_at')
    list_filter = ('rating', 'is_approved', 'is_featured', 'created_at')
    search_fields = ('user__email', 'product__name', 'comment')
    readonly_fields = ('helpful_count', 'created_at', 'updated_at')
    inlines = [ReviewImageInline]
    
    actions = ['approve_reviews', 'feature_reviews']
    
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
    approve_reviews.short_description = "Approve selected reviews"
    
    def feature_reviews(self, request, queryset):
        queryset.update(is_featured=True)
    feature_reviews.short_description = "Feature selected reviews"


@admin.register(VendorReview)
class VendorReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'vendor', 'rating', 'is_approved', 'created_at')
    list_filter = ('rating', 'is_approved', 'created_at')
    search_fields = ('user__email', 'vendor__shop_name', 'comment')
