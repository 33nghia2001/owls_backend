from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReviewViewSet, VendorReviewViewSet

router = DefaultRouter()
router.register(r'reviews', ReviewViewSet, basename='reviews')
router.register(r'vendor-reviews', VendorReviewViewSet, basename='vendor-reviews')

urlpatterns = [
    path('', include(router.urls)),
]
