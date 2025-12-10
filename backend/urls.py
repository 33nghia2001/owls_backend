from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Import ViewSets
from apps.courses.views import CourseViewSet, CategoryViewSet, LessonViewSet
from apps.reviews.views import ReviewViewSet, InstructorReplyViewSet
from apps.payments.views import VNPayReturnView, VNPayIPNView

# Setup Main Router (courses and reviews only - users/enrollments/payments have their own)
router = DefaultRouter()
router.register(r'courses', CourseViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'instructor-replies', InstructorReplyViewSet, basename='instructor-reply')

urlpatterns = [
    # Secure Admin URL - Changed from default /admin/ to prevent brute-force attacks
    path('quan-tri-vien-secure-8899/', admin.site.urls),
    
    # Main API Routes (courses, categories, lessons, reviews)
    path('api/v1/', include(router.urls)),
    
    # App-specific Routes (with their own routers)
    path('api/v1/', include('apps.users.urls')),  # /api/v1/users/, /api/v1/login/, etc.
    path('api/v1/', include('apps.enrollments.urls')),  # /api/v1/enrollments/
    path('api/v1/', include('apps.payments.urls')),  # /api/v1/payments/
    
    # VNPay Callbacks (special non-REST endpoints)
    path('api/v1/payments/vnpay/return/', VNPayReturnView.as_view(), name='vnpay-return'),
    path('api/v1/payments/vnpay/ipn/', VNPayIPNView.as_view(), name='vnpay-ipn'),
    
    # Notifications & WebSocket
    path('api/v1/notifications/', include('apps.notifications.urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)