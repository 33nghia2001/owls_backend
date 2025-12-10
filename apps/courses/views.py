from rest_framework import viewsets, filters, permissions
from django_filters.rest_framework import DjangoFilterBackend
from .models import Course, Category, Lesson
from .serializers import (
    CourseListSerializer, 
    CourseDetailSerializer, 
    CategorySerializer,
    LessonContentSerializer
)
from apps.core.permissions import IsInstructorOrReadOnly, IsEnrolledOrInstructor

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.filter(status='published')
    permission_classes = [IsInstructorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'level', 'is_free']
    search_fields = ['title', 'description']
    ordering_fields = ['price', 'average_rating', 'created_at']
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseListSerializer

    def get_queryset(self):
        user = self.request.user
        
        # Base query
        queryset = Course.objects.all()

        # Tối ưu hóa query: Load trước sections và lessons để tránh lỗi N+1
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related('sections', 'sections__lessons')

        # Logic lọc theo role (áp dụng lên queryset đã tối ưu)
        if user.is_authenticated and user.role == 'instructor' and self.action in ['update', 'partial_update', 'destroy']:
             return queryset.filter(instructor=user)
        
        return queryset.filter(status='published')

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)


class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet để phục vụ việc học - xem nội dung bài học.
    Chỉ cho phép xem nếu:
    - Là instructor/admin
    - Bài học là preview
    - Đã đăng ký khóa học (enrollment active)
    """
    queryset = Lesson.objects.all()
    serializer_class = LessonContentSerializer
    permission_classes = [permissions.IsAuthenticated, IsEnrolledOrInstructor]

    def get_queryset(self):
        # Chỉ trả về các bài học thuộc khóa học published (trừ khi là instructor)
        if self.request.user.is_authenticated and self.request.user.role == 'instructor':
             return Lesson.objects.all()
        return Lesson.objects.filter(section__course__status='published')