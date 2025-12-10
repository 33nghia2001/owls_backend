from rest_framework import viewsets, filters, permissions
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from .models import Course, Category, Lesson
from .serializers import (
    CourseListSerializer, 
    CourseDetailSerializer, 
    CategorySerializer,
    LessonContentSerializer
)
from apps.core.permissions import IsInstructorOrReadOnly, IsEnrolledOrInstructor


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for categories with Redis caching.
    Cache for 30 minutes as categories rarely change.
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    
    @method_decorator(cache_page(60 * 30))  # Cache 30 minutes
    @method_decorator(vary_on_headers('Accept-Language'))
    def list(self, request, *args, **kwargs):
        """Cached category list"""
        return super().list(request, *args, **kwargs)


class CourseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for courses with intelligent caching.
    List view cached for 15 minutes, detail view for 10 minutes.
    """
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

    @method_decorator(cache_page(60 * 15))  # Cache 15 minutes
    def list(self, request, *args, **kwargs):
        """Cached course list"""
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve with caching"""
        slug = kwargs.get('slug')
        cache_key = f'course_detail_{slug}'
        
        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # If not cached, get from DB and cache
        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response, 60 * 10)  # Cache 10 minutes
        return response

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
        from django.db import models
        user = self.request.user
        
        # 1. Instructor xem hết bài học (để quản lý)
        if user.is_authenticated and user.role == 'instructor':
             return Lesson.objects.all()
        
        # 2. Student chỉ xem được bài học của khóa mình ĐÃ MUA (Active) hoặc bài học xem thử
        if user.is_authenticated:
            # Lấy danh sách ID các khóa học đã enroll active
            enrolled_course_ids = user.enrollments.filter(
                status='active'
            ).values_list('course_id', flat=True)
            
            return Lesson.objects.filter(
                models.Q(section__course__id__in=enrolled_course_ids) | 
                models.Q(is_preview=True),
                section__course__status='published'
            ).distinct()
            
        # 3. Anonymous user chỉ thấy bài preview
        return Lesson.objects.filter(is_preview=True, section__course__status='published')