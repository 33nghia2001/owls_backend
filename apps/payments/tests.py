import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from apps.payments.models import Payment, VNPayTransaction, Discount, DiscountUsage
from apps.enrollments.models import Enrollment
from apps.courses.models import Course


@pytest.mark.unit
class TestPaymentCreation:
    """Test payment creation endpoint"""

    def test_create_payment_for_paid_course(self, authenticated_client, student_user, course):
        """Test creating payment for paid course"""
        url = reverse('payment-list')
        data = {
            'course': course.id
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Payment.objects.filter(user=student_user, course=course).exists()
        
        payment = Payment.objects.get(user=student_user, course=course)
        assert payment.amount == course.price
        assert payment.status == 'pending'

    def test_create_payment_for_free_course_blocked(self, authenticated_client, student_user, free_course):
        """Test cannot create payment for free course"""
        url = reverse('payment-list')
        data = {
            'course': free_course.id
        }
        response = authenticated_client.post(url, data, format='json')
        
        # Should reject free course payments
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_duplicate_pending_payment_blocked(self, authenticated_client, student_user, course):
        """Test cannot create duplicate pending payments"""
        # Create first payment
        Payment.objects.create(
            user=student_user,
            course=course,
            amount=course.price,
            status='pending'
        )
        
        url = reverse('payment-list')
        data = {'course': course.id}
        response = authenticated_client.post(url, data, format='json')
        
        # Should reject duplicate pending payment
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_payment_for_already_enrolled_blocked(self, authenticated_client, student_user, course, enrollment):
        """Test cannot create payment if already enrolled"""
        url = reverse('payment-list')
        data = {'course': course.id}
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_cannot_create_payment(self, api_client, course):
        """Test unauthenticated users cannot create payments"""
        url = reverse('payment-list')
        data = {'course': course.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
class TestDiscountCode:
    """Test discount code application"""

    def test_apply_valid_percentage_discount(self, authenticated_client, student_user, course, discount):
        """Test applying valid percentage discount"""
        url = reverse('payment-apply-discount')
        data = {
            'course': course.id,
            'code': discount.code
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'final_price' in response.data
        
        # Verify discount calculation
        expected_discount = (course.price * discount.discount_value) / 100
        expected_final = course.price - expected_discount
        assert Decimal(str(response.data['final_price'])) == expected_final

    def test_apply_expired_discount_blocked(self, authenticated_client, student_user, course):
        """Test expired discount codes are rejected"""
        # Create expired discount
        expired_discount = Discount.objects.create(
            code='EXPIRED20',
            discount_type='percentage',
            discount_value=Decimal('20'),
            valid_from=timezone.now() - timezone.timedelta(days=30),
            valid_to=timezone.now() - timezone.timedelta(days=1),
            is_active=True
        )
        
        url = reverse('payment-apply-discount')
        data = {
            'course': course.id,
            'code': expired_discount.code
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_apply_inactive_discount_blocked(self, authenticated_client, student_user, course):
        """Test inactive discount codes are rejected"""
        inactive_discount = Discount.objects.create(
            code='INACTIVE20',
            discount_type='percentage',
            discount_value=Decimal('20'),
            is_active=False
        )
        
        url = reverse('payment-apply-discount')
        data = {
            'course': course.id,
            'code': inactive_discount.code
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_apply_discount_exceeding_usage_limit(self, authenticated_client, student_user, course):
        """Test discount code at usage limit is rejected"""
        limited_discount = Discount.objects.create(
            code='LIMITED',
            discount_type='percentage',
            discount_value=Decimal('20'),
            usage_limit=1,
            used_count=1,
            is_active=True
        )
        
        url = reverse('payment-apply-discount')
        data = {
            'course': course.id,
            'code': limited_discount.code
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.integration
class TestVNPayPaymentFlow:
    """Test VNPay payment integration"""

    def test_generate_vnpay_url(self, authenticated_client, student_user, course):
        """Test VNPay payment URL generation"""
        # Create payment
        payment = Payment.objects.create(
            user=student_user,
            course=course,
            amount=course.price,
            status='pending'
        )
        
        url = reverse('payment-vnpay-url', kwargs={'pk': payment.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'payment_url' in response.data
        assert 'vnpay.vn' in response.data['payment_url']
        
        # Verify VNPay transaction created
        assert VNPayTransaction.objects.filter(payment=payment).exists()

    def test_vnpay_ipn_successful_payment(self, api_client, student_user, course):
        """Test VNPay IPN callback for successful payment"""
        # Create payment with VNPay transaction
        payment = Payment.objects.create(
            user=student_user,
            course=course,
            amount=course.price,
            status='pending'
        )
        vnpay_txn = VNPayTransaction.objects.create(
            payment=payment,
            vnp_TxnRef=f"PAY{payment.id}",
            vnp_Amount=int((payment.amount * 100).to_integral_value())
        )
        
        # Mock VNPay IPN callback
        url = reverse('payment-vnpay-ipn')
        vnp_params = {
            'vnp_TxnRef': vnpay_txn.vnp_TxnRef,
            'vnp_Amount': str(vnpay_txn.vnp_Amount),
            'vnp_ResponseCode': '00',  # Success
            'vnp_TransactionNo': '123456789',
            'vnp_BankCode': 'NCB',
            'vnp_SecureHash': 'mock_hash'
        }
        
        with patch('apps.payments.vnpay.VNPay.validate_response', return_value=True):
            response = api_client.get(url, vnp_params)
        
        # Verify payment completed
        payment.refresh_from_db()
        assert payment.status == 'completed'
        assert payment.paid_at is not None
        
        # Verify enrollment created
        assert Enrollment.objects.filter(student=student_user, course=course).exists()

    def test_vnpay_ipn_failed_payment(self, api_client, student_user, course):
        """Test VNPay IPN callback for failed payment"""
        payment = Payment.objects.create(
            user=student_user,
            course=course,
            amount=course.price,
            status='pending'
        )
        vnpay_txn = VNPayTransaction.objects.create(
            payment=payment,
            vnp_TxnRef=f"PAY{payment.id}",
            vnp_Amount=int((payment.amount * 100).to_integral_value())
        )
        
        url = reverse('payment-vnpay-ipn')
        vnp_params = {
            'vnp_TxnRef': vnpay_txn.vnp_TxnRef,
            'vnp_Amount': str(vnpay_txn.vnp_Amount),
            'vnp_ResponseCode': '24',  # Failed
            'vnp_SecureHash': 'mock_hash'
        }
        
        with patch('apps.payments.vnpay.VNPay.validate_response', return_value=True):
            response = api_client.get(url, vnp_params)
        
        # Verify payment failed
        payment.refresh_from_db()
        assert payment.status == 'failed'
        
        # Verify NO enrollment created
        assert not Enrollment.objects.filter(student=student_user, course=course).exists()

    def test_vnpay_ipn_invalid_signature_blocked(self, api_client, student_user, course):
        """Test VNPay IPN with invalid signature is rejected"""
        payment = Payment.objects.create(
            user=student_user,
            course=course,
            amount=course.price,
            status='pending'
        )
        vnpay_txn = VNPayTransaction.objects.create(
            payment=payment,
            vnp_TxnRef=f"PAY{payment.id}",
            vnp_Amount=int((payment.amount * 100).to_integral_value())
        )
        
        url = reverse('payment-vnpay-ipn')
        vnp_params = {
            'vnp_TxnRef': vnpay_txn.vnp_TxnRef,
            'vnp_Amount': str(vnpay_txn.vnp_Amount),
            'vnp_ResponseCode': '00',
            'vnp_SecureHash': 'invalid_hash'
        }
        
        with patch('apps.payments.vnpay.VNPay.validate_response', return_value=False):
            response = api_client.get(url, vnp_params)
        
        # Verify payment NOT completed
        payment.refresh_from_db()
        assert payment.status == 'pending'


@pytest.mark.security
class TestPaymentSecurity:
    """Test payment security measures"""

    def test_decimal_precision_prevents_rounding_errors(self, student_user, course):
        """Test Decimal type prevents floating point rounding errors"""
        # Create payment with precise amount
        payment = Payment.objects.create(
            user=student_user,
            course=course,
            amount=Decimal('99999.99')
        )
        
        # Convert to VNPay amount (multiply by 100)
        vnpay_amount = int((payment.amount * 100).to_integral_value())
        
        # Verify exact conversion
        assert vnpay_amount == 9999999
        
        # Reverse conversion should match
        reversed_amount = Decimal(str(vnpay_amount)) / 100
        assert reversed_amount == payment.amount

    def test_payment_race_condition_prevented(self, student_user, course):
        """Test concurrent payment confirmations don't create duplicate enrollments"""
        import threading
        from django.db import transaction
        from apps.payments.views import process_payment_confirmation
        
        # Create payment
        payment = Payment.objects.create(
            user=student_user,
            course=course,
            amount=course.price,
            status='pending'
        )
        VNPayTransaction.objects.create(
            payment=payment,
            vnp_TxnRef=f"PAY{payment.id}",
            vnp_Amount=int((payment.amount * 100).to_integral_value())
        )
        
        vnp_params = {
            'vnp_ResponseCode': '00',
            'vnp_TransactionNo': '123456789',
            'vnp_PayDate': '20240101120000'
        }
        
        # Simulate REAL concurrent confirmations with threads
        errors = []
        
        def confirm_payment():
            try:
                with transaction.atomic():
                    # Refresh to get latest state
                    fresh_payment = Payment.objects.select_for_update().get(id=payment.id)
                    process_payment_confirmation(fresh_payment, vnp_params)
            except Exception as e:
                errors.append(e)
        
        # Run 2 threads simultaneously
        thread1 = threading.Thread(target=confirm_payment)
        thread2 = threading.Thread(target=confirm_payment)
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Verify only ONE enrollment created (despite 2 concurrent attempts)
        enrollment_count = Enrollment.objects.filter(student=student_user, course=course).count()
        assert enrollment_count == 1, f"Expected 1 enrollment, got {enrollment_count}"

    def test_payment_amount_validation_prevents_tampering(self, api_client, student_user, course):
        """Test VNPay IPN validates payment amount matches"""
        payment = Payment.objects.create(
            user=student_user,
            course=course,
            amount=Decimal('100000.00'),
            status='pending'
        )
        vnpay_txn = VNPayTransaction.objects.create(
            payment=payment,
            vnp_TxnRef=f"PAY{payment.id}",
            vnp_Amount=10000000  # 100,000 VND * 100
        )
        
        # Attacker tries to tamper with amount
        url = reverse('payment-vnpay-ipn')
        vnp_params = {
            'vnp_TxnRef': vnpay_txn.vnp_TxnRef,
            'vnp_Amount': '100',  # Tampered amount
            'vnp_ResponseCode': '00',
            'vnp_SecureHash': 'mock_hash'
        }
        
        with patch('apps.payments.vnpay.VNPay.validate_response', return_value=True):
            response = api_client.get(url, vnp_params)
        
        # Should detect amount mismatch
        payment.refresh_from_db()
        # Payment should remain pending or be marked as failed
        assert payment.status in ['pending', 'failed']
