from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from .serializers import UserSerializer, RegisterSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterThrottle(AnonRateThrottle):
    """Custom throttle cho registration - 5 lần/giờ"""
    scope = 'register'


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