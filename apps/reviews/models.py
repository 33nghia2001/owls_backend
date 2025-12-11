from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg
import uuid


class Review(models.Model):
    """Product reviews from customers."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    order_item = models.OneToOneField(
        'orders.OrderItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='review'
    )
    
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField()
    
    # Moderation
    is_approved = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Helpful votes
    helpful_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reviews'
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']
        unique_together = ['user', 'product']  # One review per product per user
    
    def __str__(self):
        return f"{self.user.email} - {self.product.name} - {self.rating}★"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update product rating
        self.update_product_rating()
    
    def update_product_rating(self):
        """Update the product's average rating."""
        reviews = Review.objects.filter(product=self.product, is_approved=True)
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        self.product.rating = round(avg_rating, 2)
        self.product.review_count = reviews.count()
        self.product.save(update_fields=['rating', 'review_count'])


class ReviewImage(models.Model):
    """Images attached to reviews."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='reviews/')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'review_images'
        verbose_name = 'Review Image'
        verbose_name_plural = 'Review Images'


class ReviewHelpful(models.Model):
    """Track helpful votes for reviews."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='helpful_votes')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='helpful_votes'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'review_helpful'
        unique_together = ['review', 'user']


class VendorReview(models.Model):
    """Reviews for vendors/shops."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vendor_reviews'
    )
    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendor_reviews'
    )
    
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    
    is_approved = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendor_reviews'
        verbose_name = 'Vendor Review'
        verbose_name_plural = 'Vendor Reviews'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.vendor.shop_name} - {self.rating}★"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update vendor rating
        reviews = VendorReview.objects.filter(vendor=self.vendor, is_approved=True)
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        self.vendor.rating = round(avg_rating, 2)
        self.vendor.save(update_fields=['rating'])
