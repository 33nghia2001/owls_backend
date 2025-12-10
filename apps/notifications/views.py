from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.core.cache import cache
from django.conf import settings
import secrets


class WebSocketTicketThrottle(UserRateThrottle):
    """Throttle for WebSocket ticket generation to prevent Redis spam."""
    scope = 'ws_ticket'
    rate = '10/min'  # Allow 10 tickets per minute per user


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([WebSocketTicketThrottle])
def generate_ws_ticket(request):
    """
    Generate a short-lived ticket for WebSocket connection.
    
    SECURITY FIX: Implements the missing ticket system for mobile clients
    that cannot use cookies for WebSocket authentication.
    
    Usage:
    1. Client calls this endpoint to get a ticket
    2. Client connects to WebSocket with: ws[s]://host/ws/notifications/?ticket=<ticket>
    3. Ticket is valid for 30 seconds and can only be used once
    
    Throttling: 10 requests per minute per user to prevent Redis spam
    
    Returns:
        {
            "ticket": "random_token_here",
            "expires_in": 30,
            "ws_url": "wss://domain.com/ws/notifications/?ticket=..."
        }
    """
    # Generate cryptographically secure random ticket
    ticket = secrets.token_urlsafe(32)
    
    # Store ticket in Redis cache with 30-second expiration
    # Ticket maps to user_id for authentication
    cache.set(f'ws_ticket:{ticket}', request.user.id, timeout=30)
    
    # Build WebSocket URL from environment config
    # WS_BASE_URL should be set in production (e.g., wss://api.yourdomain.com)
    ws_base_url = getattr(settings, 'WS_BASE_URL', 'ws://localhost:8000')
    
    return Response({
        'ticket': ticket,
        'expires_in': 30,
        'ws_url': f'{ws_base_url}/ws/notifications/?ticket={ticket}'
    })
