from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VendorAnalyticsViewSet, AdminAnalyticsViewSet

router = DefaultRouter()
router.register(r'vendor-analytics', VendorAnalyticsViewSet, basename='vendor-analytics')
router.register(r'admin-analytics', AdminAnalyticsViewSet, basename='admin-analytics')

urlpatterns = [
    path('', include(router.urls)),
]
