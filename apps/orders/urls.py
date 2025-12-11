from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, VendorOrderViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'vendor-orders', VendorOrderViewSet, basename='vendor-orders')

urlpatterns = [
    path('', include(router.urls)),
]
