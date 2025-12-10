"""
Custom Middleware for Django Application
"""
from django.http import HttpResponseForbidden
from django.conf import settings
from ipware import get_client_ip
import os


class AdminIPWhitelistMiddleware:
    """
    Middleware to restrict admin access to whitelisted IPs only.
    Prevents unauthorized access to Django admin panel.
    Uses django-ipware to get real client IP (防止IP欺骗).
    
    CRITICAL SECURITY:
    - MUST configure IPWARE_TRUSTED_PROXY_LIST in production
    - Without proper proxy config, X-Forwarded-For can be spoofed
    - Example: IPWARE_TRUSTED_PROXY_LIST=173.245.48.0/20,103.21.244.0/22 (Cloudflare)
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Get whitelisted IPs from environment variable
        whitelist = os.environ.get('ADMIN_IP_WHITELIST', '')
        self.allowed_ips = [ip.strip() for ip in whitelist.split(',') if ip.strip()]
        
        # CRITICAL SECURITY: FORCE proper proxy configuration in production
        if not settings.DEBUG:
            trusted_proxies = getattr(settings, 'IPWARE_META_PRECEDENCE_ORDER', None)
            if not trusted_proxies:
                # HARD FAIL: Don't allow application to start without proper security config
                raise RuntimeError(
                    "CRITICAL SECURITY ERROR: IPWARE_TRUSTED_PROXY_LIST not configured in production!\n"
                    "IP-based access control can be bypassed via X-Forwarded-For spoofing.\n"
                    "This is a Remote Code Execution (RCE) vector allowing admin panel takeover.\n\n"
                    "REQUIRED ACTION:\n"
                    "Set IPWARE_TRUSTED_PROXY_LIST in .env with your Load Balancer/CDN IP ranges:\n"
                    "  - Cloudflare: IPWARE_TRUSTED_PROXY_LIST=173.245.48.0/20,103.21.244.0/22\n"
                    "  - AWS ALB: IPWARE_TRUSTED_PROXY_LIST=10.0.0.0/8,172.16.0.0/12\n"
                    "  - Nginx: IPWARE_TRUSTED_PROXY_LIST=<your_nginx_server_ip>\n\n"
                    "Application startup aborted for security."
                )

    def __call__(self, request):
        # Check if accessing admin URL
        if request.path.startswith('/quan-tri-vien-secure-8899/'):
            # Skip in DEBUG mode or if no whitelist configured
            if settings.DEBUG and not self.allowed_ips:
                return self.get_response(request)
            
            # Get real client IP using django-ipware 
            client_ip, is_routable = get_client_ip(request)
            
            # Block if IP not in whitelist
            if self.allowed_ips and client_ip not in self.allowed_ips:
                return HttpResponseForbidden(
                    '<h1>403 Forbidden</h1><p>Your IP address is not authorized to access this page.</p>'
                )
        
        return self.get_response(request)
