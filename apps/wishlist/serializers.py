from rest_framework import serializers
from .models import Wishlist, WishlistItem
from apps.products.serializers import ProductListSerializer


class WishlistItemSerializer(serializers.ModelSerializer):
    """Serializer for wishlist items."""
    product = ProductListSerializer(read_only=True)
    product_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = WishlistItem
        fields = ['id', 'product', 'product_id', 'note', 'added_at']
        read_only_fields = ['id', 'added_at']


class WishlistSerializer(serializers.ModelSerializer):
    """Serializer for wishlists."""
    items = WishlistItemSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Wishlist
        fields = ['id', 'name', 'is_public', 'items', 'items_count', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_items_count(self, obj):
        return obj.items.count()
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
