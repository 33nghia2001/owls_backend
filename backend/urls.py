"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

# API v1 URL patterns
api_v1_patterns = [
    # Authentication & Users
    path('', include('apps.users.urls')),
    
    # Vendors
    path('', include('apps.vendors.urls')),
    
    # Products & Categories
    path('', include('apps.products.urls')),
    
    # Shopping
    path('', include('apps.cart.urls')),
    path('', include('apps.wishlist.urls')),
    
    # Orders & Payments
    path('', include('apps.orders.urls')),
    path('', include('apps.payments.urls')),
    
    # Reviews
    path('', include('apps.reviews.urls')),
    
    # Coupons
    path('', include('apps.coupons.urls')),
    
    # Shipping
    path('', include('apps.shipping.urls')),
    
    # Inventory (vendor only)
    path('', include('apps.inventory.urls')),
    
    # Notifications
    path('', include('apps.notifications.urls')),
    
    # Messaging
    path('', include('apps.messaging.urls')),
    
    # Analytics
    path('', include('apps.analytics.urls')),
]

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API v1
    path('api/v1/', include(api_v1_patterns)),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Django Debug Toolbar
    import debug_toolbar
    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
