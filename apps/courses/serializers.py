from rest_framework import serializers
from .models import Course, Section, Lesson, Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon']

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'lesson_type', 'video_duration', 'is_preview', 'order']

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
        fields = '__all__'
        
    def get_instructor(self, obj):
        return {
            "id": obj.instructor.id,
            "name": obj.instructor.full_name,
            "avatar": obj.instructor.avatar.url if obj.instructor.avatar else None,
            "bio": obj.instructor.bio
        }