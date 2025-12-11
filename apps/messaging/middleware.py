"""
Custom authentication middleware for Django Channels WebSocket.
Supports both JWT token and Ticket-based authentication.

Recommended: Use ticket-based auth for better security.
- Client calls POST /api/messaging/ws-ticket/ to get a one-time ticket
- Client connects with ws://domain/ws/chat/123/?ticket=abc123

Fallback: JWT token via query string (less secure - token visible in logs)
- ws://domain/ws/chat/123/?token=eyJ...
"""
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from urllib.parse import parse_qs
import logging
import secrets

logger = logging.getLogger(__name__)
User = get_user_model()

# Ticket settings
WS_TICKET_PREFIX = 'ws_ticket_'
WS_TICKET_EXPIRY = 60  # seconds


def create_ws_ticket(user_id):
    """
    Create a one-time WebSocket authentication ticket.
    Returns the ticket string to be used in WebSocket connection.
    """
    ticket = secrets.token_urlsafe(32)
    cache_key = f"{WS_TICKET_PREFIX}{ticket}"
    cache.set(cache_key, str(user_id), timeout=WS_TICKET_EXPIRY)
    return ticket


@database_sync_to_async
def get_user_from_ticket(ticket):
    """
    Validate ticket and return the associated user.
    Ticket is consumed (one-time use) after validation.
    """
    cache_key = f"{WS_TICKET_PREFIX}{ticket}"
    user_id = cache.get(cache_key)
    
    if user_id:
        # Delete ticket immediately (one-time use)
        cache.delete(cache_key)
        
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.warning(f"User not found for ticket: {user_id}")
    
    return AnonymousUser()


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
    Custom middleware for WebSocket authentication.
    
    Supports two methods (in order of preference):
    1. Ticket-based auth (more secure): ?ticket=abc123
    2. JWT token auth (fallback): ?token=eyJ...
    """
    
    async def __call__(self, scope, receive, send):
        # Parse query string to get token
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        
        # Try ticket-based auth first (preferred, more secure)
        ticket_list = query_params.get('ticket', [])
        if ticket_list:
            scope['user'] = await get_user_from_ticket(ticket_list[0])
            return await super().__call__(scope, receive, send)
        
        # Fallback to JWT token auth
        token_list = query_params.get('token', [])
        if token_list:
            logger.warning("WebSocket using JWT token in URL - consider using ticket auth instead")
            scope['user'] = await get_user_from_token(token_list[0])
            return await super().__call__(scope, receive, send)
        
        # No auth provided
        scope['user'] = AnonymousUser()
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """
    Convenience wrapper that combines JWT auth with session auth.
    JWT takes precedence if token is provided.
    """
    from channels.auth import AuthMiddlewareStack
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
