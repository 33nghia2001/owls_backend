from django.contrib import admin
from .models import Review, ReviewHelpful, InstructorReply, ReportReview


class InstructorReplyInline(admin.StackedInline):
    model = InstructorReply
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'rating', 'is_approved', 'is_featured', 'helpful_count', 'created_at']
    list_filter = ['rating', 'is_approved', 'is_featured', 'created_at']
    search_fields = ['user__username', 'course__title', 'title', 'comment']
    readonly_fields = ['helpful_count', 'not_helpful_count', 'created_at', 'updated_at']
    inlines = [InstructorReplyInline]
    
    fieldsets = (
        ('Review Info', {
            'fields': ('course', 'user', 'rating')
        }),
        ('Content', {
            'fields': ('title', 'comment')
        }),
        ('Engagement', {
            'fields': ('helpful_count', 'not_helpful_count')
        }),
        ('Status', {
            'fields': ('is_approved', 'is_featured')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ['review', 'user', 'is_helpful', 'created_at']
    list_filter = ['is_helpful', 'created_at']
    search_fields = ['review__course__title', 'user__username']


@admin.register(InstructorReply)
class InstructorReplyAdmin(admin.ModelAdmin):
    list_display = ['review', 'instructor', 'created_at', 'updated_at']
    search_fields = ['review__course__title', 'instructor__username', 'reply_text']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ReportReview)
class ReportReviewAdmin(admin.ModelAdmin):
    list_display = ['review', 'reported_by', 'reason', 'status', 'reported_at', 'resolved_at']
    list_filter = ['reason', 'status', 'reported_at']
    search_fields = ['review__course__title', 'reported_by__username', 'description']
    readonly_fields = ['reported_at', 'resolved_at']
