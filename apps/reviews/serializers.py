from rest_framework import serializers
from .models import Review, ReviewImage, ReviewHelpful, VendorReview


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
    
    class Meta:
        model = Review
        fields = [
            'id', 'user_name', 'user_avatar', 'rating', 'title', 'comment',
            'images', 'helpful_count', 'is_helpful', 'created_at'
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
    
    def validate(self, attrs):
        user = self.context['request'].user
        product = attrs['product']
        
        # Check if user already reviewed this product
        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("You have already reviewed this product.")
        
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
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
