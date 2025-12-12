from rest_framework import serializers
from .models import Order, OrderItem, OrderStatusHistory
from apps.products.serializers import ProductListSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order items."""
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'variant', 'product_name', 'product_sku',
            'variant_name', 'quantity', 'unit_price', 'total_price', 'status'
        ]


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    """Serializer for order status history."""
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    
    class Meta:
        model = OrderStatusHistory
        fields = ['id', 'status', 'note', 'created_by_email', 'created_at']


class OrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for order listing."""
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'payment_status',
            'total', 'items_count', 'created_at'
        ]
    
    def get_items_count(self, obj):
        return obj.items.count()


class OrderDetailSerializer(serializers.ModelSerializer):
    """Full serializer for order detail."""
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'payment_status',
            'subtotal', 'shipping_cost', 'discount_amount', 'tax_amount', 'total',
            # Shipping Address Fields
            'shipping_name', 'shipping_phone', 'shipping_address',
            'shipping_province', 'shipping_ward', 'shipping_country', 'shipping_postal_code',
            # Billing Address Fields
            'billing_name', 'billing_phone', 'billing_address',
            'billing_province', 'billing_ward', 'billing_country', 'billing_postal_code',
            'coupon', 'customer_note',
            'items', 'status_history',
            'created_at', 'confirmed_at', 'shipped_at', 'delivered_at'
        ]


class CreateOrderSerializer(serializers.Serializer):
    """Serializer for creating orders from cart."""
    
    # Shipping Address
    shipping_name = serializers.CharField(max_length=100)
    shipping_phone = serializers.CharField(max_length=20)
    shipping_address = serializers.CharField(max_length=255)
    
    # Cấu trúc địa chỉ mới: Tỉnh/TP và Phường/Xã
    shipping_province = serializers.CharField(max_length=100)
    shipping_ward = serializers.CharField(max_length=100)
    
    shipping_country = serializers.CharField(max_length=100, default='Vietnam')
    shipping_postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    
    # Optional billing address
    same_as_shipping = serializers.BooleanField(default=True)
    billing_name = serializers.CharField(max_length=100, required=False)
    billing_phone = serializers.CharField(max_length=20, required=False)
    billing_address = serializers.CharField(max_length=255, required=False)
    billing_province = serializers.CharField(max_length=100, required=False)
    billing_ward = serializers.CharField(max_length=100, required=False)
    billing_country = serializers.CharField(max_length=100, required=False)
    billing_postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    
    # Optional
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    customer_note = serializers.CharField(required=False, allow_blank=True)
    
    # Payment method
    payment_method = serializers.ChoiceField(choices=['cod', 'stripe', 'vnpay'])


class UpdateOrderStatusSerializer(serializers.Serializer):
    """Serializer for updating order status."""
    status = serializers.ChoiceField(choices=Order.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True)


class VendorOrderItemSerializer(serializers.ModelSerializer):
    """Serializer for vendor's view of order items."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.shipping_name', read_only=True)
    shipping_address = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'order_number', 'customer_name', 'shipping_address',
            'product_name', 'variant_name', 'quantity', 'unit_price', 
            'total_price', 'status', 'commission_amount', 'created_at',
            'product_image',
        ]
    
    def get_product_image(self, obj):
        """Get primary product image or first available."""
        if not obj.product:
            return None
        image = obj.product.images.filter(is_primary=True).first()
        if not image:
            image = obj.product.images.first()
        if image and image.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image.image.url)
            return image.image.url
        return None
    
    def get_shipping_address(self, obj):
        """Format full shipping address from new fields."""
        order = obj.order
        # Format: Số nhà/Đường, Phường/Xã, Tỉnh/TP
        return f"{order.shipping_address}, {order.shipping_ward}, {order.shipping_province}"