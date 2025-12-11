"""
Unit tests for Orders app.
Tests cover:
- Order creation from cart
- Order status transitions
- Order cancellation
- Vendor order management
"""
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from djmoney.money import Money

from apps.users.models import Users as CustomUser
from apps.vendors.models import Vendor
from apps.products.models import Product, Category
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.coupons.models import Coupon


class OrderModelTests(TestCase):
    """Test Order model."""
    
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            role='customer'
        )
    
    def test_order_number_generated(self):
        """Test that order number is auto-generated."""
        order = Order.objects.create(
            user=self.user,
            subtotal=Money(100000, 'VND'),
            total=Money(130000, 'VND'),
            shipping_name='Test User',
            shipping_phone='+84912345678',
            shipping_address='123 Test St',
            shipping_city='Ho Chi Minh',
            shipping_state='Ho Chi Minh',
            shipping_postal_code='70000'
        )
        
        self.assertTrue(order.order_number.startswith('OWL'))
        self.assertEqual(len(order.order_number), 11)  # OWL + 8 chars
    
    def test_order_default_status(self):
        """Test order default status is pending."""
        order = Order.objects.create(
            user=self.user,
            subtotal=Money(100000, 'VND'),
            total=Money(130000, 'VND'),
            shipping_name='Test User',
            shipping_phone='+84912345678',
            shipping_address='123 Test St',
            shipping_city='Ho Chi Minh',
            shipping_state='Ho Chi Minh',
            shipping_postal_code='70000'
        )
        
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.payment_status, 'pending')


