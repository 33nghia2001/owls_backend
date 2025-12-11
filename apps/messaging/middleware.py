"""
Custom authentication middleware for Django Channels WebSocket.
Supports JWT token authentication via query string.

Usage in frontend:
const ws = new WebSocket('ws://domain/ws/chat/123/?token=eyJ...');
"""
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_key):
    """
    Validate JWT token and return the associated user.
    Returns AnonymousUser if token is invalid.
    """
    try:
        # Validate the access token
        access_token = AccessToken(token_key)
        user_id = access_token.get('user_id')
        
        if user_id:
            user = User.objects.get(id=user_id)
            return user
            
    except (InvalidToken, TokenError) as e:
        logger.warning(f"Invalid JWT token in WebSocket connection: {e}")
    except User.DoesNotExist:
        logger.warning(f"User not found for token user_id: {user_id}")
    except Exception as e:
        logger.error(f"Error validating JWT token: {e}")
    
    return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware for JWT authentication in WebSocket connections.
    
    Extracts JWT token from query string parameter 'token' and authenticates the user.
    Falls back to session authentication if no token is provided.
    """
    
    async def __call__(self, scope, receive, send):
        # Parse query string to get token
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        
        token_list = query_params.get('token', [])
        
        if token_list:
            # JWT token provided in query string
            token = token_list[0]
            scope['user'] = await get_user_from_token(token)
        else:
            # No token provided, check if session auth already set user
            # (from AuthMiddlewareStack)
            if 'user' not in scope or scope['user'].is_anonymous:
                scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """
    Convenience wrapper that combines JWT auth with session auth.
    JWT takes precedence if token is provided.
    """
    from channels.auth import AuthMiddlewareStack
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
