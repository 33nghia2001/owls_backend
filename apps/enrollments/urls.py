from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EnrollmentViewSet, LessonProgressViewSet, QuizAttemptViewSet

router = DefaultRouter()
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')
router.register(r'lesson-progress', LessonProgressViewSet, basename='lesson-progress')
router.register(r'quiz-attempts', QuizAttemptViewSet, basename='quiz-attempt')

urlpatterns = [
    path('', include(router.urls)),
]
