"""
Google OAuth authentication views.
"""
import uuid
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from social_django.utils import load_strategy, load_backend
from social_core.backends.google import GoogleOAuth2
from social_core.exceptions import AuthException, AuthCanceled
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings

User = get_user_model()
logger = logging.getLogger(__name__)


class GoogleLoginView(APIView):
    """
    Initiate Google OAuth login.
    
    GET /api/users/auth/google/
    Response: { "authorization_url": "https://accounts.google.com/o/oauth2/..." }
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        # SECURITY: Use BACKEND_URL to prevent Host Header Injection
        # Use reverse() for maintainability when URL structure changes
        callback_path = reverse('google_callback')
        redirect_uri = f"{settings.BACKEND_URL}{callback_path}"
        strategy = load_strategy(request)
        backend = GoogleOAuth2(strategy=strategy, redirect_uri=redirect_uri)
        
        authorization_url = backend.auth_url()
        
        return Response({
            'authorization_url': authorization_url
        })


class GoogleCallbackView(APIView):
    """
    Handle Google OAuth callback and return JWT tokens.
    
    GET /api/users/auth/google/callback/?code=...&state=...
    Response: { "access": "...", "refresh": "...", "user": {...} }
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        code = request.GET.get('code')
        if not code:
            return Response(
                {'error': 'Authorization code not provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # SECURITY: Use BACKEND_URL to prevent Host Header Injection
            # Use reverse() for maintainability when URL structure changes
            callback_path = reverse('google_callback')
            redirect_uri = f"{settings.BACKEND_URL}{callback_path}"
            strategy = load_strategy(request)
            backend = GoogleOAuth2(strategy=strategy, redirect_uri=redirect_uri)
            
            # Exchange code for access token
            access_token = backend.auth_complete(request=request)
            
            # Get user from access token
            user_data = backend.user_data(access_token['access_token'])
            
            # Get or create user
            user = self.get_or_create_user(user_data)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'full_name': user.full_name,
                    'role': user.role,
                }
            })
            
        except (AuthException, AuthCanceled) as e:
            return Response(
                {'error': f'Authentication failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'An error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_or_create_user(self, user_data):
        """Get existing user or create new one from Google data."""
        email = user_data.get('email')
        
        # Check if user exists
        try:
            user = User.objects.get(email=email)
            
            # SECURITY: Only allow account linking if email was verified
            # Prevents account takeover via pre-registration with victim's email
            if not user.email_verified:
                logger.warning(
                    f"Blocked Google OAuth login for unverified email account: {email}. "
                    "Potential account takeover attempt."
                )
                raise ValueError(
                    "An account with this email exists but is not verified. "
                    "Please verify your email or reset your password first."
                )
            
            return user
        except User.DoesNotExist:
            pass
        
        # SECURITY: Generate random username to prevent enumeration
        # Old method: username = email.split('@')[0] allows attackers to guess usernames
        # New method: Use UUID for unpredictable usernames
        username = f"user_{uuid.uuid4().hex[:12]}"
        
        # Ensure uniqueness (extremely unlikely collision with UUID)
        while User.objects.filter(username=username).exists():
            username = f"user_{uuid.uuid4().hex[:12]}"
        
        user = User.objects.create_user(
            username=username,
            email=email,
            full_name=user_data.get('name', ''),
            role='student',
            is_active=True,
            email_verified=True  # Google already verified email
        )
        
        logger.info(f"Created new user via Google OAuth: {email} (username: {username})")
        
        return user
