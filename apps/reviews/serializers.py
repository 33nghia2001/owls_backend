from rest_framework import serializers
from .models import Review, ReviewImage, ReviewHelpful, VendorReview
from apps.orders.models import OrderItem
import bleach


class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ['id', 'image']


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for product reviews."""
    user_name = serializers.SerializerMethodField()
    user_avatar = serializers.SerializerMethodField()
    images = ReviewImageSerializer(many=True, read_only=True)
    is_helpful = serializers.SerializerMethodField()
    is_verified_purchase = serializers.SerializerMethodField()
    
    class Meta:
        model = Review
        fields = [
            'id', 'user_name', 'user_avatar', 'rating', 'title', 'comment',
            'images', 'helpful_count', 'is_helpful', 'is_verified_purchase', 'created_at'
        ]
    
    def get_user_name(self, obj):
        return obj.user.full_name or obj.user.email.split('@')[0]
    
    def get_user_avatar(self, obj):
        if obj.user.avatar:
            return obj.user.avatar.url
        return None
    
    def get_is_helpful(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.helpful_votes.filter(user=request.user).exists()
        return False
    
    def get_is_verified_purchase(self, obj):
        """Check if reviewer actually purchased and received the product."""
        return OrderItem.objects.filter(
            order__user=obj.user,
            product=obj.product,
            order__status='delivered'
        ).exists()


class CreateReviewSerializer(serializers.ModelSerializer):
    """Serializer for creating reviews."""
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Review
        fields = ['product', 'order_item', 'rating', 'title', 'comment', 'images']
    
    def validate_title(self, value):
        """Sanitize review title to prevent XSS."""
        if value:
            return bleach.clean(value, tags=[], strip=True)
        return value
    
    def validate_comment(self, value):
        """Sanitize review comment to prevent XSS."""
        if value:
            return bleach.clean(value, tags=[], strip=True)
        return value
    
    def validate(self, attrs):
        user = self.context['request'].user
        product = attrs['product']
        order_item = attrs.get('order_item')
        
        # Check if user already reviewed this product
        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("Bạn đã đánh giá sản phẩm này rồi.")
        
        # SECURITY: Verified Purchase Check - User must have purchased and received the product
        has_purchased = OrderItem.objects.filter(
            order__user=user,
            product=product,
            order__status='delivered'  # Only delivered orders qualify
        ).exists()
        
        if not has_purchased:
            raise serializers.ValidationError(
                "Bạn chỉ có thể đánh giá sản phẩm sau khi đã nhận hàng."
            )
        
        # If order_item is provided, validate it belongs to user and is delivered
        if order_item:
            if order_item.order.user != user:
                raise serializers.ValidationError("Đơn hàng không hợp lệ.")
            if order_item.order.status != 'delivered':
                raise serializers.ValidationError("Đơn hàng chưa được giao.")
            if order_item.product != product:
                raise serializers.ValidationError("Sản phẩm không khớp với đơn hàng.")
        
        return attrs
    
    def create(self, validated_data):
        images = validated_data.pop('images', [])
        validated_data['user'] = self.context['request'].user
        
        review = super().create(validated_data)
        
        for image in images:
            ReviewImage.objects.create(review=review, image=image)
        
        return review


class VendorReviewSerializer(serializers.ModelSerializer):
    """Serializer for vendor reviews."""
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = VendorReview
        fields = ['id', 'user_name', 'rating', 'comment', 'created_at']
    
    def get_user_name(self, obj):
        return obj.user.full_name or obj.user.email.split('@')[0]


class CreateVendorReviewSerializer(serializers.ModelSerializer):
    """Serializer for creating vendor reviews."""
    
    class Meta:
        model = VendorReview
        fields = ['vendor', 'order', 'rating', 'comment']
    
    def validate_comment(self, value):
        """Sanitize comment to prevent XSS attacks."""
        if value:
            return bleach.clean(value, tags=[], strip=True)
        return value
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
