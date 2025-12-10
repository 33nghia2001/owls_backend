from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, DiscountViewSet

router = DefaultRouter()
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'discounts', DiscountViewSet, basename='discount')

urlpatterns = [
    path('', include(router.urls)),
]
