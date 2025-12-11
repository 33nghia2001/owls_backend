from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShippingMethodViewSet, ShipmentViewSet

router = DefaultRouter()
router.register(r'shipping-methods', ShippingMethodViewSet, basename='shipping-methods')
router.register(r'shipments', ShipmentViewSet, basename='shipments')

urlpatterns = [
    path('', include(router.urls)),
]
