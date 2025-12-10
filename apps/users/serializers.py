from rest_framework import serializers
from django.contrib.auth import get_user_model
from turnstile.fields import TurnstileField
from .models import InstructorProfile

User = get_user_model()

class PublicUserSerializer(serializers.ModelSerializer):
    """Serializer cho thông tin user công khai - ẨN email, phone, date_of_birth"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'avatar', 'bio', 'role']
        # KHÔNG BAO GỒM: email, phone, date_of_birth

class UserSerializer(serializers.ModelSerializer):
    """Serializer đầy đủ - CHỈ dùng cho chính user hoặc admin"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'avatar', 'bio']
        read_only_fields = ['role']  # Không cho phép tự đổi role qua API update thường

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    turnstile = TurnstileField()  # Cloudflare Turnstile CAPTCHA

    class Meta:
        model = User
        # Xóa 'role' khỏi fields để user không tự gửi lên được
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'turnstile']
    
    def create(self, validated_data):
        # Remove turnstile from validated_data before creating user
        validated_data.pop('turnstile', None)
        # Mặc định luôn set role là 'student' khi đăng ký qua API này
        validated_data['role'] = 'student'
        user = User.objects.create_user(**validated_data)
        return user

class InstructorProfileSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)  # Dùng PublicUserSerializer thay vì UserSerializer
    class Meta:
        model = InstructorProfile
        fields = '__all__'