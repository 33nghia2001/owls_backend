from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, BrandViewSet, ProductViewSet,
    ProductImageViewSet, ProductAttributeViewSet, ProductTagViewSet
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'brands', BrandViewSet, basename='brands')
router.register(r'products', ProductViewSet, basename='products')
router.register(r'product-images', ProductImageViewSet, basename='product-images')
router.register(r'attributes', ProductAttributeViewSet, basename='attributes')
router.register(r'tags', ProductTagViewSet, basename='tags')

urlpatterns = [
    path('', include(router.urls)),
]
