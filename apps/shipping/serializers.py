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


class ShippingQuoteSerializer(serializers.Serializer):
    """Serializer for shipping fee quotes from providers."""
    provider = serializers.CharField()
    service_type = serializers.CharField()
    service_name = serializers.CharField()
    fee = serializers.DecimalField(max_digits=12, decimal_places=0)
    insurance_fee = serializers.DecimalField(max_digits=12, decimal_places=0)
    total_fee = serializers.DecimalField(max_digits=12, decimal_places=0)
    estimated_days = serializers.IntegerField()


class CalculateShippingFeeSerializer(serializers.Serializer):
    """Request serializer for shipping fee calculation."""
    provider = serializers.ChoiceField(choices=['GHN', 'GHTK'], default='GHN')
    to_district_id = serializers.IntegerField(required=False)
    to_ward_code = serializers.CharField(required=False)
    from_district_id = serializers.IntegerField(required=False)
    from_ward_code = serializers.CharField(required=False)
    weight = serializers.IntegerField(required=False, min_value=1)
    length = serializers.IntegerField(required=False, default=20)
    width = serializers.IntegerField(required=False, default=20)
    height = serializers.IntegerField(required=False, default=10)
    insurance_value = serializers.IntegerField(required=False, default=0)
    
    # GHTK-specific fields
    province = serializers.CharField(required=False)
    district = serializers.CharField(required=False)
    address = serializers.CharField(required=False)
    
    # Items for weight calculation
    items = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )
