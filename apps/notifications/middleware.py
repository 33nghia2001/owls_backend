"""
Custom JWT Authentication Middleware for Django Channels WebSockets.
Securely authenticate WebSocket connections using HttpOnly cookies instead of URL params.
"""
import logging
from urllib.parse import parse_qs
from typing import Optional, Dict, Union, TYPE_CHECKING

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

User = get_user_model()
logger = logging.getLogger(__name__)

# Constants
ACCESS_TOKEN_COOKIE_NAME = 'access_token'
TICKET_PARAM_NAME = 'ticket'
TICKET_CACHE_PREFIX = 'ws_ticket:'

# Lua script for atomic GET and DEL operation in Redis
ATOMIC_GET_DEL_SCRIPT = """
local value = redis.call('GET', KEYS[1])
if value then
    redis.call('DEL', KEYS[1])
    return value
else
    return nil
end
"""

class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections via JWT.
    
    Priority order:
    1. HttpOnly Cookie (Most secure - recommended for production)
    2. One-time ticket from query params (Fallback)
    """

    async def __call__(self, scope, receive, send):
        # 1. Try cookie authentication first
        scope['user'] = await self.get_user_from_cookie(scope)

        # 2. If cookies failed, try ticket authentication
        if scope['user'].is_anonymous:
            scope['user'] = await self.get_user_from_ticket(scope)

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_cookie(self, scope) -> Union['AbstractBaseUser', AnonymousUser]:
        """Authenticate user from HttpOnly cookie."""
        try:
            cookies = self._parse_cookies(scope)
            access_token_str = cookies.get(ACCESS_TOKEN_COOKIE_NAME)

            if not access_token_str:
                return AnonymousUser()

            # Validate JWT
            access_token = AccessToken(access_token_str)
            user_id = access_token['user_id']

            return self._get_user_by_id(user_id)

        except (TokenError, InvalidToken, KeyError):
            return AnonymousUser()
        except Exception as e:
            logger.error(f"WebSocket Cookie Auth Error: {str(e)}")
            return AnonymousUser()

    @database_sync_to_async
    def get_user_from_ticket(self, scope) -> Union['AbstractBaseUser', AnonymousUser]:
        """Authenticate using one-time ticket (Atomic Redis operation)."""
        try:
            ticket = self._get_ticket_from_scope(scope)
            if not ticket:
                return AnonymousUser()

            # Attempt to redeem ticket atomically
            user_id = self._redeem_ticket(ticket)
            
            if user_id:
                return self._get_user_by_id(user_id)
            
            return AnonymousUser()

        except Exception as e:
            logger.error(f"WebSocket Ticket Auth Error: {str(e)}")
            return AnonymousUser()

    # --------------------------------------------------------------------------
    # Helper Methods
    # --------------------------------------------------------------------------

    def _parse_cookies(self, scope) -> Dict[str, str]:
        """Extract cookies from scope headers into a dictionary."""
        cookies = {}
        for header_name, header_value in scope.get('headers', []):
            if header_name == b'cookie':
                cookie_str = header_value.decode()
                # Parse simple cookie string
                for cookie in cookie_str.split('; '):
                    if '=' in cookie:
                        key, value = cookie.split('=', 1)
                        cookies[key] = value
        return cookies

    def _get_ticket_from_scope(self, scope) -> Optional[str]:
        """Extract ticket from query string."""
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        return query_params.get(TICKET_PARAM_NAME, [None])[0]

    def _redeem_ticket(self, ticket: str) -> Optional[int]:
        """
        Atomically retrieve and delete the ticket from Redis.
        Returns user_id if valid, else None.
        """
        ticket_key = f'{TICKET_CACHE_PREFIX}{ticket}'
        
        try:
            # Access underlying Redis client for Lua execution
            if hasattr(cache, 'client') and hasattr(cache.client, 'get_client'):
                 # django-redis specific
                redis_client = cache.client.get_client()
            else:
                # Fallback or standard redis backend, might need adjustment based on specific cache backend setup
                # For safety in this context, we assume django-redis is used based on the original code
                redis_client = getattr(cache, '_cache', cache).get_client(None)

            # Execute Lua script
            user_id = redis_client.eval(ATOMIC_GET_DEL_SCRIPT, 1, ticket_key)

            if user_id:
                return int(user_id) if not isinstance(user_id, bytes) else int(user_id.decode())

        except Exception as e:
            # Fallback: Standard get/delete if Lua fails (e.g. cluster limitations or client issues)
            # This covers the race condition window technically, but provides service continuity
            logger.warning(f"Lua script failed, falling back to standard cache ops: {e}")
            user_id = cache.get(ticket_key)
            if user_id:
                cache.delete(ticket_key)
                return int(user_id)
        
        return None

    def _get_user_by_id(self, user_id: int) -> Union['AbstractBaseUser', AnonymousUser]:
        """Retrieve user from DB by ID."""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()


def JWTAuthMiddlewareStack(inner):
    """Helper to wrap WebSocket routes."""
    return JWTAuthMiddleware(inner)