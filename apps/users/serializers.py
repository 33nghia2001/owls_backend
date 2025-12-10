from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import InstructorProfile

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'avatar', 'bio']
        read_only_fields = ['role']  # Không cho phép tự đổi role qua API update thường

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        # Xóa 'role' khỏi fields để user không tự gửi lên được
        fields = ['username', 'email', 'password', 'first_name', 'last_name']
    
    def create(self, validated_data):
        # Mặc định luôn set role là 'student' khi đăng ký qua API này
        validated_data['role'] = 'student'
        user = User.objects.create_user(**validated_data)
        return user

class InstructorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = InstructorProfile
        fields = '__all__'