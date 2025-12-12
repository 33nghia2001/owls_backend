from rest_framework import serializers
from .models import Order, OrderItem, OrderStatusHistory, SubOrder, SubOrderStatusHistory, RefundRequest
from apps.products.serializers import ProductListSerializer
from apps.shipping.constants import normalize_province_name, is_valid_province


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


class SubOrderStatusHistorySerializer(serializers.ModelSerializer):
    """Serializer for sub-order status history."""
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    
    class Meta:
        model = SubOrderStatusHistory
        fields = ['id', 'status', 'note', 'created_by_email', 'created_at']


class SubOrderSerializer(serializers.ModelSerializer):
    """Serializer for sub-orders (per vendor)."""
    vendor_name = serializers.CharField(source='vendor.business_name', read_only=True)
    status_history = SubOrderStatusHistorySerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SubOrder
        fields = [
            'id', 'sub_order_number', 'vendor', 'vendor_name', 'status',
            'subtotal', 'shipping_cost', 'total',
            'commission_rate', 'commission_amount',
            'tracking_number', 'carrier_name',
            'status_history', 'items_count',
            'created_at', 'confirmed_at', 'shipped_at', 'delivered_at'
        ]
    
    def get_items_count(self, obj):
        return obj.order.items.filter(vendor=obj.vendor).count()


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
    sub_orders = SubOrderSerializer(many=True, read_only=True)
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
            'items', 'sub_orders', 'status_history',
            'created_at', 'confirmed_at', 'shipped_at', 'delivered_at'
        ]


class CreateOrderSerializer(serializers.Serializer):
    """Serializer for creating orders from cart."""
    
    # Guest checkout fields
    guest_email = serializers.EmailField(required=False, allow_blank=True)
    guest_cart_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
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
    
    def validate_shipping_province(self, value):
        """Validate and normalize shipping province name."""
        normalized = normalize_province_name(value)
        if not normalized:
            raise serializers.ValidationError(
                f'Tỉnh/Thành phố "{value}" không hợp lệ. Vui lòng chọn từ danh sách tỉnh thành Việt Nam.'
            )
        return normalized
    
    def validate_billing_province(self, value):
        """Validate and normalize billing province name if provided."""
        if not value:
            return value
        normalized = normalize_province_name(value)
        if not normalized:
            raise serializers.ValidationError(
                f'Tỉnh/Thành phố "{value}" không hợp lệ. Vui lòng chọn từ danh sách tỉnh thành Việt Nam.'
            )
        return normalized


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


class RefundRequestSerializer(serializers.ModelSerializer):
    """Serializer for refund requests."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    item_name = serializers.CharField(source='item.product_name', read_only=True, allow_null=True)
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True, allow_null=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = RefundRequest
        fields = [
            'id', 'order', 'order_number', 'sub_order', 'item', 'item_name',
            'reason', 'reason_display', 'description',
            'requested_amount', 'approved_amount',
            'status', 'status_display',
            'evidence_images',
            'reviewed_by', 'reviewed_by_email', 'review_note', 'reviewed_at',
            'refund_transaction_id', 'refunded_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'approved_amount', 'status', 
            'reviewed_by', 'review_note', 'reviewed_at',
            'refund_transaction_id', 'refunded_at',
            'created_at', 'updated_at'
        ]


class CreateRefundRequestSerializer(serializers.Serializer):
    """Serializer for creating refund requests."""
    order_id = serializers.UUIDField()
    item_id = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.ChoiceField(choices=RefundRequest.Reason.choices)
    description = serializers.CharField(min_length=20, max_length=2000)
    evidence_images = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        max_length=5  # Max 5 images
    )
    
    def validate_order_id(self, value):
        """Validate order exists and belongs to user."""
        user = self.context['request'].user
        try:
            order = Order.objects.get(id=value, user=user)
        except Order.DoesNotExist:
            raise serializers.ValidationError('Đơn hàng không tồn tại.')
        
        # Check if order is eligible for refund
        if order.status in [Order.Status.PENDING, Order.Status.CANCELLED, Order.Status.REFUNDED]:
            raise serializers.ValidationError(
                f'Đơn hàng có trạng thái "{order.get_status_display()}" không thể yêu cầu hoàn tiền.'
            )
        
        # Check if refund already requested
        if order.refund_requests.filter(
            status__in=[RefundRequest.Status.PENDING, RefundRequest.Status.UNDER_REVIEW, 
                       RefundRequest.Status.APPROVED, RefundRequest.Status.PROCESSING]
        ).exists():
            raise serializers.ValidationError('Đơn hàng này đã có yêu cầu hoàn tiền đang xử lý.')
        
        return value
    
    def validate_item_id(self, value):
        """Validate item belongs to the order."""
        if not value:
            return value
        
        order_id = self.initial_data.get('order_id')
        if order_id:
            try:
                item = OrderItem.objects.get(id=value, order_id=order_id)
                # Check if item already has pending refund
                if item.refund_requests.filter(
                    status__in=[RefundRequest.Status.PENDING, RefundRequest.Status.UNDER_REVIEW]
                ).exists():
                    raise serializers.ValidationError('Sản phẩm này đã có yêu cầu hoàn tiền đang xử lý.')
            except OrderItem.DoesNotExist:
                raise serializers.ValidationError('Sản phẩm không tồn tại trong đơn hàng.')
        
        return value
    
    def create(self, validated_data):
        order = Order.objects.get(id=validated_data['order_id'])
        item = None
        if validated_data.get('item_id'):
            item = OrderItem.objects.get(id=validated_data['item_id'])
        
        # Calculate requested amount
        if item:
            requested_amount = item.total_price
        else:
            requested_amount = order.total
        
        return RefundRequest.objects.create(
            order=order,
            item=item,
            reason=validated_data['reason'],
            description=validated_data['description'],
            evidence_images=validated_data.get('evidence_images', []),
            requested_amount=requested_amount,
        )


class ReviewRefundRequestSerializer(serializers.Serializer):
    """Serializer for reviewing refund requests (vendor/admin)."""
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, 
        required=False, allow_null=True
    )  # Only for partial refunds
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)