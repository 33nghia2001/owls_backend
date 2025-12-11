from rest_framework import serializers
from .models import (
    Category, Brand, Product, ProductImage, ProductAttribute,
    ProductAttributeValue, ProductVariant, ProductVariantAttribute, ProductTag
)
from backend.validators import validate_image_upload
import bleach

# Allowed HTML tags for product descriptions (prevent XSS)
ALLOWED_HTML_TAGS = ['b', 'i', 'u', 'p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'span', 'div']
# SECURITY: Do not allow 'class' attribute as it can enable CSS-based attacks
# Only allow essential safe attributes
ALLOWED_HTML_ATTRS = {'a': ['href', 'title']}


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for categories."""
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'icon', 'parent', 'children', 'is_active']
    
    def get_children(self, obj):
        children = obj.get_children().filter(is_active=True)
        return CategorySerializer(children, many=True).data


class CategoryTreeSerializer(serializers.ModelSerializer):
    """Flat serializer for category selection."""
    full_path = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'full_path', 'level']
    
    def get_full_path(self, obj):
        return ' > '.join([a.name for a in obj.get_ancestors(include_self=True)])


class BrandSerializer(serializers.ModelSerializer):
    """Serializer for brands."""
    
    class Meta:
        model = Brand
        fields = ['id', 'name', 'slug', 'logo', 'description', 'website', 'is_active']


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for product images."""
    
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'order']
    
    def validate_image(self, value):
        """Validate uploaded image file."""
        validate_image_upload(value)
        return value


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    """Serializer for attribute values."""
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    
    class Meta:
        model = ProductAttributeValue
        fields = ['id', 'attribute', 'attribute_name', 'value', 'color_code']


