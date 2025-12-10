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
from apps.reviews.views import ReviewViewSet, InstructorReplyViewSet
from apps.payments.views import PaymentViewSet, DiscountViewSet, VNPayReturnView, VNPayIPNView

# Setup Router
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')
router.register(r'lesson-progress', LessonProgressViewSet, basename='lesson-progress')
router.register(r'quiz-attempts', QuizAttemptViewSet, basename='quiz-attempt')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'instructor-replies', InstructorReplyViewSet, basename='instructor-reply')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'discounts', DiscountViewSet, basename='discount')

urlpatterns = [
    # Secure Admin URL - Changed from default /admin/ to prevent brute-force attacks
    path('quan-tri-vien-secure-8899/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    
    # VNPay Callbacks
    path('api/v1/payments/vnpay/return/', VNPayReturnView.as_view(), name='vnpay-return'),
    path('api/v1/payments/vnpay/ipn/', VNPayIPNView.as_view(), name='vnpay-ipn'),
    
    # Authentication URLs (Login/Refresh)
    path('api/v1/auth/', include('rest_framework.urls')), # Basic auth login/logout
    path('api/v1/token/', include('apps.users.urls')), # JWT authentication
    
    # Notifications & WebSocket
    path('api/v1/notifications/', include('apps.notifications.urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)