from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VendorViewSet, VendorBankAccountViewSet, VendorPayoutViewSet

router = DefaultRouter()
router.register(r'vendors', VendorViewSet, basename='vendors')
router.register(r'bank-accounts', VendorBankAccountViewSet, basename='bank-accounts')
router.register(r'payouts', VendorPayoutViewSet, basename='payouts')

urlpatterns = [
    path('', include(router.urls)),
]