class ProductVariantAttributeSerializer(serializers.ModelSerializer):
    """Serializer for variant attributes."""
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_value = serializers.CharField(source='value.value', read_only=True)
    color_code = serializers.CharField(source='value.color_code', read_only=True)
    
    class Meta:
        model = ProductVariantAttribute
        fields = ['attribute', 'attribute_name', 'value', 'attribute_value', 'color_code']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for product variants."""
    attribute_values = ProductVariantAttributeSerializer(many=True, read_only=True)
    final_price = serializers.ReadOnlyField()
    stock_quantity = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductVariant
        fields = [
            'id', 'sku', 'name', 'price', 'compare_price', 'final_price',
            'image', 'is_active', 'attribute_values', 'stock_quantity'
        ]
    
    def get_stock_quantity(self, obj):
        if hasattr(obj, 'inventory'):
            return obj.inventory.quantity
        return 0


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for product listing."""
    vendor_name = serializers.CharField(source='vendor.shop_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    is_on_sale = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'price', 'compare_price', 'is_on_sale',
            'discount_percentage', 'primary_image', 'vendor_name', 'category_name',
            'rating', 'review_count', 'sold_count', 'is_featured'
        ]
    
    def get_primary_image(self, obj):
        """
        Get primary image without causing N+1 query.
        
        Uses prefetched images from queryset (via prefetch_related('images'))
        and filters in Python instead of making additional DB queries.
        """
        # Access prefetched images via .all() to use cache
        images = obj.images.all()
        
        # Filter in Python (no additional query if images were prefetched)
        primary = next((img for img in images if img.is_primary), None)
        if primary:
            return ProductImageSerializer(primary).data
        
        # Fallback to first image
        first_image = images[0] if images else None
        return ProductImageSerializer(first_image).data if first_image else None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Full serializer for product detail page."""
    vendor = serializers.SerializerMethodField()
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    tags = serializers.SerializerMethodField()
    is_on_sale = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'sku', 'description', 'short_description',
            'price', 'compare_price', 'is_on_sale', 'discount_percentage',
            'status', 'is_featured', 'is_digital',
            'meta_title', 'meta_description',
            'rating', 'review_count', 'sold_count', 'view_count',
            'vendor', 'category', 'brand', 'images', 'variants', 'tags',
            'created_at', 'updated_at'
        ]
    
    def get_vendor(self, obj):
        return {
            'id': obj.vendor.id,
            'shop_name': obj.vendor.shop_name,
            'slug': obj.vendor.slug,
            'logo': obj.vendor.logo.url if obj.vendor.logo else None,
            'rating': obj.vendor.rating
        }
    
    def get_tags(self, obj):
        return [mapping.tag.name for mapping in obj.tag_mappings.all()]


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating products."""
    
    # DoS Prevention: Limit tags per product and tag name length
    MAX_TAGS_PER_PRODUCT = 10
    MAX_TAG_LENGTH = 50
    
    images = ProductImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=MAX_TAG_LENGTH),
        write_only=True,
        required=False,
        max_length=MAX_TAGS_PER_PRODUCT  # Limit number of tags
    )
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'sku', 'description', 'short_description',
            'category', 'brand', 'price', 'compare_price', 'cost_price',
            'status', 'is_featured', 'is_digital',
            'meta_title', 'meta_description',
            'images', 'uploaded_images', 'tags'
        ]
        read_only_fields = ['id', 'slug']
    
    def validate_tags(self, value):
        """
        Validate tags to prevent DoS:
        - Max 10 tags per product
        - Max 50 chars per tag name
        - Remove duplicates
        """
        if not value:
            return value
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in value:
            tag_lower = tag.strip().lower()
            if tag_lower and tag_lower not in seen:
                seen.add(tag_lower)
                unique_tags.append(tag.strip())
        
        if len(unique_tags) > self.MAX_TAGS_PER_PRODUCT:
            raise serializers.ValidationError(
                f"Maximum {self.MAX_TAGS_PER_PRODUCT} tags allowed per product."
            )
        
        return unique_tags
    
    def validate_description(self, value):
        """Sanitize HTML in product description to prevent XSS attacks."""
        if value:
            return bleach.clean(value, tags=ALLOWED_HTML_TAGS, attributes=ALLOWED_HTML_ATTRS, strip=True)
        return value
    
    def validate_short_description(self, value):
        """Sanitize HTML in short description to prevent XSS attacks."""
        if value:
            return bleach.clean(value, tags=ALLOWED_HTML_TAGS, attributes=ALLOWED_HTML_ATTRS, strip=True)
        return value
    
    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        tags = validated_data.pop('tags', [])
        
        validated_data['vendor'] = self.context['request'].user.vendor_profile
        product = super().create(validated_data)
        
        # Create images
        for i, image in enumerate(uploaded_images):
            ProductImage.objects.create(
                product=product,
                image=image,
                is_primary=(i == 0),
                order=i
            )
        
        # Create tags
        for tag_name in tags:
            tag, _ = ProductTag.objects.get_or_create(name=tag_name)
            product.tag_mappings.create(tag=tag)
        
        return product
    
    def update(self, instance, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        tags = validated_data.pop('tags', None)
        
        instance = super().update(instance, validated_data)
        
        # Add new images
        if uploaded_images:
            max_order = instance.images.count()
            for i, image in enumerate(uploaded_images):
                ProductImage.objects.create(
                    product=instance,
                    image=image,
                    order=max_order + i
                )
        
        # Update tags
        if tags is not None:
            instance.tag_mappings.all().delete()
            for tag_name in tags:
                tag, _ = ProductTag.objects.get_or_create(name=tag_name)
                instance.tag_mappings.create(tag=tag)
        
        return instance


class ProductAttributeSerializer(serializers.ModelSerializer):
    """Serializer for product attributes."""
    values = ProductAttributeValueSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProductAttribute
        fields = ['id', 'name', 'slug', 'values']


class ProductTagSerializer(serializers.ModelSerializer):
    """Serializer for product tags."""
    
    class Meta:
        model = ProductTag
        fields = ['id', 'name', 'slug']
