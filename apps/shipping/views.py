from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes as perm
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.conf import settings
import logging

from .models import ShippingMethod, Shipment
from .serializers import ShippingMethodSerializer, ShipmentSerializer, ShippingQuoteSerializer
from .constants import VIETNAM_PROVINCES
from .services import get_shipping_provider, GHNProvider

logger = logging.getLogger(__name__)


@api_view(['GET'])
@perm([AllowAny])
def get_provinces(request):
    """
    Get list of valid Vietnam provinces for address validation.
    Used by frontend for address form dropdowns.
    """
    return Response({
        'provinces': VIETNAM_PROVINCES,
        'country': 'Vietnam'
    })


@api_view(['GET'])
@perm([AllowAny])
def get_ghn_provinces(request):
    """Get provinces from GHN API for accurate shipping calculation."""
    try:
        provider = GHNProvider()
        provinces = provider.get_provinces()
        return Response({'provinces': provinces})
    except Exception as e:
        logger.error(f"Failed to get GHN provinces: {e}")
        return Response(
            {'error': 'Failed to fetch provinces from shipping provider.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


@api_view(['GET'])
@perm([AllowAny])
def get_ghn_districts(request):
    """Get districts from GHN API."""
    province_id = request.query_params.get('province_id')
    if not province_id:
        return Response(
            {'error': 'province_id is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        provider = GHNProvider()
        districts = provider.get_districts(int(province_id))
        return Response({'districts': districts})
    except Exception as e:
        logger.error(f"Failed to get GHN districts: {e}")
        return Response(
            {'error': 'Failed to fetch districts from shipping provider.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


@api_view(['GET'])
@perm([AllowAny])
def get_ghn_wards(request):
    """Get wards from GHN API."""
    district_id = request.query_params.get('district_id')
    if not district_id:
        return Response(
            {'error': 'district_id is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        provider = GHNProvider()
        wards = provider.get_wards(int(district_id))
        return Response({'wards': wards})
    except Exception as e:
        logger.error(f"Failed to get GHN wards: {e}")
        return Response(
            {'error': 'Failed to fetch wards from shipping provider.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


@api_view(['POST'])
@perm([AllowAny])
def calculate_shipping_fee(request):
    """
    Calculate shipping fee using GHN or GHTK API.
    
    Request body:
    {
        "provider": "GHN",  // or "GHTK"
        "to_district_id": 1444,  // GHN district ID
        "to_ward_code": "20314",  // GHN ward code
        "weight": 500,  // grams
        "items": [{"weight": 200, "quantity": 2}],  // optional
        "insurance_value": 100000,  // optional, VND
        "from_district_id": 1542,  // optional, default from settings
        "from_ward_code": "21012",  // optional
        
        // For GHTK (uses province/district names)
        "province": "Hồ Chí Minh",
        "district": "Quận 3",
        "address": "123 ABC Street"
    }
    """
    provider_name = request.data.get('provider', 'GHN')
    
    try:
        provider = get_shipping_provider(provider_name)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    # Calculate total weight from items if provided
    items = request.data.get('items', [])
    total_weight = request.data.get('weight', 0)
    
    if items and not total_weight:
        total_weight = sum(
            item.get('weight', 200) * item.get('quantity', 1)
            for item in items
        )
    
    total_weight = max(total_weight, 100)  # Minimum 100g
    
    try:
        if provider_name.upper() == 'GHN':
            quotes = provider.calculate_fee(
                from_district_id=request.data.get('from_district_id'),
                from_ward_code=request.data.get('from_ward_code'),
                to_district_id=request.data.get('to_district_id'),
                to_ward_code=request.data.get('to_ward_code'),
                weight=total_weight,
                length=request.data.get('length', 20),
                width=request.data.get('width', 20),
                height=request.data.get('height', 10),
                insurance_value=request.data.get('insurance_value', 0),
            )
        else:  # GHTK
            quotes = provider.calculate_fee(
                weight=total_weight,
                province=request.data.get('province'),
                district=request.data.get('district'),
                address=request.data.get('address', ''),
                value=request.data.get('insurance_value', 0),
            )
        
        serializer = ShippingQuoteSerializer(quotes, many=True)
        return Response({
            'provider': provider_name,
            'quotes': serializer.data,
            'weight': total_weight,
        })
    except Exception as e:
        logger.error(f"Shipping fee calculation failed: {e}")
        return Response(
            {'error': f'Failed to calculate shipping fee: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


@api_view(['POST'])
@perm([IsAuthenticated])
def track_shipment(request):
    """
    Track shipment by tracking number using provider API.
    
    Request body:
    {
        "tracking_number": "GHN123456",
        "provider": "GHN"  // optional, will try to detect
    }
    """
    tracking_number = request.data.get('tracking_number')
    if not tracking_number:
        return Response(
            {'error': 'tracking_number is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Try to get provider from shipment record
    provider_name = request.data.get('provider')
    if not provider_name:
        try:
            shipment = Shipment.objects.get(
                tracking_number=tracking_number,
                order__user=request.user
            )
            provider_name = shipment.carrier or 'GHN'
        except Shipment.DoesNotExist:
            provider_name = 'GHN'  # Default to GHN
    
    try:
        provider = get_shipping_provider(provider_name)
        tracking_info = provider.track_order(tracking_number)
        
        return Response({
            'tracking_number': tracking_number,
            'provider': provider_name,
            'status': tracking_info.status,
            'status_description': tracking_info.status_description,
            'location': tracking_info.location,
            'events': tracking_info.events,
        })
    except Exception as e:
        logger.error(f"Shipment tracking failed: {e}")
        return Response(
            {'error': f'Failed to track shipment: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


class ShippingMethodViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for shipping methods."""
    queryset = ShippingMethod.objects.filter(is_active=True)
    serializer_class = ShippingMethodSerializer
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """Calculate shipping cost."""
        method_id = request.data.get('method_id')
        weight_kg = request.data.get('weight_kg', 0)
        
        try:
            method = ShippingMethod.objects.get(id=method_id, is_active=True)
        except ShippingMethod.DoesNotExist:
            return Response(
                {'error': 'Shipping method not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        cost = method.calculate_cost(float(weight_kg))
        
        return Response({
            'method': ShippingMethodSerializer(method).data,
            'cost': cost
        })


class ShipmentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for shipments."""
    serializer_class = ShipmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Shipment.objects.filter(
            order__user=self.request.user
        ).prefetch_related('tracking_history')
    
    @action(detail=False, methods=['get'])
    def track(self, request):
        """Track shipment by tracking number."""
        tracking_number = request.query_params.get('tracking_number')
        if not tracking_number:
            return Response(
                {'error': 'Tracking number required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        shipment = get_object_or_404(
            Shipment,
            tracking_number=tracking_number,
            order__user=request.user
        )
        
        return Response(ShipmentSerializer(shipment).data)
