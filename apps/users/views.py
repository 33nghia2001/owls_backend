from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import logout
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

from .models import Users, Address
from .serializers import (
    UserSerializer, UserRegistrationSerializer, UserLoginSerializer,
    ChangePasswordSerializer, AddressSerializer
)

logger = logging.getLogger(__name__)


# Cookie settings for JWT tokens
JWT_COOKIE_SECURE = not settings.DEBUG  # True in production (HTTPS only)
JWT_COOKIE_HTTPONLY = True
# SECURITY: For cross-domain (frontend on Netlify, backend on Koyeb),
# we need SameSite='None' with Secure=True to allow cookies in cross-origin requests.
# In development (same origin), 'Lax' works fine.
JWT_COOKIE_SAMESITE = 'None' if not settings.DEBUG else 'Lax'
JWT_ACCESS_COOKIE_NAME = 'access_token'
JWT_REFRESH_COOKIE_NAME = 'refresh_token'
JWT_ACCESS_MAX_AGE = 60 * 15  # 15 minutes
JWT_REFRESH_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def set_jwt_cookies(response, access_token, refresh_token):
    """Helper function to set JWT tokens as httpOnly cookies."""
    response.set_cookie(
        JWT_ACCESS_COOKIE_NAME,
        access_token,
        max_age=JWT_ACCESS_MAX_AGE,
        httponly=JWT_COOKIE_HTTPONLY,
        secure=JWT_COOKIE_SECURE,
        samesite=JWT_COOKIE_SAMESITE,
        path='/',
    )
    response.set_cookie(
        JWT_REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=JWT_REFRESH_MAX_AGE,
        httponly=JWT_COOKIE_HTTPONLY,
        secure=JWT_COOKIE_SECURE,
        samesite=JWT_COOKIE_SAMESITE,
        path='/',  # Set to root path so it's sent with all API requests
    )
    return response


def clear_jwt_cookies(response):
    """Helper function to clear JWT cookies on logout."""
    response.delete_cookie(JWT_ACCESS_COOKIE_NAME, path='/')
    response.delete_cookie(JWT_REFRESH_COOKIE_NAME, path='/')
    return response


class LoginRateThrottle(ScopedRateThrottle):
    """Custom throttle for login attempts to prevent brute force."""
    scope = 'login'


class RegistrationRateThrottle(ScopedRateThrottle):
    """Custom throttle for registration to prevent spam accounts."""
    scope = 'registration'


