from rest_framework import serializers
from .models import Enrollment, LessonProgress, QuizAttempt
from apps.courses.serializers import CourseListSerializer


class LessonProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = ['id', 'lesson', 'is_completed', 'time_spent', 'last_position', 'completed_at']
        read_only_fields = ['completed_at']


class EnrollmentSerializer(serializers.ModelSerializer):
    course_detail = CourseListSerializer(source='course', read_only=True)
    
    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'course', 'course_detail', 'status', 'progress_percentage', 
                  'completed_lessons_count', 'enrolled_at', 'completed_at']
        read_only_fields = ['student', 'status', 'progress_percentage', 'completed_lessons_count', 
                           'enrolled_at', 'completed_at']


class EnrollmentDetailSerializer(serializers.ModelSerializer):
    course_detail = CourseListSerializer(source='course', read_only=True)
    lesson_progress = LessonProgressSerializer(many=True, read_only=True)
    
    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'course', 'course_detail', 'status', 'progress_percentage',
                  'completed_lessons_count', 'total_time_spent', 'lesson_progress',
                  'enrolled_at', 'completed_at', 'last_accessed_at', 'certificate_issued']
        read_only_fields = ['student', 'status', 'progress_percentage', 'completed_lessons_count',
                           'total_time_spent', 'enrolled_at', 'completed_at', 'last_accessed_at',
                           'certificate_issued']


class QuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttempt
        fields = ['id', 'enrollment', 'quiz', 'score', 'max_score', 'passed', 
                  'answers', 'time_taken', 'started_at', 'completed_at']
        read_only_fields = ['enrollment', 'started_at', 'completed_at']
