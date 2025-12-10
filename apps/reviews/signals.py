"""
Signal handlers for reviews app.

BUSINESS LOGIC: Automatically hide/remove reviews when enrollments are cancelled or refunded.
This prevents "review bombing" attacks where users leave negative reviews then request refunds.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.enrollments.models import Enrollment
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Enrollment)
def hide_review_on_enrollment_cancel(sender, instance, **kwargs):
    """
    Hide reviews when enrollment is cancelled, expired, or refunded.
    
    SECURITY FIX: Prevents "Review Bombing" attack where:
    1. Attacker buys course
    2. Leaves 1-star negative review
    3. Requests refund
    4. Negative review remains, damaging instructor reputation
    
    This ensures only students with active/completed enrollments can have visible reviews.
    """
    # Only process if enrollment status changed to cancelled/expired/refunded
    if instance.status in ['cancelled', 'expired', 'refunded']:
        from apps.reviews.models import Review
        
        try:
            # Find and hide reviews for this student-course combination
            reviews = Review.objects.filter(
                user=instance.student,
                course=instance.course,
                is_approved=True  # Only hide approved reviews
            )
            
            count = reviews.count()
            if count > 0:
                # Hide reviews (set is_approved=False)
                reviews.update(is_approved=False)
                logger.info(
                    f"Hidden {count} review(s) for enrollment {instance.id}. "
                    f"Student: {instance.student.id}, Course: {instance.course.id}, "
                    f"Status: {instance.status}"
                )
        except Exception as e:
            logger.error(
                f"Error hiding reviews for enrollment {instance.id}: {e}",
                exc_info=True
            )


@receiver(post_save, sender=Enrollment)
def restore_review_on_enrollment_reactivate(sender, instance, **kwargs):
    """
    Restore hidden reviews if enrollment is reactivated (e.g., after resolving dispute).
    
    This handles edge cases where:
    - User requests refund, review hidden
    - Refund denied, enrollment reactivated
    - Review should be visible again
    """
    if instance.status in ['active', 'completed']:
        from apps.reviews.models import Review
        
        try:
            # Find hidden reviews for this student-course combination
            reviews = Review.objects.filter(
                user=instance.student,
                course=instance.course,
                is_approved=False  # Only restore previously hidden reviews
            )
            
            count = reviews.count()
            if count > 0:
                # Restore reviews (set is_approved=True)
                reviews.update(is_approved=True)
                logger.info(
                    f"Restored {count} review(s) for enrollment {instance.id}. "
                    f"Student: {instance.student.id}, Course: {instance.course.id}, "
                    f"Status: {instance.status}"
                )
        except Exception as e:
            logger.error(
                f"Error restoring reviews for enrollment {instance.id}: {e}",
                exc_info=True
            )
