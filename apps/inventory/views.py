from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Inventory, InventoryMovement
from apps.vendors.permissions import IsApprovedVendor


class InventorySerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    available_quantity = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = Inventory
        fields = [
            'id', 'product', 'variant', 'product_name', 'quantity',
            'reserved_quantity', 'available_quantity', 'is_in_stock',
            'is_low_stock', 'low_stock_threshold', 'warehouse_location'
        ]
    
    def validate(self, attrs):
        """
        Validate inventory constraints before saving.
        Prevents Ghost Inventory (product with variants having its own inventory).
        """
        product = attrs.get('product')
        variant = attrs.get('variant')
        
        # For updates, get existing values if not in attrs
        if self.instance:
            product = product if 'product' in attrs else self.instance.product
            variant = variant if 'variant' in attrs else self.instance.variant
        
        # Must have exactly one of product or variant
        if product and variant:
            raise serializers.ValidationError(
                "Inventory cannot be linked to both product and variant."
            )
        if not product and not variant:
            raise serializers.ValidationError(
                "Inventory must be linked to either a product or variant."
            )
        
        # CRITICAL: Prevent Ghost Inventory
        if product and product.variants.exists():
            raise serializers.ValidationError(
                f"Cannot create inventory for product '{product.name}' because it has variants. "
                "Inventory must be managed at the variant level."
            )
        
        return attrs
    
    def get_product_name(self, obj):
        if obj.product:
            return obj.product.name
        if obj.variant:
            return f"{obj.variant.product.name} - {obj.variant.name}"
        return ''


class InventoryMovementSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    
    class Meta:
        model = InventoryMovement
        fields = [
            'id', 'inventory', 'movement_type', 'quantity',
            'reference_type', 'reference_id', 'note',
            'created_by_email', 'created_at'
        ]


class InventoryViewSet(viewsets.ModelViewSet):
    """ViewSet for inventory management."""
    serializer_class = InventorySerializer
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    
    def get_queryset(self):
        vendor = self.request.user.vendor_profile
        return Inventory.objects.filter(
            Q(product__vendor=vendor) | Q(variant__product__vendor=vendor)
        )
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get low stock items."""
        queryset = self.get_queryset()
        low_stock_items = [inv for inv in queryset if inv.is_low_stock]
        serializer = InventorySerializer(low_stock_items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def adjust(self, request, pk=None):
        """Adjust inventory quantity."""
        inventory = self.get_object()
        
        new_quantity = request.data.get('quantity')
        note = request.data.get('note', '')
        
        if new_quantity is None:
            return Response(
                {'error': 'Quantity required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        InventoryMovement.objects.create(
            inventory=inventory,
            movement_type='adjustment',
            quantity=int(new_quantity),
            reference_type='manual',
            note=note,
            created_by=request.user
        )
        
        inventory.refresh_from_db()
        return Response(InventorySerializer(inventory).data)
    
    @action(detail=True, methods=['post'])
    def add_stock(self, request, pk=None):
        """Add stock to inventory."""
        inventory = self.get_object()
        
        quantity = request.data.get('quantity', 0)
        note = request.data.get('note', '')
        
        if quantity <= 0:
            return Response(
                {'error': 'Quantity must be positive.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        InventoryMovement.objects.create(
            inventory=inventory,
            movement_type='in',
            quantity=int(quantity),
            reference_type='manual',
            note=note,
            created_by=request.user
        )
        
        inventory.refresh_from_db()
        return Response(InventorySerializer(inventory).data)


class InventoryMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for inventory movement history."""
    serializer_class = InventoryMovementSerializer
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    
    def get_queryset(self):
        vendor = self.request.user.vendor_profile
        return InventoryMovement.objects.filter(
            Q(inventory__product__vendor=vendor) |
            Q(inventory__variant__product__vendor=vendor)
        )
