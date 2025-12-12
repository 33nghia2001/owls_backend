from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ShippingMethodViewSet, ShipmentViewSet, get_provinces,
    get_ghn_provinces, get_ghn_districts, get_ghn_wards,
    calculate_shipping_fee, track_shipment
)

router = DefaultRouter()
router.register(r'shipping-methods', ShippingMethodViewSet, basename='shipping-methods')
router.register(r'shipments', ShipmentViewSet, basename='shipments')

urlpatterns = [
    path('', include(router.urls)),
    path('provinces/', get_provinces, name='provinces'),
    
    # GHN location APIs for address forms
    path('ghn/provinces/', get_ghn_provinces, name='ghn-provinces'),
    path('ghn/districts/', get_ghn_districts, name='ghn-districts'),
    path('ghn/wards/', get_ghn_wards, name='ghn-wards'),
    
    # Shipping fee calculation
    path('calculate-fee/', calculate_shipping_fee, name='calculate-shipping-fee'),
    
    # Real-time tracking
    path('track/', track_shipment, name='track-shipment'),
]
