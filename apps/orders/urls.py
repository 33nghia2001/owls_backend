from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, VendorOrderViewSet, RefundRequestViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'vendor-orders', VendorOrderViewSet, basename='vendor-orders')
router.register(r'refunds', RefundRequestViewSet, basename='refunds')

urlpatterns = [
    path('', include(router.urls)),
]
