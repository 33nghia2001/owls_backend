from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.courses.models import Course


class Review(models.Model):
    """Course Reviews and Ratings"""
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    
    # Rating (1-5 stars)
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Review content
    title = models.CharField(max_length=255, blank=True)
    comment = models.TextField()
    
    # Helpful votes
    helpful_count = models.PositiveIntegerField(default=0)
    not_helpful_count = models.PositiveIntegerField(default=0)
    
    # Status
    is_approved = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reviews'
        unique_together = ['course', 'user']  # One review per user per course
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['course', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.course.title} - {self.rating} stars"


class ReviewHelpful(models.Model):
    """Track which users found reviews helpful"""
    
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='helpful_votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_votes')
    is_helpful = models.BooleanField()  # True = helpful, False = not helpful
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'review_helpful'
        unique_together = ['review', 'user']
        verbose_name_plural = 'Review Helpful Votes'
    
    def __str__(self):
        vote_type = "helpful" if self.is_helpful else "not helpful"
        return f"{self.user.username} marked review as {vote_type}"
    
    def save(self, *args, **kwargs):
        """Update helpful counts when vote is saved"""
        super().save(*args, **kwargs)
        
        # Recalculate counts
        helpful = ReviewHelpful.objects.filter(review=self.review, is_helpful=True).count()
        not_helpful = ReviewHelpful.objects.filter(review=self.review, is_helpful=False).count()
        
        self.review.helpful_count = helpful
        self.review.not_helpful_count = not_helpful
        self.review.save(update_fields=['helpful_count', 'not_helpful_count'])


class InstructorReply(models.Model):
    """Instructor replies to reviews"""
    
    review = models.OneToOneField(Review, on_delete=models.CASCADE, related_name='instructor_reply')
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_replies')
    
    reply_text = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'instructor_replies'
        verbose_name_plural = 'Instructor Replies'
    
    def __str__(self):
        return f"Reply by {self.instructor.username} to review #{self.review.id}"


class ReportReview(models.Model):
    """Report inappropriate reviews"""
    
    REPORT_REASONS = (
        ('spam', 'Spam'),
        ('offensive', 'Offensive Language'),
        ('irrelevant', 'Irrelevant Content'),
        ('fake', 'Fake Review'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('reviewing', 'Under Review'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    )
    
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_reports')
    
    reason = models.CharField(max_length=20, choices=REPORT_REASONS)
    description = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.TextField(blank=True)
    
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'review_reports'
        ordering = ['-reported_at']
    
    def __str__(self):
        return f"Report on review #{self.review.id} by {self.reported_by.username}"


# --- DJANGO SIGNALS (Tự động cập nhật rating) ---
@receiver([post_save, post_delete], sender=Review)
def update_course_rating(sender, instance, **kwargs):
    """
    Signal tự động tính lại rating khi có Review được Thêm/Sửa/Xóa.
    Hoạt động cả trên API và Django Admin.
    """
    from django.db.models import Avg, Count
    course = instance.course
    
    stats = Review.objects.filter(
        course=course,
        is_approved=True
    ).aggregate(
        avg_rating=Avg('rating'),
        total_reviews=Count('id')
    )
    
    course.average_rating = stats['avg_rating'] or 0.00
    course.total_reviews = stats['total_reviews'] or 0
    course.save(update_fields=['average_rating', 'total_reviews'])
