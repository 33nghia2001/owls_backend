from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer, RegisterSerializer, CustomTokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterThrottle(AnonRateThrottle):
    """Custom throttle cho registration - 5 lần/giờ"""
    scope = 'register'


class LoginRateThrottle(AnonRateThrottle):
    """Throttle cho login - Chỉ cho phép 5 lần thử đăng nhập mỗi phút từ 1 IP"""
    rate = '5/min'


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_permissions(self):
        if self.action == 'create': # Đăng ký
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
    
    def get_throttles(self):
        """Áp dụng throttle cho registration"""
        if self.action == 'create':
            return [RegisterThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action == 'create':
            return RegisterSerializer
        return UserSerializer

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        """API để lấy hoặc cập nhật thông tin cá nhân của user đang login"""
        user = request.user
        if request.method == 'GET':
            serializer = self.get_serializer(user)
            return Response(serializer.data)
        elif request.method == 'PATCH':
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    API Đăng nhập tùy chỉnh:
    - Có Captcha (qua Serializer)
    - Có Rate Limit (5 request/phút)
    - Trả về Access Token + Refresh Token + User Info
    """
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]


class LogoutView(APIView):
    """
    API Logout - Blacklist refresh token để vô hiệu hóa hoàn toàn.
    Ngăn chặn "Zombie Token" attack.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {"message": "Successfully logged out"},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return Response(
                {"error": "Invalid token or already blacklisted"},
                status=status.HTTP_400_BAD_REQUEST
            )