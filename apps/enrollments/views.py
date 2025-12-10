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
    """
    ViewSet for managing course enrollments.
    
    SECURITY: Users can only view their own enrollments (list/retrieve).
    CREATE is BLOCKED for regular users to prevent free enrollment bypass.
    Only Admins can manually create enrollments (for special cases like refunds, gifts, etc.)
    Normal enrollment flow: User pays via Payment API -> System creates Enrollment automatically.
    """
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    # SECURITY FIX: Disable create/update/delete for non-admin users
    http_method_names = ['get', 'post', 'head', 'options']  # Allow POST only for custom actions

    def get_queryset(self):
        """
        Get enrollments for current user (or all for admin).
        
        PERFORMANCE FIX: Use select_related to prevent N+1 queries when
        serializer accesses course.instructor and course.category.
        """
        if self.request.user.is_staff:
            # Admin can see all enrollments
            return Enrollment.objects.all().select_related(
                'course',
                'course__instructor',
                'course__category',
                'student'
            )
        
        # Regular users only see their own enrollments
        return Enrollment.objects.filter(student=self.request.user).select_related(
            'course',
            'course__instructor',  # Prevent N+1 for instructor_name in serializer
            'course__category'      # Prevent N+1 for category_name in serializer
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EnrollmentDetailSerializer
        return EnrollmentSerializer

    def create(self, request, *args, **kwargs):
        """
        SECURITY: Block public enrollment creation to prevent payment bypass.
        
        Enrollments are created automatically by the payment system when payment succeeds.
        Only admins can manually create enrollments for special cases.
        """
        if not request.user.is_staff:
            return Response(
                {
                    'error': 'Direct enrollment is not allowed',
                    'message': 'Please complete payment via /api/v1/payments/ to enroll in a course',
                    'detail': 'Enrollments are created automatically after successful payment'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Admin can create enrollment manually (for special cases: refunds, gifts, etc.)
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """
        Admin-only manual enrollment creation.
        Auto-assigns student from request if not specified.
        """
        # If admin doesn't specify student, use current user
        if 'student' not in serializer.validated_data:
            serializer.save(student=self.request.user)
        else:
            serializer.save()

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