class OrderAPITests(APITestCase):
    """Test Order API endpoints."""
    
    def setUp(self):
        # Create customer
        self.customer = CustomUser.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            role='customer'
        )
        
        # Create vendor user and profile
        self.vendor_user = CustomUser.objects.create_user(
            email='vendor@test.com',
            password='testpass123',
            role='vendor'
        )
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            shop_name='Test Shop',
            slug='test-shop',
            status='approved',
            commission_rate=Decimal('10.00')
        )
        
        # Create category
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        # Create product
        self.product = Product.objects.create(
            vendor=self.vendor,
            category=self.category,
            name='Test Product',
            slug='test-product',
            price=Money(100000, 'VND'),
            stock=100,
            status='published'
        )
        
        # Create cart with item
        self.cart = Cart.objects.create(user=self.customer)
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2,
            unit_price=Money(100000, 'VND')
        )
        
        self.client = APIClient()
    
    def test_create_order_from_cart(self):
        """Test creating order from cart."""
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'shipping_name': 'Test Customer',
            'shipping_phone': '+84912345678',
            'shipping_address': '123 Test Street',
            'shipping_city': 'Ho Chi Minh',
            'shipping_state': 'Ho Chi Minh',
            'shipping_postal_code': '70000',
            'same_as_shipping': True
        }
        
        response = self.client.post(reverse('order-list'), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('order_number', response.data)
        self.assertEqual(response.data['status'], 'pending')
        
        # Check cart is cleared
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.items.count(), 0)
    
    def test_create_order_empty_cart(self):
        """Test creating order with empty cart fails."""
        self.client.force_authenticate(user=self.customer)
        
        # Clear cart
        self.cart.items.all().delete()
        
        data = {
            'shipping_name': 'Test Customer',
            'shipping_phone': '+84912345678',
            'shipping_address': '123 Test Street',
            'shipping_city': 'Ho Chi Minh',
            'shipping_state': 'Ho Chi Minh',
            'shipping_postal_code': '70000',
        }
        
        response = self.client.post(reverse('order-list'), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_list_orders(self):
        """Test listing user's orders."""
        self.client.force_authenticate(user=self.customer)
        
        # Create an order
        Order.objects.create(
            user=self.customer,
            subtotal=Money(200000, 'VND'),
            total=Money(230000, 'VND'),
            shipping_name='Test',
            shipping_phone='+84912345678',
            shipping_address='123 Test St',
            shipping_city='HCM',
            shipping_state='HCM',
            shipping_postal_code='70000'
        )
        
        response = self.client.get(reverse('order-list'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_cancel_order(self):
        """Test cancelling an order."""
        self.client.force_authenticate(user=self.customer)
        
        order = Order.objects.create(
            user=self.customer,
            subtotal=Money(200000, 'VND'),
            total=Money(230000, 'VND'),
            shipping_name='Test',
            shipping_phone='+84912345678',
            shipping_address='123 Test St',
            shipping_city='HCM',
            shipping_state='HCM',
            shipping_postal_code='70000',
            status='pending'
        )
        
        response = self.client.post(
            reverse('order-cancel', kwargs={'pk': order.id})
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
    
    def test_cannot_cancel_shipped_order(self):
        """Test that shipped orders cannot be cancelled."""
        self.client.force_authenticate(user=self.customer)
        
        order = Order.objects.create(
            user=self.customer,
            subtotal=Money(200000, 'VND'),
            total=Money(230000, 'VND'),
            shipping_name='Test',
            shipping_phone='+84912345678',
            shipping_address='123 Test St',
            shipping_city='HCM',
            shipping_state='HCM',
            shipping_postal_code='70000',
            status='shipped'
        )
        
        response = self.client.post(
            reverse('order-cancel', kwargs={'pk': order.id})
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_other_user_cannot_see_order(self):
        """Test that users cannot see other's orders."""
        # Create order for customer
        order = Order.objects.create(
            user=self.customer,
            subtotal=Money(200000, 'VND'),
            total=Money(230000, 'VND'),
            shipping_name='Test',
            shipping_phone='+84912345678',
            shipping_address='123 Test St',
            shipping_city='HCM',
            shipping_state='HCM',
            shipping_postal_code='70000'
        )
        
        # Try to access as vendor user
        self.client.force_authenticate(user=self.vendor_user)
        
        response = self.client.get(reverse('order-detail', kwargs={'pk': order.id}))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class OrderWithCouponTests(APITestCase):
    """Test orders with coupons."""
    
    def setUp(self):
        self.customer = CustomUser.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            role='customer'
        )
        
        self.vendor_user = CustomUser.objects.create_user(
            email='vendor@test.com',
            password='testpass123',
            role='vendor'
        )
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            shop_name='Test Shop',
            slug='test-shop',
            status='approved',
            commission_rate=Decimal('10.00')
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        self.product = Product.objects.create(
            vendor=self.vendor,
            category=self.category,
            name='Test Product',
            slug='test-product',
            price=Money(100000, 'VND'),
            stock=100,
            status='published'
        )
        
        self.cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2,
            unit_price=Money(100000, 'VND')
        )
        
        # Create coupon
        self.coupon = Coupon.objects.create(
            code='DISCOUNT10',
            discount_type='percentage',
            discount_value=10,
            max_discount=Money(50000, 'VND'),
            min_order_amount=Money(100000, 'VND'),
            is_active=True
        )
        
        self.client = APIClient()
    
    def test_order_with_valid_coupon(self):
        """Test creating order with valid coupon."""
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'shipping_name': 'Test Customer',
            'shipping_phone': '+84912345678',
            'shipping_address': '123 Test Street',
            'shipping_city': 'Ho Chi Minh',
            'shipping_state': 'Ho Chi Minh',
            'shipping_postal_code': '70000',
            'coupon_code': 'DISCOUNT10'
        }
        
        response = self.client.post(reverse('order-list'), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check discount applied
        self.assertGreater(float(response.data['discount_amount']), 0)


class VendorOrderTests(APITestCase):
    """Test vendor order management."""
    
    def setUp(self):
        self.customer = CustomUser.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            role='customer'
        )
        
        self.vendor_user = CustomUser.objects.create_user(
            email='vendor@test.com',
            password='testpass123',
            role='vendor'
        )
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            shop_name='Test Shop',
            slug='test-shop',
            status='approved',
            commission_rate=Decimal('10.00')
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        self.product = Product.objects.create(
            vendor=self.vendor,
            category=self.category,
            name='Test Product',
            slug='test-product',
            price=Money(100000, 'VND'),
            stock=100,
            status='published'
        )
        
        # Create order
        self.order = Order.objects.create(
            user=self.customer,
            subtotal=Money(200000, 'VND'),
            total=Money(230000, 'VND'),
            shipping_name='Test',
            shipping_phone='+84912345678',
            shipping_address='123 Test St',
            shipping_city='HCM',
            shipping_state='HCM',
            shipping_postal_code='70000',
            status='pending'
        )
        
        # Create order item
        self.order_item = OrderItem.objects.create(
            order=self.order,
            vendor=self.vendor,
            product=self.product,
            product_name='Test Product',
            quantity=2,
            unit_price=Money(100000, 'VND'),
            commission_rate=Decimal('10.00')
        )
        
        self.client = APIClient()
    
    def test_vendor_can_see_their_orders(self):
        """Test vendor can see orders for their products."""
        self.client.force_authenticate(user=self.vendor_user)
        
        response = self.client.get(reverse('vendor-order-list'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_vendor_update_order_status(self):
        """Test vendor can update order item status."""
        self.client.force_authenticate(user=self.vendor_user)
        
        # First confirm the order
        self.order_item.status = 'confirmed'
        self.order_item.save()
        
        data = {'status': 'processing'}
        
        response = self.client.post(
            reverse('vendor-order-update-status', kwargs={'pk': self.order_item.id}),
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.order_item.refresh_from_db()
        self.assertEqual(self.order_item.status, 'processing')
    
    def test_invalid_status_transition(self):
        """Test invalid status transition fails."""
        self.client.force_authenticate(user=self.vendor_user)
        
        # Try to go from pending to delivered directly
        data = {'status': 'delivered'}
        
        response = self.client.post(
            reverse('vendor-order-update-status', kwargs={'pk': self.order_item.id}),
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_vendor_stats(self):
        """Test vendor order statistics."""
        self.client.force_authenticate(user=self.vendor_user)
        
        response = self.client.get(reverse('vendor-order-stats'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_orders', response.data)
        self.assertIn('pending', response.data)


class OrderStatusHistoryTests(TestCase):
    """Test order status history tracking."""
    
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            role='customer'
        )
        
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Money(200000, 'VND'),
            total=Money(230000, 'VND'),
            shipping_name='Test',
            shipping_phone='+84912345678',
            shipping_address='123 Test St',
            shipping_city='HCM',
            shipping_state='HCM',
            shipping_postal_code='70000'
        )
    
    def test_status_history_created(self):
        """Test status history is created."""
        OrderStatusHistory.objects.create(
            order=self.order,
            status='pending',
            note='Order created',
            created_by=self.user
        )
        
        self.assertEqual(self.order.status_history.count(), 1)
        self.assertEqual(self.order.status_history.first().status, 'pending')
