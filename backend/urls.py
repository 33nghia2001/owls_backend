from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Import ViewSets
from apps.users.views import UserViewSet
from apps.courses.views import CourseViewSet, CategoryViewSet, LessonViewSet
from apps.enrollments.views import EnrollmentViewSet, LessonProgressViewSet, QuizAttemptViewSet

# Setup Router
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')
router.register(r'lesson-progress', LessonProgressViewSet, basename='lesson-progress')
router.register(r'quiz-attempts', QuizAttemptViewSet, basename='quiz-attempt')
# Bạn sẽ register thêm reviews, payments tại đây sau này

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    
    # Authentication URLs (Login/Refresh)
    path('api/v1/auth/', include('rest_framework.urls')), # Basic auth login/logout
    path('api/v1/token/', include('apps.users.urls')), # Cần tạo file urls trong users cho JWT nếu chưa có
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)