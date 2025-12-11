from rest_framework import permissions


class IsVendorOwner(permissions.BasePermission):
    """Permission to check if user is the vendor owner."""
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsApprovedVendor(permissions.BasePermission):
    """Permission to check if user is an approved vendor."""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not hasattr(request.user, 'vendor_profile'):
            return False
        return request.user.vendor_profile.status == 'approved'
