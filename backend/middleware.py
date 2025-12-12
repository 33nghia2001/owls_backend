"""
Custom middleware for OWLS Marketplace.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class JWTCookieMiddleware:
    """
    Middleware to extract JWT access token from httpOnly cookie
    and add it to the Authorization header for DRF authentication.
    
    This allows using httpOnly cookies for security while maintaining
    compatibility with DRF's token authentication.
    
    CSRF Protection Strategy:
    - SameSite=Lax prevents most cross-site POST attacks
    - Origin header verification for additional protection
    - CORS configuration limits allowed origins
    """
    
    JWT_ACCESS_COOKIE_NAME = 'access_token'
    
    # HTTP methods that modify state (need extra CSRF protection)
    UNSAFE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Build set of allowed origins from CORS settings
        self.allowed_origins = set(getattr(settings, 'CORS_ALLOWED_ORIGINS', []))
    
    def __call__(self, request):
        # Debug: Log cookies received
        if request.path.startswith('/api/'):
            logger.debug(f"Path: {request.path}, Cookies: {list(request.COOKIES.keys())}")
        
        # CSRF Protection: Verify Origin header for unsafe methods with cookie auth
        if (request.method in self.UNSAFE_METHODS and 
            request.path.startswith('/api/') and
            request.COOKIES.get(self.JWT_ACCESS_COOKIE_NAME)):
            
            origin = request.META.get('HTTP_ORIGIN')
            if origin and origin not in self.allowed_origins:
                # Log potential CSRF attempt
                logger.warning(
                    f"CSRF Protection: Blocked request from origin {origin} "
                    f"to {request.path}. Method: {request.method}"
                )
                from django.http import JsonResponse
                return JsonResponse(
                    {'error': 'CSRF validation failed: Invalid origin'},
                    status=403
                )
        
        # Only process if no Authorization header is present
        if 'HTTP_AUTHORIZATION' not in request.META:
            access_token = request.COOKIES.get(self.JWT_ACCESS_COOKIE_NAME)
            if access_token:
                # Add the token to the request headers for DRF
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
                logger.debug(f"Added Bearer token for {request.path}")
            else:
                logger.debug(f"No access_token cookie found for {request.path}")
        
        response = self.get_response(request)
        return response
