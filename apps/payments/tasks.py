"""
Celery tasks for payment processing with retry mechanism.
"""
import logging
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Payment, PaymentLog
from .vnpay import VNPayService

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minutes between retries
    retry_kwargs={'max_retries': 5},
    acks_late=True,
)
def process_vnpay_refund_task(self, payment_id, amount, reason, client_ip, user_name):
    """
    Process VNPay refund asynchronously with automatic retry on failure.
    
    Args:
        payment_id: Payment record ID
        amount: Refund amount (Decimal string)
        reason: Refund reason
        client_ip: Client IP address
        user_name: User who initiated refund
    
    Retries automatically up to 5 times with exponential backoff.
    """
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        logger.error(f"Payment {payment_id} not found for refund")
        return {'success': False, 'error': 'Payment not found'}
    
    # Already refunded? Skip
    if payment.status == 'refunded':
        logger.info(f"Payment {payment_id} already refunded, skipping")
        return {'success': True, 'message': 'Already refunded'}
    
    # Mark as processing
    payment.status = 'refund_pending'
    payment.save(update_fields=['status'])
    
    vnpay_service = VNPayService()
    refund_amount = Decimal(str(amount))
    
    try:
        response = vnpay_service.refund(payment, refund_amount, reason, client_ip, user_name)
        
        if response.get('vnp_ResponseCode') == '00':
            # Success
            payment.status = 'refunded'
            payment.refund_amount = refund_amount
            payment.refunded_at = timezone.now()
            
            gw_response = payment.gateway_response or {}
            gw_response.update({'refund_response': response})
            payment.gateway_response = gw_response
            payment.save()
            
            PaymentLog.objects.create(
                payment=payment,
                action='vnpay_refund_async',
                request_data={'amount': str(refund_amount), 'reason': reason},
                response_data=response,
                is_success=True
            )
            
            logger.info(f"VNPay refund successful for payment {payment_id}")
            return {'success': True, 'data': response}
        
        else:
            # VNPay returned error - log and retry
            error_msg = response.get('vnp_Message', 'Unknown VNPay error')
            
            PaymentLog.objects.create(
                payment=payment,
                action='vnpay_refund_async',
                request_data={'amount': str(refund_amount), 'reason': reason, 'attempt': self.request.retries + 1},
                response_data=response,
                is_success=False,
                error_message=error_msg
            )
            
            # Check if it's a temporary error that should be retried
            temp_error_codes = ['99', '97', '96']  # Network/timeout errors
            if response.get('vnp_ResponseCode') in temp_error_codes:
                logger.warning(f"VNPay temporary error for payment {payment_id}, retrying...")
                raise Exception(f"VNPay temporary error: {error_msg}")
            
            # Permanent error - don't retry
            payment.status = 'refund_failed'
            payment.save(update_fields=['status'])
            
            # Alert admin for permanent failures
            _send_refund_alert(payment, error_msg)
            
            logger.error(f"VNPay permanent refund error for payment {payment_id}: {error_msg}")
            return {'success': False, 'error': error_msg}
    
    except Exception as e:
        logger.error(f"VNPay refund exception for payment {payment_id}: {e}")
        
        # Log the attempt
        PaymentLog.objects.create(
            payment=payment,
            action='vnpay_refund_async',
            request_data={'amount': str(refund_amount), 'attempt': self.request.retries + 1},
            response_data={},
            is_success=False,
            error_message=str(e)
        )
        
        # Re-raise to trigger Celery retry
        raise


def _send_refund_alert(payment, error_msg):
    """Send alert email to admin for failed refunds."""
    try:
        admin_email = getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)
        send_mail(
            subject=f"[URGENT] VNPay Refund Failed - Payment #{payment.id}",
            message=f"""
VNPay refund failed and requires manual intervention.

Payment ID: {payment.id}
Order: {payment.order.order_number}
Amount: {payment.amount}
Error: {error_msg}

Please process this refund manually through VNPay merchant portal.
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=True
        )
    except Exception as e:
        logger.error(f"Failed to send refund alert email: {e}")


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
)
def sync_payment_status_task(self, payment_id):
    """
    Sync payment status with payment gateway.
    Useful for checking pending payments.
    """
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return {'success': False, 'error': 'Payment not found'}
    
    if payment.method == 'vnpay' and payment.status == 'pending':
        # Query VNPay for status
        vnpay_service = VNPayService()
        # Note: VNPay query API implementation would go here
        # For now, just log the check
        logger.info(f"Checking VNPay status for payment {payment_id}")
    
    return {'success': True, 'status': payment.status}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,  # Max 5 minutes between retries
    retry_kwargs={'max_retries': 3},
)
def send_payment_alert_email_task(self, subject, message):
    """
    Send urgent payment alert email to admin asynchronously.
    
    This prevents blocking the IPN webhook response when email
    delivery is slow or fails.
    
    Args:
        subject: Email subject (will be prefixed with [URGENT - PAYMENT ALERT])
        message: Email body text
    """
    try:
        admin_email = getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)
        
        send_mail(
            subject=f"[URGENT - PAYMENT ALERT] {subject}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=False  # Raise exception so Celery can retry
        )
        
        logger.info(f"Payment alert email sent: {subject}")
        return {'success': True, 'subject': subject}
        
    except Exception as e:
        logger.error(f"Failed to send payment alert email: {e}")
        raise  # Re-raise for Celery retry
