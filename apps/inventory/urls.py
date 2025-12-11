from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InventoryViewSet, InventoryMovementViewSet

router = DefaultRouter()
router.register(r'inventory', InventoryViewSet, basename='inventory')
router.register(r'inventory-movements', InventoryMovementViewSet, basename='inventory-movement')

urlpatterns = [
    path('', include(router.urls)),
]
