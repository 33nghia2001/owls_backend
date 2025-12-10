from django.contrib import admin
from .models import Notification, NotificationPreference, Announcement, AnnouncementView


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'notification_type', 'title', 'is_read', 'email_sent', 'created_at']
    list_filter = ['notification_type', 'is_read', 'email_sent', 'created_at']
    search_fields = ['recipient__username', 'title', 'message']
    readonly_fields = ['created_at', 'read_at', 'email_sent_at']
    
    fieldsets = (
        ('Recipient', {
            'fields': ('recipient',)
        }),
        ('Content', {
            'fields': ('notification_type', 'title', 'message', 'action_url')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'email_sent', 'email_sent_at')
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id')
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'email_enrollment', 'push_enrollment', 'daily_digest', 'weekly_digest']
    search_fields = ['user__username', 'user__email']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Email Notifications', {
            'fields': (
                'email_enrollment', 'email_course_updates', 'email_new_lessons',
                'email_assignments', 'email_reviews', 'email_messages',
                'email_announcements', 'email_marketing'
            )
        }),
        ('Push Notifications', {
            'fields': (
                'push_enrollment', 'push_course_updates', 'push_new_lessons',
                'push_assignments', 'push_reviews', 'push_messages'
            )
        }),
        ('Digest', {
            'fields': ('daily_digest', 'weekly_digest')
        }),
    )


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'announcement_type', 'priority', 'is_active', 'view_count', 'published_at', 'expires_at']
    list_filter = ['announcement_type', 'priority', 'is_active', 'published_at']
    search_fields = ['title', 'content']
    filter_horizontal = ['target_users', 'target_courses']
    readonly_fields = ['view_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'content')
        }),
        ('Settings', {
            'fields': ('announcement_type', 'priority', 'is_active')
        }),
        ('Target Audience', {
            'fields': ('target_users', 'target_courses')
        }),
        ('Publishing', {
            'fields': ('created_by', 'published_at', 'expires_at')
        }),
        ('Stats', {
            'fields': ('view_count',)
        }),
    )


@admin.register(AnnouncementView)
class AnnouncementViewAdmin(admin.ModelAdmin):
    list_display = ['announcement', 'user', 'viewed_at']
    list_filter = ['viewed_at']
    search_fields = ['announcement__title', 'user__username']
