"""
Celery tasks for asynchronous processing with rate limiting.

SECURITY: Tasks are rate-limited to prevent DoS attacks on email servers
and Redis queue flooding.
"""
import io
import logging
import textwrap
from typing import Optional, Dict, Any, List

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail, EmailMessage
from django.db import transaction
from django.db.models import F, Count
from django.utils import timezone
from datetime import timedelta

# Local Imports
# Import models inside functions where possible to avoid AppRegistryNotReady in some setups,
# but shared utilities can be imported here if they don't depend on models at module level.
try:
    from apps.notifications.utils import send_notification_to_user
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ==============================================================================
# HELPER FUNCTIONS (Internal)
# ==============================================================================

def _send_email_wrapper(subject: str, message: str, recipient_list: List[str], html_message: str = None) -> bool:
    """
    Wrapper để gửi email an toàn, tránh boilerplate code.
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
            html_message=html_message
        )
        return True
    except Exception as exc:
        logger.error(f'Error sending email to {recipient_list}: {exc}')
        raise exc  # Re-raise để Celery retry

def _send_ws_notification_wrapper(user_id: int, title: str, message: str, msg_type: str = 'info') -> None:
    """
    Wrapper gửi WebSocket notification an toàn. 
    Lỗi ở đây không nên làm fail task chính (như gửi email).
    """
    try:
        from apps.notifications.utils import send_notification_to_user
        send_notification_to_user(
            user_id=user_id,
            notification_data={
                'title': title,
                'message': message,
                'type': msg_type,
                'created_at': timezone.now().isoformat(),
                'is_read': False,
            }
        )
    except ImportError:
        logger.warning("Notification app not installed or utils not found.")
    except Exception as e:
        logger.error(f"Error sending WS notification to user {user_id}: {e}")

# ==============================================================================
# CELERY TASKS
# ==============================================================================

@shared_task(bind=True, max_retries=3, rate_limit='10/m')
def send_enrollment_confirmation_email(self, enrollment_id: int):
    """
    Send enrollment confirmation email to student.
    SECURITY: Rate limited to 10/minute.
    """
    from apps.enrollments.models import Enrollment
    
    try:
        enrollment = Enrollment.objects.select_related('student', 'course').get(id=enrollment_id)
        student = enrollment.student
        course = enrollment.course
        
        subject = f'Enrollment Confirmed: {course.title}'
        message = textwrap.dedent(f"""
            Hi {student.get_full_name() or student.username},
            
            Congratulations! You have successfully enrolled in "{course.title}".
            
            You can now access all course materials and start learning.
            
            Course Link: {settings.FRONTEND_URL}/courses/{course.slug}
            
            Happy Learning!
        """)
        
        # 1. Send Email
        _send_email_wrapper(subject, message, [student.email])
        logger.info(f'Enrollment email sent to {student.email} for course {course.id}')
        
        # 2. Send WebSocket Notification
        _send_ws_notification_wrapper(
            user_id=student.id,
            title='Enrollment Confirmed',
            message=f'You have successfully enrolled in {course.title}',
            msg_type='success'
        )
        
    except Enrollment.DoesNotExist:
        logger.error(f'Enrollment {enrollment_id} not found')
    except Exception as exc:
        logger.error(f'Task error: {exc}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, rate_limit='10/m')
def send_payment_success_email(self, payment_id: int):
    """
    Send payment confirmation email.
    SECURITY: Rate limited.
    """
    from apps.payments.models import Payment
    
    try:
        payment = Payment.objects.select_related('user', 'course').get(id=payment_id)
        user = payment.user
        course = payment.course
        
        subject = f'Payment Confirmed - {course.title}'
        message = textwrap.dedent(f"""
            Hi {user.get_full_name() or user.username},
            
            Your payment of {payment.amount:,.0f} {payment.currency} for "{course.title}" has been confirmed.
            
            Transaction ID: {payment.transaction_id}
            Payment Method: {payment.payment_method.upper()}
            
            You can now access the course materials.
            
            Thank you for your purchase!
        """)
        
        # 1. Send Email
        _send_email_wrapper(subject, message, [user.email])
        logger.info(f'Payment confirmation email sent to {user.email}')
        
        # 2. Send WebSocket Notification
        _send_ws_notification_wrapper(
            user_id=user.id,
            title='Payment Successful',
            message=f'Your payment for {course.title} has been confirmed',
            msg_type='success'
        )
        
    except Exception as exc:
        logger.error(f'Error processing payment email task: {exc}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, rate_limit='5/m')
def send_certificate_email(self, enrollment_id: int, certificate_path: str):
    """
    Send course completion certificate to student via email with PDF attachment.
    
    SECURITY FIX: Validates certificate_path to prevent LFI/Path Traversal attacks.
    Only allows files within 'certificates/' directory.
    """
    from apps.enrollments.models import Enrollment
    
    # SECURITY CHECK: Prevent path traversal attacks
    if not certificate_path.startswith('certificates/') or '..' in certificate_path:
        logger.critical(
            f"SECURITY ALERT: Path traversal attempt in send_certificate_email. "
            f"Path: {certificate_path}, Enrollment: {enrollment_id}"
        )
        return  # Silently fail - do not process malicious paths
    
    try:
        enrollment = Enrollment.objects.select_related('student', 'course').get(id=enrollment_id)
        student = enrollment.student
        
        subject = f'Congratulations! Certificate for {enrollment.course.title}'
        message = textwrap.dedent(f"""
            Hi {student.get_full_name() or student.username},
            
            Congratulations on completing "{enrollment.course.title}"!
            
            Your certificate of completion is attached to this email.
            
            You can also view and download your certificates from your dashboard:
            {settings.FRONTEND_URL}/my-certificates
            
            We're proud of your achievement!
            
            Best regards,
            The Learning Team
        """)
        
        # Create Email Object
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[student.email],
        )
        
        # Attach PDF
        if default_storage.exists(certificate_path):
            with default_storage.open(certificate_path, 'rb') as f:
                email.attach(
                    f'certificate_{enrollment.course.slug}.pdf',
                    f.read(),
                    'application/pdf'
                )
            email.send(fail_silently=False)
            logger.info(f'Certificate email sent to {student.email}')
        else:
            logger.error(f"Certificate file not found at {certificate_path}")
            # Don't retry if file is missing, it won't appear magically
            return

        # Send WebSocket Notification
        _send_ws_notification_wrapper(
            user_id=student.id,
            title='Certificate Ready!',
            message=f'Your certificate for {enrollment.course.title} is ready for download',
            msg_type='success'
        )
        
    except Enrollment.DoesNotExist:
        logger.error(f'Enrollment {enrollment_id} not found')
    except Exception as exc:
        logger.error(f'Error sending certificate email: {exc}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, rate_limit='5/m')
def generate_course_certificate(self, enrollment_id: int):
    """
    Generate PDF certificate for completed course using ReportLab.
    
    SECURITY: Rate limited to 5/minute to prevent DoS attacks.
    PDF generation is CPU/memory intensive and could overwhelm workers.
    """
    from apps.enrollments.models import Enrollment
    # ReportLab imports (moved inside to save memory if task not used)
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    
    try:
        enrollment = Enrollment.objects.select_related(
            'student', 'course', 'course__instructor'
        ).get(id=enrollment_id)
        
        if enrollment.status != 'completed':
            logger.warning(f'Cannot generate certificate - enrollment {enrollment_id} not completed')
            return None
        
        # Buffer for PDF
        buffer = io.BytesIO()
        page_width, page_height = landscape(A4)
        c = canvas.Canvas(buffer, pagesize=landscape(A4))
        
        # --- PDF Drawing Logic (Simplified for brevity but kept functional) ---
        # Draw Border
        c.setStrokeColor(colors.HexColor('#1a5490'))
        c.setLineWidth(3)
        c.rect(0.5*inch, 0.5*inch, page_width - inch, page_height - inch)
        
        # Content Configuration
        center_x = page_width / 2
        student_name = enrollment.student.get_full_name() or enrollment.student.username
        course_title = enrollment.course.title
        instructor_name = enrollment.course.instructor.get_full_name()
        date_str = (enrollment.completed_at or timezone.now()).strftime('%B %d, %Y')
        cert_id = f"CERT-{enrollment.id}"

        # Draw Text
        def draw_text(text, y, font='Helvetica', size=12, color=colors.black):
            c.setFont(font, size)
            c.setFillColor(color)
            c.drawCentredString(center_x, y, text)

        draw_text("CERTIFICATE OF COMPLETION", page_height - 2*inch, 'Helvetica-Bold', 40, colors.HexColor('#1a5490'))
        draw_text("This is to certify that", page_height - 2.8*inch, 'Helvetica', 18)
        draw_text(student_name, page_height - 3.5*inch, 'Helvetica-Bold', 32, colors.HexColor('#2c5aa0'))
        draw_text("has successfully completed the course", page_height - 4.1*inch, 'Helvetica', 16)
        draw_text(course_title, page_height - 4.7*inch, 'Helvetica-Bold', 22, colors.HexColor('#1a5490'))
        draw_text(f"Completed on {date_str}", page_height - 5.5*inch, 'Helvetica', 14)
        
        # Signature
        sig_y = page_height - 6.7*inch
        c.setLineWidth(1)
        c.line(center_x - 2*inch, sig_y, center_x + 2*inch, sig_y)
        draw_text(instructor_name, sig_y - 0.2*inch, 'Helvetica-Bold', 12)
        draw_text("Course Instructor", sig_y - 0.4*inch, 'Helvetica', 10)
        draw_text(f"ID: {cert_id}", 0.8*inch, 'Helvetica', 9, colors.grey)
        
        c.showPage()
        c.save()
        
        # Save File
        pdf_data = buffer.getvalue()
        buffer.close()
        
        filename = f"certificates/certificate_{enrollment.id}_{timezone.now().strftime('%Y%m%d%H%M')}.pdf"
        saved_path = default_storage.save(filename, ContentFile(pdf_data))
        
        logger.info(f'Certificate generated: {saved_path}')
        
        # Trigger email task
        send_certificate_email.delay(enrollment_id, saved_path)
        return saved_path
        
    except Exception as exc:
        logger.error(f'Error generating certificate: {exc}', exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def cleanup_expired_payments():
    """
    Periodic task to clean up expired pending payments.
    
    SECURITY FIX: Use select_for_update(skip_locked=True) to prevent race conditions
    where a payment completes via IPN while being expired by this task.
    The "Double Refund Bug" is prevented by locking rows before processing.
    """
    from apps.payments.models import Payment, Discount
    
    cutoff_time = timezone.now() - timedelta(minutes=10)
    
    with transaction.atomic():
        # 1. Lock rows that are candidates for expiration
        # skip_locked=True: Skip payments currently being processed by IPN
        expired_payments = list(
            Payment.objects.filter(
                status='pending',
                created_at__lt=cutoff_time
            ).select_for_update(skip_locked=True)
            .select_related('discount')
            .only('id', 'discount')
        )
        
        if not expired_payments:
            return 0

        # 2. Calculate refunds in memory (Safe now because rows are locked)
        discount_refund_map = {}
        payment_ids = []
        
        for payment in expired_payments:
            payment_ids.append(payment.id)
            # SAFETY: Check both discount existence and discount_id to prevent AttributeError
            if payment.discount_id:
                discount_refund_map[payment.discount_id] = discount_refund_map.get(payment.discount_id, 0) + 1
        
        # 3. Bulk update discounts (Atomic decrement)
        for discount_id, count in discount_refund_map.items():
            Discount.objects.filter(id=discount_id).update(
                used_count=F('used_count') - count
            )
            logger.info(f"Refunded {count} slots for discount ID {discount_id}")

        # 4. Bulk update payments (Only locked rows)
        updated_count = Payment.objects.filter(id__in=payment_ids).update(status='expired')
    
    logger.info(f'Cleaned up {updated_count} expired payments')
    return updated_count


@shared_task(rate_limit='20/m')
def send_review_reply_notification(reply_id: int):
    """
    Notify student when instructor replies to their review.
    """
    from apps.reviews.models import InstructorReply
    
    try:
        reply = InstructorReply.objects.select_related(
            'review__user', 'review__course', 'instructor'
        ).get(id=reply_id)
        
        student = reply.review.user
        course = reply.review.course
        
        subject = 'Instructor replied to your review'
        message = textwrap.dedent(f"""
            Hi {student.get_full_name() or student.username},
            
            {reply.instructor.get_full_name()} has replied to your review on "{course.title}":
            
            "{reply.reply_text}"
            
            View the conversation: {settings.FRONTEND_URL}/courses/{course.slug}/reviews
        """)
        
        _send_email_wrapper(subject, message, [student.email])
        logger.info('Review reply notification sent')
        
    except Exception as exc:
        logger.error(f'Error sending review reply notification: {exc}', exc_info=True)