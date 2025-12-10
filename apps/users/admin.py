from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, InstructorProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('role', 'bio', 'avatar', 'phone', 'date_of_birth')
        }),
        ('Social Links', {
            'fields': ('website', 'linkedin', 'github')
        }),
        ('Settings', {
            'fields': ('email_notifications', 'marketing_emails')
        }),
    )


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'experience_years', 'total_courses', 'average_rating', 'is_verified']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['user__username', 'user__email', 'title']
