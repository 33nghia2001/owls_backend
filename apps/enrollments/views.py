from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Enrollment, LessonProgress, QuizAttempt
from .serializers import (
    EnrollmentSerializer, 
    EnrollmentDetailSerializer,
    LessonProgressSerializer,
    QuizAttemptSerializer
)
from apps.courses.models import Course, Lesson


class EnrollmentViewSet(viewsets.ModelViewSet):
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Get enrollments for current user.
        
        PERFORMANCE FIX: Use select_related to prevent N+1 queries when
        serializer accesses course.instructor and course.category.
        """
        return Enrollment.objects.filter(student=self.request.user).select_related(
            'course',
            'course__instructor',  # Prevent N+1 for instructor_name in serializer
            'course__category'      # Prevent N+1 for category_name in serializer
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EnrollmentDetailSerializer
        return EnrollmentSerializer

    def perform_create(self, serializer):
        # Tự động gán student là user đang login
        # Logic thực tế: Phải kiểm tra Payment trước khi tạo Enrollment (sẽ làm sau)
        # Tạm thời cho phép đăng ký free để test
        course = serializer.validated_data['course']
        
        # Kiểm tra xem đã đăng ký chưa - Chỉ chặn nếu đang active hoặc đã hoàn thành
        if Enrollment.objects.filter(
            student=self.request.user, 
            course=course,
            status__in=['active', 'completed']  # Chỉ chặn nếu đang học hoặc đã học xong
        ).exists():
            return Response(
                {'error': 'You are already active in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save(student=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_lesson_complete(self, request, pk=None):
        """Mark a lesson as completed"""
        enrollment = self.get_object()
        lesson_id = request.data.get('lesson_id')
        
        if not lesson_id:
            return Response({'error': 'lesson_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # Kiểm tra xem bài học này có thuộc khóa học đang enroll không
        if lesson.section.course_id != enrollment.course_id:
            return Response(
                {'error': 'This lesson does not belong to the enrolled course'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Tạo hoặc cập nhật lesson progress
        progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson
        )
        
        if not progress.is_completed:
            progress.mark_as_completed()
        
        serializer = LessonProgressSerializer(progress)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get detailed progress for an enrollment"""
        enrollment = self.get_object()
        lesson_progress = enrollment.lesson_progress.all()
        serializer = LessonProgressSerializer(lesson_progress, many=True)
        return Response({
            'enrollment_id': enrollment.id,
            'progress_percentage': enrollment.progress_percentage,
            'completed_lessons': enrollment.completed_lessons_count,
            'lesson_progress': serializer.data
        })


class LessonProgressViewSet(viewsets.ReadOnlyModelViewSet):
    """View for lesson progress"""
    serializer_class = LessonProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LessonProgress.objects.filter(enrollment__student=self.request.user)


class QuizAttemptViewSet(viewsets.ModelViewSet):
    """View for quiz attempts"""
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return QuizAttempt.objects.filter(enrollment__student=self.request.user)

