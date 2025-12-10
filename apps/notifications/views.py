from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.cache import cache
import secrets


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_ws_ticket(request):
    """
    Generate a short-lived ticket for WebSocket connection.
    
    SECURITY FIX: Implements the missing ticket system for mobile clients
    that cannot use cookies for WebSocket authentication.
    
    Usage:
    1. Client calls this endpoint to get a ticket
    2. Client connects to WebSocket with: ws://host/ws/notifications/?ticket=<ticket>
    3. Ticket is valid for 30 seconds and can only be used once
    
    Returns:
        {
            "ticket": "random_token_here",
            "expires_in": 30
        }
    """
    # Generate cryptographically secure random ticket
    ticket = secrets.token_urlsafe(32)
    
    # Store ticket in Redis cache with 30-second expiration
    # Ticket maps to user_id for authentication
    cache.set(f'ws_ticket:{ticket}', request.user.id, timeout=30)
    
    return Response({
        'ticket': ticket,
        'expires_in': 30,
        'ws_url': f'ws://localhost:8000/ws/notifications/?ticket={ticket}'
    })
