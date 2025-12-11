from rest_framework import serializers
from .models import ShippingMethod, Shipment, ShipmentTracking


class ShippingMethodSerializer(serializers.ModelSerializer):
    delivery_time = serializers.SerializerMethodField()
    
    class Meta:
        model = ShippingMethod
        fields = ['id', 'name', 'code', 'description', 'base_cost', 'delivery_time']
    
    def get_delivery_time(self, obj):
        if obj.min_days == obj.max_days:
            return f"{obj.min_days} days"
        return f"{obj.min_days}-{obj.max_days} days"


class ShipmentTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentTracking
        fields = ['status', 'location', 'description', 'timestamp']


class ShipmentSerializer(serializers.ModelSerializer):
    tracking_history = ShipmentTrackingSerializer(many=True, read_only=True)
    method_name = serializers.CharField(source='method.name', read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'order', 'method', 'method_name', 'tracking_number',
            'carrier', 'status', 'weight_kg', 'tracking_history',
            'created_at', 'shipped_at', 'delivered_at'
        ]
