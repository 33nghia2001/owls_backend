import os
import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from apps.courses.models import Course, Category
from apps.enrollments.models import Enrollment
from apps.payments.models import Payment, Discount
from decimal import Decimal

# Force DEBUG mode for tests (bypass security middleware)
os.environ.setdefault('DJANGO_DEBUG', '1')
os.environ.setdefault('IPWARE_TRUSTED_PROXY_LIST', '127.0.0.1')

User = get_user_model()


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db, settings):
    """
    Auto-enable DEBUG mode for all tests to bypass security middleware.
    Without this, IPWARE middleware will reject all test requests.
    """
    settings.DEBUG = True
    settings.IPWARE_TRUSTED_PROXY_LIST = ['127.0.0.1']


@pytest.fixture
def api_client():
    """Return DRF API client."""
    return APIClient()


@pytest.fixture
def student_user(db):
    """Create a student user."""
    return User.objects.create_user(
        username='student',
        email='student@test.com',
        password='testpass123',
        role='student'
    )


@pytest.fixture
def instructor_user(db):
    """Create an instructor user."""
    return User.objects.create_user(
        username='instructor',
        email='instructor@test.com',
        password='testpass123',
        role='instructor'
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        username='admin',
        email='admin@test.com',
        password='testpass123',
        role='admin',
        is_staff=True,
        is_superuser=True
    )


@pytest.fixture
def category(db):
    """Create a course category."""
    return Category.objects.create(
        name='Programming',
        slug='programming',
        description='Programming courses'
    )


@pytest.fixture
def course(db, instructor_user, category):
    """Create a course."""
    return Course.objects.create(
        title='Test Course',
        slug='test-course',
        description='Test course description',
        instructor=instructor_user,
        category=category,
        price=Decimal('100000.00'),
        status='published'
    )


@pytest.fixture
def free_course(db, instructor_user, category):
    """Create a free course."""
    return Course.objects.create(
        title='Free Course',
        slug='free-course',
        description='Free course description',
        instructor=instructor_user,
        category=category,
        price=Decimal('0.00'),
        status='published'
    )


@pytest.fixture
def enrollment(db, student_user, course):
    """Create an active enrollment."""
    return Enrollment.objects.create(
        student=student_user,
        course=course,
        status='active'
    )


@pytest.fixture
def payment(db, student_user, course):
    """Create a pending payment."""
    return Payment.objects.create(
        user=student_user,
        course=course,
        amount=Decimal('100000.00'),
        payment_method='vnpay',
        status='pending'
    )


@pytest.fixture
def discount(db):
    """Create an active discount code."""
    from django.utils import timezone
    return Discount.objects.create(
        code='TEST50',
        discount_type='percentage',
        discount_value=Decimal('50.00'),
        max_uses=10,
        is_active=True,
        valid_from=timezone.now(),
        valid_until=timezone.now() + timezone.timedelta(days=30)
    )


@pytest.fixture
def authenticated_client(api_client, student_user):
    """Return authenticated API client."""
    api_client.force_authenticate(user=student_user)
    return api_client


@pytest.fixture
def instructor_client(api_client, instructor_user):
    """Return authenticated instructor API client."""
    api_client.force_authenticate(user=instructor_user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Return authenticated admin API client."""
    api_client.force_authenticate(user=admin_user)
    return api_client
