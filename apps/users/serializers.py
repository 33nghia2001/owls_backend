from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import Users, Address


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details."""
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = Users
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'full_name', 'phone', 'avatar', 'role', 'is_verified',
            'date_joined', 'updated_at'
        ]
        read_only_fields = ['id', 'email', 'role', 'is_verified', 'date_joined']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = Users
        fields = ['email', 'password', 'password_confirm', 'first_name', 'last_name', 'phone']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = Users.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        user = authenticate(email=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")
        
        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        return attrs


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for user addresses with Vietnam-specific fields."""
    
    # Computed fields
    full_address = serializers.ReadOnlyField()
    
    class Meta:
        model = Address
        fields = [
            'id', 'address_type', 'full_name', 'phone', 'street_address',
            'apartment', 
            # New Vietnam-specific fields
            'province', 'province_id', 'district', 'district_id', 
            'ward', 'ward_code',
            # Legacy fields (read-only, for backward compatibility)
            'city', 'state',
            'country', 'postal_code',
            'is_default', 'full_address', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'city', 'state', 'full_address', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        # Ensure Vietnam-specific fields are provided
        if not attrs.get('province'):
            raise serializers.ValidationError({'province': 'Tỉnh/Thành phố là bắt buộc.'})
        if not attrs.get('district'):
            raise serializers.ValidationError({'district': 'Quận/Huyện là bắt buộc.'})
        if not attrs.get('ward'):
            raise serializers.ValidationError({'ward': 'Phường/Xã là bắt buộc.'})
        return attrs
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
