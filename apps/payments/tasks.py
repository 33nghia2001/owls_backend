"""
Celery tasks for asynchronous processing with rate limiting.

SECURITY: Tasks are rate-limited to prevent DoS attacks on email servers
and Redis queue flooding.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.enrollments.models import Enrollment
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    bind=True, 
    max_retries=3,
    rate_limit='10/m'  # SECURITY: Max 10 emails per minute to prevent abuse
)
def send_enrollment_confirmation_email(self, enrollment_id):
    """
    Send enrollment confirmation email to student.
    
    SECURITY: Rate limited to 10/minute to prevent email server abuse.
    Async task to avoid blocking payment response.
    """
    try:
        enrollment = Enrollment.objects.select_related('student', 'course').get(id=enrollment_id)
        
        subject = f'Enrollment Confirmed: {enrollment.course.title}'
        message = f"""
        Hi {enrollment.student.get_full_name()},
        
        Congratulations! You have successfully enrolled in "{enrollment.course.title}".
        
        You can now access all course materials and start learning.
        
        Course Link: {settings.FRONTEND_URL}/courses/{enrollment.course.slug}
        
        Happy Learning!
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[enrollment.student.email],
            fail_silently=False,
        )
        
        logger.info(f'Enrollment email sent to {enrollment.student.email} for course {enrollment.course.id}')
        
        # Send real-time WebSocket notification
        from apps.notifications.utils import send_notification_to_user
        send_notification_to_user(
            user_id=enrollment.student.id,
            notification_data={
                'title': 'Enrollment Confirmed',
                'message': f'You have successfully enrolled in {enrollment.course.title}',
                'type': 'success',
                'created_at': timezone.now().isoformat(),
                'is_read': False,
            }
        )
        
    except Enrollment.DoesNotExist:
        logger.error(f'Enrollment {enrollment_id} not found')
    except Exception as exc:
        logger.error(f'Error sending enrollment email: {exc}')
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(
    bind=True, 
    max_retries=3,
    rate_limit='10/m'  # SECURITY: Max 10 emails per minute
)
def send_payment_success_email(self, payment_id):
    """
    Send payment confirmation email.
    
    SECURITY: Rate limited to prevent email server abuse.
    """
    try:
        from apps.payments.models import Payment
        
        payment = Payment.objects.select_related('user', 'course').get(id=payment_id)
        
        subject = f'Payment Confirmed - {payment.course.title}'
        message = f"""
        Hi {payment.user.get_full_name()},
        
        Your payment of {payment.amount} VND for "{payment.course.title}" has been confirmed.
        
        Transaction ID: {payment.transaction_id}
        Payment Method: {payment.payment_method.upper()}
        
        You can now access the course materials.
        
        Thank you for your purchase!
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payment.user.email],
            fail_silently=False,
        )
        
        logger.info(f'Payment confirmation email sent to {payment.user.email}')
        
        # Send real-time WebSocket notification
        from apps.notifications.utils import send_notification_to_user
        send_notification_to_user(
            user_id=payment.user.id,
            notification_data={
                'title': 'Payment Successful',
                'message': f'Your payment for {payment.course.title} has been confirmed',
                'type': 'success',
                'created_at': timezone.now().isoformat(),
                'is_read': False,
            }
        )
        
    except Exception as exc:
        logger.error(f'Error sending payment email: {exc}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def generate_course_certificate(enrollment_id):
    """
    Generate PDF certificate for completed course.
    This is a placeholder - implement with ReportLab or similar.
    """
    try:
        enrollment = Enrollment.objects.select_related('student', 'course').get(id=enrollment_id)
        
        # TODO: Implement PDF generation with ReportLab
        # from reportlab.pdfgen import canvas
        # Generate certificate PDF with student name, course, completion date
        
        logger.info(f'Certificate generated for enrollment {enrollment_id}')
        
        # Send certificate via email
        # send_certificate_email.delay(enrollment_id)
        
    except Exception as exc:
        logger.error(f'Error generating certificate: {exc}')


@shared_task
def cleanup_expired_payments():
    """
    Periodic task to clean up expired pending payments.
    Should be run via Celery Beat every 30 minutes.
    """
    from apps.payments.models import Payment, Discount
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import F
    
    cutoff_time = timezone.now() - timedelta(minutes=10)
    
    expired_payments = Payment.objects.filter(
        status='pending',
        created_at__lt=cutoff_time
    ).select_related('discount')
    
    count = 0
    for payment in expired_payments:
        # Release discount slot
        if payment.discount:
            Discount.objects.filter(id=payment.discount.id).update(
                used_count=F('used_count') - 1
            )
        count += 1
    
    # Bulk update to expired
    expired_payments.update(status='expired')
    
    logger.info(f'Cleaned up {count} expired payments')
    return count


@shared_task(rate_limit='20/m')  # SECURITY: Max 20 notifications per minute
def send_review_reply_notification(reply_id):
    """
    Notify student when instructor replies to their review.
    
    SECURITY: Rate limited to prevent notification spam.
    """
    try:
        from apps.reviews.models import InstructorReply
        
        reply = InstructorReply.objects.select_related(
            'review__user', 'review__course', 'instructor'
        ).get(id=reply_id)
        
        subject = f'Instructor replied to your review'
        message = f"""
        Hi {reply.review.user.get_full_name()},
        
        {reply.instructor.get_full_name()} has replied to your review on "{reply.review.course.title}":
        
        "{reply.reply_text}"
        
        View the conversation: {settings.FRONTEND_URL}/courses/{reply.review.course.slug}/reviews
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[reply.review.user.email],
            fail_silently=False,
        )
        
        logger.info(f'Review reply notification sent')
        
    except Exception as exc:
        logger.error(f'Error sending review reply notification: {exc}')
