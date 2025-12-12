"""
Custom middleware for OWLS Marketplace.
"""


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
        # Only process if no Authorization header is present
        if 'HTTP_AUTHORIZATION' not in request.META:
            access_token = request.COOKIES.get(self.JWT_ACCESS_COOKIE_NAME)
            if access_token:
                # Add the token to the request headers for DRF
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
        
        response = self.get_response(request)
        return response
