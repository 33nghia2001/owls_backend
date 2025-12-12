import logging
import stripe
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.mail import send_mail
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.orders.models import Order
from .models import Payment, PaymentLog
from .serializers import PaymentSerializer, CreatePaymentSerializer
from .vnpay import VNPayService
from .tasks import process_vnpay_refund_task

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for payments handling: COD, Stripe, VNPay."""
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Payment.objects.filter(
            user=self.request.user
        ).select_related(
            'order', 'user'
        ).prefetch_related(
            'logs'
        ).order_by('-created_at')
    
    def _get_client_ip(self, request):
        """Get the real client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip

    def _send_alert_email(self, subject, message):
        """Gửi email cảnh báo khẩn cấp cho Admin."""
        try:
            admin_email = getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)
            send_mail(
                subject=f"[URGENT - PAYMENT ALERT] {subject}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")

    @action(detail=False, methods=['post'])
    def create_payment(self, request):
        """Create a payment for an order."""
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order = get_object_or_404(
            Order,
            id=serializer.validated_data['order_id'],
            user=request.user
        )
        
        if hasattr(order, 'payment') and order.payment.status == 'completed':
            return Response(
                {'error': 'Order already paid.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        method = serializer.validated_data['method']
        
        # Create or get payment record
        payment, created = Payment.objects.get_or_create(
            order=order,
            defaults={
                'user': request.user,
                'method': method,
                'amount': order.total,
                'status': 'pending'
            }
        )
        
        if not created:
            payment.method = method
            payment.save()
        
        # --- PROCESS METHODS ---
        
        # 1. COD (Cash On Delivery)
        if method == 'cod':
            payment.status = 'pending'
            payment.save()
            
            order.payment_status = 'pending'
            order.status = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save()
            
            return Response({
                'payment': PaymentSerializer(payment).data,
                'message': 'Order confirmed. Pay on delivery.'
            })
        
        # 2. STRIPE
        elif method == 'stripe':
            try:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'vnd',
                            'product_data': {'name': f'Order {order.order_number}'},
                            'unit_amount': int(order.total.amount),
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=f'{settings.FRONTEND_URL}/checkout/success?order_id={order.id}',
                    cancel_url=f'{settings.FRONTEND_URL}/checkout/cancel',
                    metadata={
                        'order_id': str(order.id),
                        'payment_id': str(payment.id),
                    }
                )
                
                payment.transaction_id = checkout_session.id
                payment.status = 'processing'
                payment.save()
                
                return Response({
                    'payment': PaymentSerializer(payment).data,
                    'checkout_url': checkout_session.url
                })
                
            except stripe.error.StripeError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        # 3. VNPAY
        elif method == 'vnpay':
            try:
                vnpay_service = VNPayService()
                client_ip = self._get_client_ip(request)
                
                payment_url = vnpay_service.create_payment_url(order, None, client_ip)
                
                payment.status = 'processing'
                payment.save()
                
                PaymentLog.objects.create(
                    payment=payment,
                    action='create_vnpay_url',
                    request_data={'order_id': str(order.id)},
                    response_data={'payment_url': payment_url},
                    is_success=True
                )
                
                return Response({
                    'payment': PaymentSerializer(payment).data,
                    'payment_url': payment_url
                })
                
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({'error': 'Invalid payment method.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    @transaction.atomic
    def vnpay_return(self, request):
        """
        Handle VNPay return callback (Client Redirect).
        Verify signature -> Update Order/Payment -> Redirect UI.
        """
        params = dict(request.GET)
        # Flatten list values
        params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
        
        vnpay_service = VNPayService()
        
        if not vnpay_service.verify_callback(params.copy()):
            return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)
        
        order_id = params.get('vnp_TxnRef')
        try:
            order = Order.objects.get(id=order_id)
            payment = order.payment
        except (Order.DoesNotExist, Payment.DoesNotExist):
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        response_code = params.get('vnp_ResponseCode')
        is_success = vnpay_service.is_success(response_code)
        
        if is_success:
            if payment.status != 'completed':
                payment.status = 'completed'
                payment.transaction_id = params.get('vnp_TransactionNo', '')
                payment.gateway_response = params
                payment.completed_at = timezone.now()
                payment.save()
                
                order.payment_status = 'paid'
                order.status = 'confirmed'
                order.confirmed_at = timezone.now()
                order.save()
            
            return Response({
                'success': True,
                'message': 'Payment successful',
                'order_id': str(order.id)
            })
        else:
            payment.status = 'failed'
            payment.gateway_response = params
            payment.save()
            return Response({
                'success': False,
                'message': 'Payment failed',
                'error_code': response_code
            })

    @action(detail=False, methods=['get', 'post'], permission_classes=[AllowAny])
    @transaction.atomic
    def vnpay_ipn(self, request):
        """
        Handle VNPay IPN (Server-to-Server).
        Critical for ensuring payment confirmation even if user closes browser.
        Includes replay attack prevention and idempotency checks.
        """
        from datetime import timedelta
        import hashlib
        from .models import WebhookEvent
        
        if request.method == 'POST':
            params = dict(request.POST)
        else:
            params = dict(request.GET)
        
        params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
        
        vnpay_service = VNPayService()
        
        # 1. Verify Signature FIRST
        if not vnpay_service.verify_callback(params.copy()):
            return Response({'RspCode': '97', 'Message': 'Invalid Signature'})
        
        # 2. REPLAY ATTACK PREVENTION - Check timestamp
        vnp_pay_date = params.get('vnp_PayDate')
        if vnp_pay_date:
            try:
                from datetime import datetime
                pay_time = datetime.strptime(vnp_pay_date, '%Y%m%d%H%M%S')
                pay_time = timezone.make_aware(pay_time)
                if timezone.now() - pay_time > timedelta(minutes=30):
                    logger.warning(f"VNPay IPN expired callback: {vnp_pay_date}")
                    return Response({'RspCode': '98', 'Message': 'Callback expired'})
            except ValueError:
                pass  # Allow if date parsing fails
        
        # 3. IDEMPOTENCY - Check if this transaction was already processed
        vnp_transaction_no = params.get('vnp_TransactionNo', '')
        event_id = f"vnpay_{vnp_transaction_no}"
        
        if WebhookEvent.objects.filter(event_id=event_id, source='vnpay').exists():
            logger.info(f"VNPay IPN duplicate: {vnp_transaction_no}")
            return Response({'RspCode': '02', 'Message': 'Already processed'})
        
        order_id = params.get('vnp_TxnRef')
        
        # 4. Check Order/Payment Existence
        try:
            order = Order.objects.select_for_update().get(id=order_id)
            payment = order.payment
        except (Order.DoesNotExist, Payment.DoesNotExist):
            return Response({'RspCode': '01', 'Message': 'Order not found'})

        # 3. Idempotency Check
        if payment.status == 'completed':
            return Response({'RspCode': '02', 'Message': 'Order already confirmed'})
            
        # 4. Amount Validation
        vnp_amount = Decimal(params.get('vnp_Amount', 0)) / 100
        if vnp_amount != order.total.amount:
            return Response({'RspCode': '04', 'Message': 'Invalid Amount'})
        
        response_code = params.get('vnp_ResponseCode')
        is_success = vnpay_service.is_success(response_code)
        
        if is_success:
            # --- CRITICAL RACE CONDITION CHECK ---
            # Nếu đơn hàng đã bị hủy (bởi người dùng hoặc cronjob) nhưng tiền vẫn về
            if order.status == 'cancelled':
                payment.status = 'pending_refund'
                payment.transaction_id = params.get('vnp_TransactionNo', '')
                payment.gateway_response = params
                payment.completed_at = timezone.now()
                payment.save()
                
                # Gửi email báo động cho Admin
                self._send_alert_email(
                    subject=f"CRITICAL: Tiền về cho đơn hủy #{order.order_number}",
                    message=f"Đơn hàng {order.id} đã bị hủy nhưng nhận được thanh toán VNPay.\n"
                            f"Mã GD: {params.get('vnp_TransactionNo')}\n"
                            f"Số tiền: {vnp_amount}\n"
                            f"Yêu cầu: Kiểm tra và hoàn tiền thủ công."
                )
                
                PaymentLog.objects.create(
                    payment=payment,
                    action='vnpay_ipn_cancelled',
                    request_data=params,
                    response_data={'response_code': response_code},
                    is_success=False,
                    error_message='Payment received for cancelled order'
                )
                return Response({'RspCode': '00', 'Message': 'Confirm Success (Refund Needed)'})

            # --- NORMAL SUCCESS CASE ---
            payment.status = 'completed'
            payment.transaction_id = params.get('vnp_TransactionNo', '')
            payment.gateway_response = params
            payment.completed_at = timezone.now()
            payment.save()
            
            order.payment_status = 'paid'
            order.status = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save()
            
            # Record webhook event for idempotency
            WebhookEvent.objects.create(
                event_id=event_id,
                event_type='payment_success',
                source='vnpay'
            )
            
            PaymentLog.objects.create(
                payment=payment,
                action='vnpay_ipn',
                request_data=params,
                response_data={'response_code': response_code},
                is_success=True
            )
            return Response({'RspCode': '00', 'Message': 'Confirm Success'})
            
        else:
            # Payment Failed - still record event to prevent replay
            WebhookEvent.objects.create(
                event_id=event_id,
                event_type='payment_failed',
                source='vnpay'
            )
            
            payment.status = 'failed'
            payment.gateway_response = params
            payment.save()
            return Response({'RspCode': '00', 'Message': 'Confirm Success'})

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    @transaction.atomic
    def stripe_webhook(self, request):
        """Handle Stripe webhook events."""
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            order_id = session['metadata'].get('order_id')
            payment_id = session['metadata'].get('payment_id')
            
            try:
                payment = Payment.objects.select_for_update().get(id=payment_id)
                order = payment.order
                
                if payment.status == 'completed':
                    return Response({'status': 'already_processed'})
                
                # Check race condition for Stripe as well
                if order.status == 'cancelled':
                    payment.status = 'pending_refund'
                    payment.transaction_id = session.get('payment_intent', '')
                    payment.gateway_response = dict(session)
                    payment.save()
                    
                    self._send_alert_email(
                        subject=f"CRITICAL: Stripe payment for cancelled order #{order.order_number}",
                        message=f"Order {order.id} was cancelled but payment received."
                    )
                    return Response({'status': 'refund_needed'})
                
                payment.status = 'completed'
                payment.transaction_id = session.get('payment_intent', '')
                payment.gateway_response = dict(session)
                payment.completed_at = timezone.now()
                payment.save()
                
                order.payment_status = 'paid'
                order.status = 'confirmed'
                order.confirmed_at = timezone.now()
                order.save()
                
            except Payment.DoesNotExist:
                pass
        
        return Response({'status': 'success'})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    @transaction.atomic
    def refund(self, request, pk=None):
        """
        Process a refund for a payment (Admin/Staff only).
        """
        if not request.user.is_staff:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        payment = get_object_or_404(Payment, pk=pk)
        
        if payment.status not in ['completed', 'pending_refund']:
            return Response(
                {'error': f'Cannot refund payment with status: {payment.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refund_amount = request.data.get('amount')
        reason = request.data.get('reason', 'requested_by_customer')
        
        # DOUBLE REFUND PROTECTION
        requested_amount = Decimal(str(refund_amount)) if refund_amount else payment.amount.amount
        already_refunded = payment.refund_amount.amount if payment.refund_amount else Decimal('0')
        max_refundable = payment.amount.amount - already_refunded
        
        if requested_amount > max_refundable:
            return Response({
                'error': f'Cannot refund {requested_amount}. Already refunded: {already_refunded}. Max remaining: {max_refundable}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if payment.method == 'stripe':
            return self._process_stripe_refund(payment, refund_amount, reason)
        elif payment.method == 'vnpay':
            return self._process_vnpay_refund(payment, refund_amount, reason)
        elif payment.method == 'cod':
            payment.status = 'refunded'
            payment.refund_amount = requested_amount
            payment.refunded_at = timezone.now()
            payment.save()
            return Response({'success': True, 'message': 'COD marked as refunded.'})
            
        return Response({'error': 'Unsupported method.'}, status=status.HTTP_400_BAD_REQUEST)

    def _process_stripe_refund(self, payment, refund_amount=None, reason='requested_by_customer'):
        """Helper to process Stripe refund."""
        if not payment.transaction_id:
            return Response({'error': 'No transaction ID.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            params = {
                'payment_intent': payment.transaction_id,
                'reason': reason,
            }
            if refund_amount:
                params['amount'] = int(Decimal(refund_amount))

            refund = stripe.Refund.create(**params)
            
            payment.status = 'refunded' if refund.status == 'succeeded' else 'refund_pending'
            payment.save()
            
            PaymentLog.objects.create(
                payment=payment,
                action='stripe_refund',
                request_data=params,
                response_data={'refund_id': refund.id, 'status': refund.status},
                is_success=True
            )
            
            return Response({'success': True, 'refund_id': refund.id})
            
        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _process_vnpay_refund(self, payment, refund_amount=None, reason='requested_by_customer'):
        """
        Process VNPay refund using Celery task for reliability.
        Falls back to sync processing if Celery is unavailable.
        """
        client_ip = self._get_client_ip(self.request)
        user_name = self.request.user.email
        
        # Determine amount (full or partial)
        amount = Decimal(str(refund_amount)) if refund_amount else payment.amount.amount
        
        try:
            # Try async processing with Celery (preferred)
            task = process_vnpay_refund_task.delay(
                payment_id=str(payment.id),
                amount=str(amount),
                reason=reason,
                client_ip=client_ip,
                user_name=user_name
            )
            
            # Mark payment as processing
            payment.status = 'refund_pending'
            payment.save(update_fields=['status'])
            
            PaymentLog.objects.create(
                payment=payment,
                action='vnpay_refund_queued',
                request_data={'amount': str(amount), 'reason': reason, 'task_id': task.id},
                response_data={},
                is_success=True
            )
            
            return Response({
                'success': True,
                'message': 'Refund request queued for processing',
                'task_id': task.id,
                'status': 'pending'
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as celery_error:
            # Celery unavailable - fallback to sync processing
            logger.warning(f"Celery unavailable, processing refund synchronously: {celery_error}")
            return self._process_vnpay_refund_sync(payment, amount, reason, client_ip, user_name)

    def _process_vnpay_refund_sync(self, payment, amount, reason, client_ip, user_name):
        """
        Synchronous VNPay refund processing (fallback when Celery unavailable).
        """
        vnpay_service = VNPayService()
        
        try:
            response = vnpay_service.refund(payment, amount, reason, client_ip, user_name)
            
            if response.get('vnp_ResponseCode') == '00':
                payment.status = 'refunded'
                payment.refund_amount = amount
                payment.refunded_at = timezone.now()
                
                gw_response = payment.gateway_response or {}
                gw_response.update({'refund_response': response})
                payment.gateway_response = gw_response
                payment.save()
                
                PaymentLog.objects.create(
                    payment=payment,
                    action='vnpay_refund_sync',
                    request_data={'amount': str(amount), 'reason': reason},
                    response_data=response,
                    is_success=True
                )
                
                return Response({
                    'success': True,
                    'message': 'Refund successful',
                    'data': response
                })
            else:
                PaymentLog.objects.create(
                    payment=payment,
                    action='vnpay_refund_sync',
                    request_data={'amount': str(amount)},
                    response_data=response,
                    is_success=False,
                    error_message=response.get('vnp_Message', 'Unknown error')
                )
                return Response(
                    {'error': f"VNPay Error: {response.get('vnp_Message')}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"VNPay refund exception: {e}")
            return Response(
                {'error': f"Internal Error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )