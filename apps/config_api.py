"""
System configuration API endpoints.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings


@api_view(['GET'])
@permission_classes([AllowAny])
def get_public_config(request):
    """
    Return public configuration values that frontend needs.
    This avoids hardcoding values in frontend and ensures consistency.
    """
    return Response({
        'shipping': {
            'free_shipping_threshold': getattr(settings, 'FREE_SHIPPING_THRESHOLD', 500000),
            'default_shipping_cost': getattr(settings, 'DEFAULT_SHIPPING_COST', 30000),
        },
        'currency': {
            'code': 'VND',
            'symbol': '₫',
            'decimal_places': 0,
        },
        'order': {
            'max_pending_orders': getattr(settings, 'MAX_PENDING_ORDERS_PER_USER', 3),
        },
        'file_upload': {
            'max_image_size_mb': getattr(settings, 'MAX_UPLOAD_SIZE', 5),
            'allowed_image_types': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
        },
    })
