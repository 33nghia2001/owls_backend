from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Users, Address


@admin.register(Users)
class CustomUserAdmin(UserAdmin):
    model = Users
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_active', 'is_verified', 'date_joined')
    list_filter = ('role', 'is_active', 'is_verified', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'username', 'phone', 'avatar')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'is_verified', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'role'),
        }),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'city', 'address_type', 'is_default')
    list_filter = ('address_type', 'is_default', 'country')
    search_fields = ('full_name', 'street_address', 'city')
