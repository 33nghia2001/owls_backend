from rest_framework import viewsets, filters, permissions
from django_filters.rest_framework import DjangoFilterBackend
from .models import Course, Category, Lesson
from .serializers import CourseListSerializer, CourseDetailSerializer, CategorySerializer
from apps.core.permissions import IsInstructorOrReadOnly

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
        # Instructor thấy hết course của họ, User thường chỉ thấy course đã publish
        user = self.request.user
        if user.is_authenticated and user.role == 'instructor' and self.action in ['update', 'partial_update', 'destroy']:
             return Course.objects.filter(instructor=user)
        return Course.objects.filter(status='published')

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)