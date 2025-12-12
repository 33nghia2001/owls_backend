"""
Custom middleware for OWLS Marketplace.
"""
import logging

logger = logging.getLogger(__name__)


class JWTCookieMiddleware:
    """
    Middleware to extract JWT access token from httpOnly cookie
    and add it to the Authorization header for DRF authentication.
    
    This allows using httpOnly cookies for security while maintaining
    compatibility with DRF's token authentication.
    """
    
    JWT_ACCESS_COOKIE_NAME = 'access_token'
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Debug: Log cookies received
        if request.path.startswith('/api/'):
            logger.debug(f"Path: {request.path}, Cookies: {list(request.COOKIES.keys())}")
        
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
