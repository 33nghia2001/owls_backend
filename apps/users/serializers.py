from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
# Đảm bảo bạn đã cài đặt thư viện hỗ trợ turnstile
from turnstile.fields import TurnstileField 

from .models import InstructorProfile

User = get_user_model()

# ==========================================
# User Serializers
# ==========================================

class PublicUserSerializer(serializers.ModelSerializer):
    """
    Serializer cho thông tin user công khai.
    Sử dụng khi hiển thị thông tin tác giả, giảng viên cho người lạ xem.
    Tuyệt đối KHÔNG trả về: email, phone, date_of_birth.
    """
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 
            'avatar', 'bio', 'role'
        ]
        # Đặt read_only để đảm bảo an toàn tuyệt đối
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer đầy đủ thông tin User.
    CHỈ DÙNG cho chính user đó (khi xem profile của mình) hoặc Admin.
    
    SECURITY FIX: Email is read-only to prevent account takeover.
    Users must verify new email before changing (implement separate email change flow).
    """
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'role', 'avatar', 'bio'
        ]
        # Role and email are read-only to prevent privilege escalation and account takeover
        read_only_fields = ['role', 'email']


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer dùng riêng cho endpoint Đăng ký.
    Bao gồm validation mật khẩu và Captcha.
    """
    password = serializers.CharField(
        write_only=True, 
        min_length=8, 
        style={'input_type': 'password'}
    )
    turnstile = TurnstileField()  # Cloudflare Turnstile CAPTCHA

    class Meta:
        model = User
        # Chỉ liệt kê các trường cần thiết khi đăng ký
        fields = [
            'username', 'email', 'password', 
            'first_name', 'last_name', 'turnstile'
        ]
    
    def create(self, validated_data):
        # 1. Loại bỏ field turnstile vì nó không nằm trong User model
        validated_data.pop('turnstile', None)
        
        # 2. Fix cứng role là 'student' để tránh leo thang đặc quyền
        validated_data['role'] = 'student'
        
        # 3. Tạo user với password đã được hash
        user = User.objects.create_user(**validated_data)
        
        return user


# ==========================================
# Profile Serializers
# ==========================================

class InstructorProfileSerializer(serializers.ModelSerializer):
    """
    Serializer cho hồ sơ giảng viên.
    Nhúng PublicUserSerializer để hiển thị thông tin user an toàn.
    """
    user = PublicUserSerializer(read_only=True)
    
    class Meta:
        model = InstructorProfile
        # Nên liệt kê field cụ thể thay vì '__all__' để kiểm soát dữ liệu đầu ra tốt hơn
        fields = [
            'id', 'user', 'title', 'expertise', 'experience_years',
            'total_students', 'total_courses', 'average_rating',
            'is_verified', 'verified_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'total_students', 'total_courses', 'average_rating', 
            'is_verified', 'verified_at', 'created_at', 'updated_at'
        ]


# ==========================================
# JWT Authentication Serializers
# ==========================================

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Login Serializer tùy chỉnh:
    1. Thêm Turnstile (Captcha) để chống Brute-force.
    2. Trả về thêm thông tin user trong response.
    """
    turnstile = TurnstileField(write_only=True)

    def validate(self, attrs):
        # 1. TurnstileField sẽ tự động validate token ở đây.
        # Nếu token sai, nó sẽ raise ValidationError ngay lập tức.
        
        # Xóa trường turnstile khỏi attrs trước khi đưa cho parent class xử lý login
        attrs.pop('turnstile', None)

        # 2. Gọi logic login mặc định (check username/password)
        data = super().validate(attrs)

        # 3. Custom Response: Thêm thông tin user vào JSON trả về
        # self.user được gán tự động sau khi validate thành công
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'role': self.user.role,
            'avatar': self.user.avatar.url if self.user.avatar else None,
        }

        return data