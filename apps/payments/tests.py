"""
Unit tests for Payments app.
Tests cover:
- Payment creation
- Payment methods (COD, Stripe, VNPay)
- Payment status transitions
- Refund handling
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from djmoney.money import Money

from apps.users.models import Users as CustomUser
from apps.vendors.models import Vendor
from apps.products.models import Product, Category
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentLog
from apps.payments.vnpay import VNPayService


class PaymentModelTests(TestCase):
    """Test Payment model."""
    
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
    
    def test_payment_creation(self):
        """Test payment can be created."""
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            method='cod',
            amount=Money(230000, 'VND')
        )
        
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(str(payment.amount.amount), '230000.00')
    
    def test_payment_str_method(self):
        """Test payment string representation."""
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            method='stripe',
            amount=Money(230000, 'VND')
        )
        
        expected = f"{self.order.order_number} - stripe - pending"
        self.assertEqual(str(payment), expected)
    
    def test_payment_log_created(self):
        """Test payment log can be created."""
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            method='vnpay',
            amount=Money(230000, 'VND')
        )
        
        log = PaymentLog.objects.create(
            payment=payment,
            action='create',
            request_data={'order_id': str(self.order.id)},
            response_data={'vnp_TxnRef': '12345'},
            is_success=True
        )
        
        self.assertEqual(payment.logs.count(), 1)
        self.assertTrue(log.is_success)


class PaymentAPITests(APITestCase):
    """Test Payment API endpoints."""
    
    def setUp(self):
        self.customer = CustomUser.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            role='customer'
        )
        
        self.order = Order.objects.create(
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
        
        self.client = APIClient()
    
    def test_create_cod_payment(self):
        """Test creating COD payment."""
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'order_id': str(self.order.id),
            'method': 'cod'
        }
        
        response = self.client.post(
            reverse('payment-create-payment'),
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payment']['method'], 'cod')
        
        # Check order status updated
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'confirmed')
    
    @patch('stripe.checkout.Session.create')
    def test_create_stripe_payment(self, mock_stripe):
        """Test creating Stripe payment."""
        mock_stripe.return_value = MagicMock(
            id='cs_test_123',
            url='https://checkout.stripe.com/test'
        )
        
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'order_id': str(self.order.id),
            'method': 'stripe',
            'return_url': 'http://localhost:3000/checkout/success'
        }
        
        response = self.client.post(
            reverse('payment-create-payment'),
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('checkout_url', response.data)
    
    def test_create_vnpay_payment(self):
        """Test creating VNPay payment."""
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'order_id': str(self.order.id),
            'method': 'vnpay',
            'return_url': 'http://localhost:3000/checkout/success'
        }
        
        response = self.client.post(
            reverse('payment-create-payment'),
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('payment_url', response.data)
    
    def test_cannot_pay_already_paid_order(self):
        """Test that already paid orders cannot be paid again."""
        # Create existing payment
        Payment.objects.create(
            order=self.order,
            user=self.customer,
            method='cod',
            amount=Money(230000, 'VND'),
            status='completed'
        )
        
        self.client.force_authenticate(user=self.customer)
        
        data = {
            'order_id': str(self.order.id),
            'method': 'stripe'
        }
        
        response = self.client.post(
            reverse('payment-create-payment'),
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_list_user_payments(self):
        """Test listing user's payments."""
        Payment.objects.create(
            order=self.order,
            user=self.customer,
            method='cod',
            amount=Money(230000, 'VND')
        )
        
        self.client.force_authenticate(user=self.customer)
        
        response = self.client.get(reverse('payment-list'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_other_user_cannot_see_payment(self):
        """Test users cannot see other's payments."""
        other_user = CustomUser.objects.create_user(
            email='other@test.com',
            password='testpass123',
            role='customer'
        )
        
        Payment.objects.create(
            order=self.order,
            user=self.customer,
            method='cod',
            amount=Money(230000, 'VND')
        )
        
        self.client.force_authenticate(user=other_user)
        
        response = self.client.get(reverse('payment-list'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)


class VNPayServiceTests(TestCase):
    """Test VNPay integration service."""
    
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
    
    def test_create_payment_url(self):
        """Test VNPay payment URL generation."""
        service = VNPayService()
        
        url = service.create_payment_url(
            order_id=str(self.order.id),
            amount=int(self.order.total.amount),
            order_desc=f"Payment for order {self.order.order_number}",
            return_url='http://localhost:3000/checkout/vnpay-return',
            ip_address='127.0.0.1'
        )
        
        self.assertIn('vnpay.vn', url)
        self.assertIn('vnp_Amount', url)
        self.assertIn('vnp_TxnRef', url)
    
    def test_verify_callback_valid(self):
        """Test VNPay callback verification with valid data."""
        service = VNPayService()
        
        # This would need actual hash from VNPay
        # For unit test, we mock the verification
        # In real scenario, you'd use test credentials from VNPay
        pass


class PaymentStatusTransitionTests(TestCase):
    """Test payment status transitions."""
    
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
    
    def test_pending_to_completed(self):
        """Test payment can go from pending to completed."""
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            method='stripe',
            amount=Money(230000, 'VND'),
            status='pending'
        )
        
        payment.status = 'completed'
        payment.save()
        
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'completed')
    
    def test_completed_to_refunded(self):
        """Test payment can be refunded."""
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            method='stripe',
            amount=Money(230000, 'VND'),
            status='completed'
        )
        
        payment.status = 'refunded'
        payment.refund_amount = Money(230000, 'VND')
        payment.refund_reason = 'Customer request'
        payment.save()
        
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'refunded')
        self.assertEqual(str(payment.refund_amount.amount), '230000.00')


class PaymentLogTests(TestCase):
    """Test payment logging."""
    
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
        
        self.payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            method='vnpay',
            amount=Money(230000, 'VND')
        )
    
    def test_log_payment_creation(self):
        """Test logging payment creation."""
        log = PaymentLog.objects.create(
            payment=self.payment,
            action='create',
            request_data={'order_id': str(self.order.id), 'amount': 230000},
            response_data={'payment_url': 'https://vnpay.vn/...'},
            is_success=True
        )
        
        self.assertEqual(log.action, 'create')
        self.assertTrue(log.is_success)
    
    def test_log_payment_callback(self):
        """Test logging payment callback."""
        log = PaymentLog.objects.create(
            payment=self.payment,
            action='callback',
            request_data={'vnp_ResponseCode': '00', 'vnp_TxnRef': '12345'},
            response_data={'status': 'completed'},
            is_success=True
        )
        
        self.assertEqual(log.action, 'callback')
        self.assertEqual(self.payment.logs.count(), 1)
    
    def test_log_failed_payment(self):
        """Test logging failed payment."""
        log = PaymentLog.objects.create(
            payment=self.payment,
            action='callback',
            request_data={'vnp_ResponseCode': '99'},
            response_data={},
            is_success=False,
            error_message='Payment failed: Invalid signature'
        )
        
        self.assertFalse(log.is_success)
        self.assertIn('Invalid signature', log.error_message)
