from django.db import models
from django.conf import settings
from django.utils import timezone
from djmoney.models.fields import MoneyField
from phonenumber_field.modelfields import PhoneNumberField
import uuid
import random
import string


def generate_order_number():
    """
    Generate unique order number with collision retry.
    
    Format: OWL + 8 random chars (e.g., OWLABC12DEF)
    If collision detected, retry with new random part.
    """
    from django.db import IntegrityError
    
    prefix = 'OWL'
    max_attempts = 10
    
    for _ in range(max_attempts):
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        order_number = f"{prefix}{random_part}"
        
        # Check if already exists (without hitting IntegrityError)
        if not Order.objects.filter(order_number=order_number).exists():
            return order_number
    
    # Fallback: use timestamp + random to ensure uniqueness
    import time
    timestamp = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{prefix}{timestamp}{random_part}"


class Order(models.Model):
    """Main order model."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, default=generate_order_number)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # Allow guest orders
        related_name='orders'
    )
    # Guest checkout email (for orders without user account)
    guest_email = models.EmailField(blank=True, null=True, db_index=True)
    
    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(
        max_length=20, 
        choices=PaymentStatus.choices, 
        default=PaymentStatus.PENDING
    )
    
    # Pricing
    subtotal = MoneyField(max_digits=12, decimal_places=2, default_currency='VND')
    shipping_cost = MoneyField(max_digits=10, decimal_places=2, default_currency='VND', default=0)
    discount_amount = MoneyField(max_digits=10, decimal_places=2, default_currency='VND', default=0)
    tax_amount = MoneyField(max_digits=10, decimal_places=2, default_currency='VND', default=0)
    total = MoneyField(max_digits=12, decimal_places=2, default_currency='VND')
    
    # Shipping Address (Updated: Removed District, added Ward & Province)
    shipping_name = models.CharField(max_length=100)
    shipping_phone = PhoneNumberField()
    shipping_address = models.CharField(max_length=255) # Số nhà, tên đường
    shipping_province = models.CharField(max_length=100) # Tỉnh / Thành phố
    shipping_ward = models.CharField(max_length=100) # Phường / Xã
    shipping_country = models.CharField(max_length=100, default='Vietnam')
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    
    # Billing Address (Updated structure)
    billing_name = models.CharField(max_length=100, blank=True)
    billing_phone = PhoneNumberField(blank=True, null=True)
    billing_address = models.CharField(max_length=255, blank=True)
    billing_province = models.CharField(max_length=100, blank=True)
    billing_ward = models.CharField(max_length=100, blank=True)
    billing_country = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=20, blank=True)
    
    # Coupon
    coupon = models.ForeignKey(
        'coupons.Coupon',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )
    
    # Notes
    customer_note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'orders'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.order_number
    
    def calculate_total(self):
        """Calculate order total from items."""
        self.subtotal = sum(item.total_price for item in self.items.all())
        self.total = self.subtotal + self.shipping_cost + self.tax_amount - self.discount_amount
        return self.total
    
    def create_sub_orders(self):
        """
        Split order into sub-orders by vendor.
        
        Called after order items are created. Groups items by vendor
        and creates a SubOrder for each unique vendor.
        
        Returns:
            list[SubOrder]: Created sub-orders
        """
        from django.db.models import Sum
        
        # Get unique vendors from order items
        vendor_ids = self.items.values_list('vendor_id', flat=True).distinct()
        
        sub_orders = []
        for vendor_id in vendor_ids:
            if not vendor_id:
                continue
                
            # Calculate subtotal for this vendor's items
            vendor_items = self.items.filter(vendor_id=vendor_id)
            subtotal = vendor_items.aggregate(Sum('total_price'))['total_price__sum'] or 0
            
            # Create sub-order
            sub_order = SubOrder.objects.create(
                order=self,
                vendor_id=vendor_id,
                subtotal=subtotal,
                status=SubOrder.Status.PENDING,
            )
            sub_orders.append(sub_order)
        
        return sub_orders
    
    def update_status_from_sub_orders(self):
        """
        Update main order status based on sub-order statuses.
        
        Logic:
        - If ALL sub-orders are delivered -> order is delivered
        - If ANY sub-order is shipped -> order is shipped  
        - If ALL sub-orders are cancelled -> order is cancelled
        - Otherwise keep current status
        """
        sub_orders = self.sub_orders.all()
        if not sub_orders.exists():
            return
        
        statuses = set(sub_orders.values_list('status', flat=True))
        
        if statuses == {SubOrder.Status.DELIVERED}:
            self.status = Order.Status.DELIVERED
            self.delivered_at = timezone.now()
        elif statuses == {SubOrder.Status.CANCELLED}:
            self.status = Order.Status.CANCELLED
            self.cancelled_at = timezone.now()
        elif SubOrder.Status.SHIPPED in statuses:
            if self.status not in [Order.Status.SHIPPED, Order.Status.DELIVERED]:
                self.status = Order.Status.SHIPPED
                self.shipped_at = timezone.now()
        elif SubOrder.Status.PROCESSING in statuses:
            if self.status == Order.Status.CONFIRMED:
                self.status = Order.Status.PROCESSING
        
        self.save(update_fields=['status', 'shipped_at', 'delivered_at', 'cancelled_at', 'updated_at'])


class OrderItem(models.Model):
    """Individual items in an order."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items'
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items'
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items'
    )
    
    # Snapshot of product info at time of order
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=50, blank=True)
    variant_name = models.CharField(max_length=255, blank=True)
    
    quantity = models.PositiveIntegerField()
    unit_price = MoneyField(max_digits=12, decimal_places=2, default_currency='VND')
    total_price = MoneyField(max_digits=12, decimal_places=2, default_currency='VND')
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Vendor commission
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    commission_amount = MoneyField(max_digits=10, decimal_places=2, default_currency='VND', default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'order_items'
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
    
    def __str__(self):
        return f"{self.order.order_number} - {self.product_name}"
    
    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        self.commission_amount = self.total_price * (self.commission_rate / 100)
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    """Track order status changes."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_status_history'
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status Histories'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order.order_number} - {self.status}"


class SubOrder(models.Model):
    """
    Sub-order for multi-vendor marketplace.
    
    When a customer orders from multiple vendors, the main Order is split
    into SubOrders - one per vendor. Each SubOrder has its own:
    - Status tracking (vendor A can ship while vendor B is still processing)
    - Shipping cost calculation (distance from vendor warehouse)
    - Tracking number
    
    This enables proper multi-vendor order management where each vendor
    only sees and manages their portion of the order.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='sub_orders')
    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.PROTECT,
        related_name='sub_orders'
    )
    
    # Sub-order number: MAIN_ORDER_NUMBER-VENDOR_ID (e.g., OWLABC12DEF-V001)
    sub_order_number = models.CharField(max_length=30, unique=True, db_index=True)
    
    # Independent status per vendor
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Pricing for this vendor's portion
    subtotal = MoneyField(max_digits=12, decimal_places=2, default_currency='VND')
    shipping_cost = MoneyField(max_digits=10, decimal_places=2, default_currency='VND', default=0)
    total = MoneyField(max_digits=12, decimal_places=2, default_currency='VND')
    
    # Vendor commission for this sub-order
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    commission_amount = MoneyField(max_digits=10, decimal_places=2, default_currency='VND', default=0)
    
    # Shipping info (can differ from main order if vendor ships directly)
    shipping_method = models.ForeignKey(
        'shipping.ShippingMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    tracking_number = models.CharField(max_length=100, blank=True)
    carrier_name = models.CharField(max_length=100, blank=True)  # GHN, GHTK, etc.
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    
    # Vendor notes
    vendor_note = models.TextField(blank=True)
    
    class Meta:
        db_table = 'sub_orders'
        verbose_name = 'Sub Order'
        verbose_name_plural = 'Sub Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'vendor']),
            models.Index(fields=['vendor', 'status']),
        ]
    
    def __str__(self):
        return self.sub_order_number
    
    def save(self, *args, **kwargs):
        if not self.sub_order_number:
            # Generate sub-order number from main order
            vendor_code = str(self.vendor.id)[:4].upper()
            self.sub_order_number = f"{self.order.order_number}-{vendor_code}"
        
        # Calculate total
        self.total = self.subtotal + self.shipping_cost
        
        # Calculate commission
        self.commission_amount = self.subtotal * (self.commission_rate / 100)
        
        super().save(*args, **kwargs)
    
    def calculate_subtotal(self):
        """Calculate subtotal from items belonging to this vendor."""
        from django.db.models import Sum
        items = self.order.items.filter(vendor=self.vendor)
        total = items.aggregate(Sum('total_price'))['total_price__sum']
        self.subtotal = total or 0
        return self.subtotal


class SubOrderStatusHistory(models.Model):
    """Track sub-order status changes (per vendor)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_order = models.ForeignKey(SubOrder, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sub_order_status_history'
        verbose_name = 'Sub Order Status History'
        verbose_name_plural = 'Sub Order Status Histories'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.sub_order.sub_order_number} - {self.status}"