class AuthViewSet(viewsets.ViewSet):
    """ViewSet for authentication endpoints."""
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'], throttle_classes=[RegistrationRateThrottle])
    def register(self, request):
        """Register a new user."""
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        response = Response({
            'user': UserSerializer(user).data,
            'message': 'Registration successful',
        }, status=status.HTTP_201_CREATED)
        
        # Set httpOnly cookies
        return set_jwt_cookies(response, access_token, refresh_token)
    
    @action(detail=False, methods=['post'], throttle_classes=[LoginRateThrottle])
    def login(self, request):
        """Login user and return tokens in httpOnly cookies."""
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        response = Response({
            'user': UserSerializer(user).data,
            'message': 'Login successful',
        })
        
        # Set httpOnly cookies
        return set_jwt_cookies(response, access_token, refresh_token)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """Logout user, blacklist refresh token and clear cookies."""
        try:
            # Try to get refresh token from cookie first, then from body
            refresh_token = request.COOKIES.get(JWT_REFRESH_COOKIE_NAME) or request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass  # Token might be invalid or already blacklisted
        
        response = Response({'message': 'Successfully logged out.'})
        return clear_jwt_cookies(response)
    
    @action(detail=False, methods=['post'])
    def token_refresh(self, request):
        """Refresh access token using refresh token from httpOnly cookie."""
        # Get refresh token from cookie first, then from body (for backward compatibility)
        refresh_token = request.COOKIES.get(JWT_REFRESH_COOKIE_NAME) or request.data.get('refresh')
        
        # Debug logging
        if settings.DEBUG:
            print(f"[TOKEN_REFRESH] Cookies received: {list(request.COOKIES.keys())}")
            print(f"[TOKEN_REFRESH] Refresh token present: {bool(refresh_token)}")
        
        if not refresh_token:
            return Response(
                {'detail': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)
            new_refresh_token = str(refresh)  # New token if ROTATE_REFRESH_TOKENS is True
            
            response = Response({
                'message': 'Token refreshed successfully',
            })
            
            # Set new httpOnly cookies
            return set_jwt_cookies(response, access_token, new_refresh_token)
        except Exception:
            response = Response(
                {'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
            # Clear invalid cookies
            return clear_jwt_cookies(response)
    
    @action(detail=False, methods=['post'], throttle_classes=[LoginRateThrottle])
    def forgot_password(self, request):
        """
        Send password reset email.
        Rate limited to prevent email enumeration/spam.
        """
        email = request.data.get('email', '').lower().strip()
        
        if not email:
            return Response(
                {'error': 'Email là bắt buộc.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Always return success to prevent email enumeration
        # But only send email if user exists
        try:
            user = Users.objects.get(email__iexact=email)
            
            # Generate password reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Build reset URL
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
            reset_url = f"{frontend_url}/auth/reset-password?uid={uid}&token={token}"
            
            # Send email (async in production via Celery)
            try:
                subject = "Đặt lại mật khẩu - OWLS Marketplace"
                message = f"""
Xin chào {user.full_name or user.email},

Bạn đã yêu cầu đặt lại mật khẩu cho tài khoản OWLS Marketplace.

Nhấn vào liên kết sau để đặt lại mật khẩu:
{reset_url}

Liên kết này sẽ hết hạn sau 24 giờ.

Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.

Trân trọng,
OWLS Marketplace Team
                """.strip()
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True
                )
                logger.info(f"Password reset email sent to {email}")
            except Exception as e:
                logger.error(f"Failed to send password reset email to {email}: {e}")
                
        except Users.DoesNotExist:
            # Don't reveal that user doesn't exist
            logger.info(f"Password reset requested for non-existent email: {email}")
        
        return Response({
            'message': 'Nếu email tồn tại trong hệ thống, bạn sẽ nhận được hướng dẫn đặt lại mật khẩu.'
        })
    
    @action(detail=False, methods=['post'])
    def reset_password(self, request):
        """
        Reset password using token from email.
        """
        uid = request.data.get('uid')
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        
        if not all([uid, token, new_password]):
            return Response(
                {'error': 'Thiếu thông tin bắt buộc.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate password length
        if len(new_password) < 8:
            return Response(
                {'error': 'Mật khẩu phải có ít nhất 8 ký tự.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Decode user id
            user_id = force_str(urlsafe_base64_decode(uid))
            user = Users.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, Users.DoesNotExist):
            return Response(
                {'error': 'Liên kết đặt lại mật khẩu không hợp lệ.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify token
        if not default_token_generator.check_token(user, token):
            return Response(
                {'error': 'Liên kết đặt lại mật khẩu đã hết hạn hoặc không hợp lệ.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        logger.info(f"Password reset successful for user {user.email}")
        
        return Response({
            'message': 'Đặt lại mật khẩu thành công. Vui lòng đăng nhập với mật khẩu mới.'
        })


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for user management."""
    queryset = Users.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Users.objects.all()
        return Users.objects.filter(id=user.id)
    
    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        """Get or update current user profile."""
        if request.method == 'GET':
            serializer = UserSerializer(request.user)
            return Response(serializer.data)
        
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def upload_avatar(self, request):
        """Upload user avatar image."""
        if 'avatar' not in request.FILES:
            return Response(
                {'error': 'Vui lòng chọn file ảnh để upload.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        avatar_file = request.FILES['avatar']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if avatar_file.content_type not in allowed_types:
            return Response(
                {'error': 'Chỉ chấp nhận file ảnh (JPEG, PNG, GIF, WebP).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if avatar_file.size > max_size:
            return Response(
                {'error': 'Kích thước file không được vượt quá 5MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete old avatar if exists
        user = request.user
        if user.avatar:
            user.avatar.delete(save=False)
        
        # Save new avatar
        user.avatar = avatar_file
        user.save()
        
        return Response({
            'message': 'Upload ảnh đại diện thành công.',
            'avatar': user.avatar.url if user.avatar else None
        })
    
    @action(detail=False, methods=['delete'])
    def delete_avatar(self, request):
        """Delete user avatar."""
        user = request.user
        if user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None
            user.save()
            return Response({'message': 'Đã xóa ảnh đại diện.'})
        return Response({'message': 'Không có ảnh đại diện để xóa.'})
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change user password."""
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({'message': 'Password changed successfully.'})
    
    @action(detail=False, methods=['post'])
    def delete_account(self, request):
        """
        Delete user account with all associated data.
        Requires password confirmation.
        """
        password = request.data.get('password')
        
        if not password:
            return Response(
                {'error': 'Vui lòng nhập mật khẩu để xác nhận xóa tài khoản.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        
        # Verify password
        if not user.check_password(password):
            return Response(
                {'error': 'Mật khẩu không đúng.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for active orders
        from apps.orders.models import Order
        active_orders = Order.objects.filter(
            user=user,
            status__in=['pending', 'confirmed', 'processing', 'shipped']
        ).exists()
        
        if active_orders:
            return Response(
                {'error': 'Bạn không thể xóa tài khoản khi còn đơn hàng đang xử lý. Vui lòng đợi đơn hàng hoàn tất hoặc hủy đơn trước.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is a vendor
        from apps.vendors.models import Vendor
        try:
            vendor = Vendor.objects.get(user=user)
            if vendor.status == 'approved':
                # Check for pending vendor orders
                vendor_orders = Order.objects.filter(
                    items__product__vendor=vendor,
                    status__in=['pending', 'confirmed', 'processing', 'shipped']
                ).exists()
                
                if vendor_orders:
                    return Response(
                        {'error': 'Bạn không thể xóa tài khoản khi cửa hàng còn đơn hàng đang xử lý.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        except Vendor.DoesNotExist:
            pass
        
        # Store email for logging
        user_email = user.email
        
        # Delete avatar if exists
        if user.avatar:
            user.avatar.delete(save=False)
        
        # Anonymize instead of hard delete (for data integrity)
        # Option 1: Hard delete - will cascade
        # user.delete()
        
        # Option 2: Soft delete / Anonymize (recommended for e-commerce)
        user.is_active = False
        user.email = f"deleted_{user.id}@deleted.owls"
        user.first_name = "Deleted"
        user.last_name = "User"
        user.phone_number = ""
        user.avatar = None
        user.save()
        
        # Delete all addresses
        Address.objects.filter(user=user).delete()
        
        logger.info(f"Account deleted/deactivated for user: {user_email}")
        
        return Response({
            'message': 'Tài khoản của bạn đã được xóa thành công.'
        })


class AddressViewSet(viewsets.ModelViewSet):
    """ViewSet for user addresses."""
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set address as default."""
        address = self.get_object()
        address.is_default = True
        address.save()
        return Response(AddressSerializer(address).data)
