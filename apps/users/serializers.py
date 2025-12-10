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
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'role']
    
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class InstructorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = InstructorProfile
        fields = '__all__'