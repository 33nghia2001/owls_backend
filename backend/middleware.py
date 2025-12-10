"""
Custom Middleware for Django Application
"""
from django.http import HttpResponseForbidden
from django.conf import settings
import os


class AdminIPWhitelistMiddleware:
    """
    Middleware to restrict admin access to whitelisted IPs only.
    Prevents unauthorized access to Django admin panel.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Get whitelisted IPs from environment variable
        whitelist = os.environ.get('ADMIN_IP_WHITELIST', '')
        self.allowed_ips = [ip.strip() for ip in whitelist.split(',') if ip.strip()]

    def __call__(self, request):
        # Check if accessing admin URL
        if request.path.startswith('/quan-tri-vien-secure-8899/'):
            # Skip in DEBUG mode or if no whitelist configured
            if settings.DEBUG and not self.allowed_ips:
                return self.get_response(request)
            
            # Get client IP
            client_ip = self.get_client_ip(request)
            
            # Block if IP not in whitelist
            if self.allowed_ips and client_ip not in self.allowed_ips:
                return HttpResponseForbidden(
                    '<h1>403 Forbidden</h1><p>Your IP address is not authorized to access this page.</p>'
                )
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        """
        Get real client IP, considering proxy headers.
        """
        # Try to get IP from X-Forwarded-For (if behind proxy)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP (client IP)
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            # Fallback to REMOTE_ADDR
            ip = request.META.get('REMOTE_ADDR')
        return ip
