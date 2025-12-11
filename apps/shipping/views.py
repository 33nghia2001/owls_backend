from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404

from .models import ShippingMethod, Shipment
from .serializers import ShippingMethodSerializer, ShipmentSerializer


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
