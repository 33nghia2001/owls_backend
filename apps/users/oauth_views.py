"""
Google OAuth authentication views.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from social_django.utils import load_strategy, load_backend
from social_core.backends.google import GoogleOAuth2
from social_core.exceptions import AuthException, AuthCanceled
from django.contrib.auth import get_user_model

User = get_user_model()


class GoogleLoginView(APIView):
    """
    Initiate Google OAuth login.
    
    GET /api/users/auth/google/
    Response: { "authorization_url": "https://accounts.google.com/o/oauth2/..." }
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        redirect_uri = request.build_absolute_uri('/api/users/auth/google/callback/')
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
            redirect_uri = request.build_absolute_uri('/api/users/auth/google/callback/')
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
            return user
        except User.DoesNotExist:
            pass
        
        # Create new user
        username = email.split('@')[0]
        
        # Ensure unique username
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        user = User.objects.create_user(
            username=username,
            email=email,
            full_name=user_data.get('name', ''),
            role='student',
            is_active=True,
            email_verified=True  # Google already verified email
        )
        
        return user
