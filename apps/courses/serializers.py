from rest_framework import serializers
from .models import Course, Section, Lesson, Category, Resource
from .utils import generate_signed_video_url, generate_signed_resource_url

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon']

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'lesson_type', 'video_duration', 'is_preview', 'order']


class ResourceSerializer(serializers.ModelSerializer):
    """Serializer cho tài liệu đính kèm"""
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Resource
        fields = ['id', 'title', 'file_url', 'file_size']
    
    def get_file_url(self, obj):
        """Return signed URL with 24-hour expiration for security"""
        if obj.file:
            # Extract public_id from Cloudinary field
            return generate_signed_resource_url(obj.file.public_id, duration_hours=24)
        return obj.file_url  # Fallback to regular URL if exists


class LessonContentSerializer(serializers.ModelSerializer):
    """
    Serializer đầy đủ nội dung bài học, chỉ dùng cho người đã đăng ký.
    Trả về video_url có chữ ký (signed URL) để bảo mật.
    """
    resources = ResourceSerializer(many=True, read_only=True)
    video_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content', 'video_url', 'video_duration', 
                  'lesson_type', 'is_preview', 'order', 'resources']
    
    def get_video_url(self, obj):
        """
        Return signed video URL with 1-hour expiration.
        Prevents unauthorized sharing and direct video piracy.
        """
        if obj.video_url and obj.video_url.startswith('http'):
            # If it's a Cloudinary video, generate signed URL
            # Extract public_id from URL (simplified - adjust based on your URL structure)
            return generate_signed_video_url(obj.video_url, duration_hours=1)
        return obj.video_url  # Fallback for external URLs

class SectionSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    
    class Meta:
        model = Section
        fields = ['id', 'title', 'order', 'lessons']

class CourseListSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Course
        fields = ['id', 'title', 'slug', 'thumbnail', 'price', 'instructor_name', 'category_name', 'average_rating', 'level']

class CourseDetailSerializer(serializers.ModelSerializer):
    sections = SectionSerializer(many=True, read_only=True)
    instructor = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        # SECURITY FIX: Explicit fields to prevent accidental exposure of internal fields
        # Never use '__all__' in production - future fields may contain sensitive data
        fields = [
            'id', 'title', 'slug', 'description', 'thumbnail', 'price', 
            'discount_price', 'level', 'language', 'category', 'instructor',
            'average_rating', 'total_students', 'total_reviews', 'duration',
            'what_you_will_learn', 'requirements', 'target_audience',
            'is_published', 'created_at', 'updated_at', 'sections'
        ]
        
    def get_instructor(self, obj):
        return {
            "id": obj.instructor.id,
            "name": obj.instructor.full_name,
            "avatar": obj.instructor.avatar.url if obj.instructor.avatar else None,
            "bio": obj.instructor.bio
        }