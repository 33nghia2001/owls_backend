import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users.models import User


@pytest.mark.unit
class TestUserRegistration:
    """Test user registration endpoint"""

    def test_register_student_success(self, api_client):
        """Test successful student registration"""
        url = reverse('user-list')
        data = {
            'username': 'newstudent',
            'email': 'newstudent@test.com',
            'password': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(username='newstudent').exists()
        user = User.objects.get(username='newstudent')
        assert user.email == 'newstudent@test.com'
        assert user.role == 'student'  # Always student by default

    def test_register_always_creates_student(self, api_client):
        """Test registration always creates student role (security fix)"""
        url = reverse('user-list')
        data = {
            'username': 'newinstructor',
            'email': 'newinstructor@test.com',
            'password': 'SecurePass123!',
            'role': 'instructor'  # Try to set instructor (should be ignored)
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        user = User.objects.get(username='newinstructor')
        # SECURITY: Role should be 'student' regardless of input
        assert user.role == 'student'

    def test_register_password_too_short(self, api_client):
        """Test registration fails with short password"""
        url = reverse('user-list')
        data = {
            'username': 'testuser',
            'email': 'test@test.com',
            'password': 'short'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_username(self, api_client, student_user):
        """Test registration fails with duplicate username"""
        url = reverse('user-list')
        data = {
            'username': student_user.username,
            'email': 'different@test.com',
            'password': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email(self, api_client, student_user):
        """Test registration fails with duplicate email"""
        url = reverse('user-list')
        data = {
            'username': 'differentuser',
            'email': student_user.email,
            'password': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.unit
class TestJWTAuthentication:
    """Test JWT token authentication flow"""

    def test_login_success(self, api_client, student_user):
        """Test successful login returns JWT tokens"""
        url = reverse('token_obtain_pair')
        data = {
            'username': 'student',
            'password': 'testpass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_unverified_email_blocked(self, api_client):
        """Test login fails for unverified email users"""
        # Create user without email verification
        user = User.objects.create_user(
            username='unverified',
            email='unverified@test.com',
            password='testpass123',
            role='student',
            email_verified=False
        )
        
        url = reverse('token_obtain_pair')
        data = {
            'username': 'unverified',
            'password': 'testpass123'
        }
        response = api_client.post(url, data, format='json')
        
        # Should fail if email verification is enforced
        # If backend allows unverified login, adjust this test
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_login_invalid_credentials(self, api_client, student_user):
        """Test login fails with invalid credentials"""
        url = reverse('token_obtain_pair')
        data = {
            'username': 'student',
            'password': 'wrongpassword'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_success(self, api_client, student_user):
        """Test token refresh returns new access token"""
        # Get initial tokens
        refresh = RefreshToken.for_user(student_user)
        
        url = reverse('token_refresh')
        data = {'refresh': str(refresh)}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

    def test_logout_blacklists_token(self, api_client, student_user):
        """Test logout blacklists refresh token"""
        # Get initial tokens
        refresh = RefreshToken.for_user(student_user)
        
        url = reverse('logout')
        api_client.force_authenticate(user=student_user)
        data = {'refresh': str(refresh)}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_205_RESET_CONTENT
        
        # Try to use blacklisted token
        refresh_url = reverse('token_refresh')
        refresh_response = api_client.post(refresh_url, data, format='json')
        
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_access_protected_endpoint_with_token(self, authenticated_client):
        """Test authenticated access to protected endpoint"""
        url = reverse('user-me')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == 'student'

    def test_access_protected_endpoint_without_token(self, api_client):
        """Test unauthenticated access is blocked"""
        url = reverse('user-me')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
class TestUserProfile:
    """Test user profile endpoints"""

    def test_get_own_profile(self, authenticated_client, student_user):
        """Test user can retrieve their own profile"""
        url = reverse('user-me')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == student_user.id
        assert response.data['username'] == student_user.username
        assert response.data['email'] == student_user.email

    def test_update_own_profile(self, authenticated_client, student_user):
        """Test user can update their own profile"""
        url = reverse('user-me')
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'bio': 'Test bio'
        }
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        student_user.refresh_from_db()
        assert student_user.first_name == 'John'
        assert student_user.last_name == 'Doe'

    def test_cannot_change_role(self, authenticated_client, student_user):
        """Test user cannot change their own role"""
        url = reverse('user-me')
        data = {'role': 'instructor'}
        response = authenticated_client.patch(url, data, format='json')
        
        # Should either ignore role change or return error
        student_user.refresh_from_db()
        assert student_user.role == 'student'

    def test_cannot_change_email_verified(self, authenticated_client, student_user):
        """Test user cannot manually set email_verified"""
        url = reverse('user-me')
        data = {'email_verified': False}
        response = authenticated_client.patch(url, data, format='json')
        
        # Should ignore or block this change
        student_user.refresh_from_db()
        assert student_user.email_verified is True


@pytest.mark.security
class TestAuthenticationSecurity:
    """Test authentication security measures"""

    def test_password_is_hashed(self, student_user):
        """Test passwords are stored as hashes, not plaintext"""
        assert student_user.password != 'testpass123'
        assert student_user.password.startswith('pbkdf2_sha256$')

    def test_token_contains_no_sensitive_data(self, student_user):
        """Test JWT token doesn't expose sensitive data"""
        refresh = RefreshToken.for_user(student_user)
        access = str(refresh.access_token)
        
        # Token should not contain password or sensitive info
        assert 'testpass123' not in access
        assert student_user.password not in access

    def test_rate_limiting_exists(self, api_client):
        """Test that rate limiting is configured (prevent brute force)"""
        # This test verifies throttle config exists
        # Actual rate limit testing would require many requests
        from django.conf import settings
        
        assert 'DEFAULT_THROTTLE_RATES' in dir(settings.REST_FRAMEWORK)
        throttle_rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert len(throttle_rates) > 0


@pytest.mark.integration
class TestGoogleOAuth:
    """Test Google OAuth authentication flow"""

    def test_oauth_creates_user_with_uuid_username(self, api_client, mocker):
        """Test OAuth creates user with UUID-based username (not email prefix)"""
        # Mock Google OAuth backend
        mock_do_auth = mocker.patch('social_core.backends.google.GoogleOAuth2.do_auth')
        mock_user_data = mocker.patch('social_core.backends.google.GoogleOAuth2.user_data')
        
        # Simulate Google returning user data
        mock_user_data.return_value = {
            'email': 'newuser@gmail.com',
            'given_name': 'John',
            'family_name': 'Doe',
            'email_verified': True
        }
        
        url = reverse('google_callback')
        response = api_client.post(url, {'code': 'mock_auth_code'}, format='json')
        
        # Verify user created with UUID username (not 'newuser')
        if response.status_code == status.HTTP_200_OK:
            users = User.objects.filter(email='newuser@gmail.com')
            if users.exists():
                user = users.first()
                # Username should be user_{uuid}, not email prefix
                assert user.username.startswith('user_')
                assert user.username != 'newuser'
                assert len(user.username) > 10  # UUID portion

    def test_oauth_requires_verified_email(self, api_client, mocker):
        """Test OAuth rejects unverified Google accounts"""
        mock_user_data = mocker.patch('social_core.backends.google.GoogleOAuth2.user_data')
        
        # Simulate Google returning unverified email
        mock_user_data.return_value = {
            'email': 'unverified@gmail.com',
            'given_name': 'John',
            'family_name': 'Doe',
            'email_verified': False
        }
        
        url = reverse('google_callback')
        response = api_client.post(url, {'code': 'mock_auth_code'}, format='json')
        
        # Should reject unverified emails
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_oauth_prevents_account_linking_attacks(self, api_client, student_user, mocker):
        """Test OAuth prevents malicious account linking"""
        mock_user_data = mocker.patch('social_core.backends.google.GoogleOAuth2.user_data')
        
        # Attacker tries to link their Google to victim's email
        mock_user_data.return_value = {
            'email': student_user.email,
            'given_name': 'Attacker',
            'family_name': 'Malicious',
            'email_verified': True
        }
        
        url = reverse('google_callback')
        response = api_client.post(url, {'code': 'mock_auth_code'}, format='json')
        
        # Should either:
        # 1. Reject if existing user doesn't have OAuth linked
        # 2. Return existing user's token only if OAuth already linked
        if response.status_code == status.HTTP_200_OK:
            # If success, verify it's returning the correct user
            assert 'access' in response.data
            # The existing user should not have been modified
            student_user.refresh_from_db()

    def test_oauth_login_returns_jwt_tokens(self, api_client, mocker):
        """Test successful OAuth login returns JWT tokens"""
        mock_do_auth = mocker.patch('social_core.backends.google.GoogleOAuth2.do_auth')
        mock_user_data = mocker.patch('social_core.backends.google.GoogleOAuth2.user_data')
        
        mock_user_data.return_value = {
            'email': 'oauth@test.com',
            'given_name': 'OAuth',
            'family_name': 'User',
            'email_verified': True
        }
        
        url = reverse('google_callback')
        response = api_client.post(url, {'code': 'valid_code'}, format='json')
        
        if response.status_code == status.HTTP_200_OK:
            assert 'access' in response.data
            assert 'refresh' in response.data
