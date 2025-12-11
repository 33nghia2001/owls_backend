from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from decimal import Decimal
import stripe

from .models import Payment, PaymentLog
from .serializers import PaymentSerializer, CreatePaymentSerializer
from .vnpay import VNPayService
from apps.orders.models import Order


# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for payments."""
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Optimized query with select_related
        return Payment.objects.filter(
            user=self.request.user
        ).select_related(
            'order',
            'user'
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
            }
        )
        
        if not created:
            payment.method = method
            payment.save()
        
        # Process based on method
        if method == 'cod':
            # Cash on delivery - mark as pending
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
        
        elif method == 'stripe':
            # Create Stripe checkout session
            try:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'vnd',
                            'product_data': {
                                'name': f'Order {order.order_number}',
                            },
                            'unit_amount': int(order.total.amount),
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    # SECURITY: Always use FRONTEND_URL to prevent Open Redirect
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
                
                # Log the request
                PaymentLog.objects.create(
                    payment=payment,
                    action='create_checkout_session',
                    request_data={'order_id': str(order.id)},
                    response_data={'session_id': checkout_session.id},
                    is_success=True
                )
                
                return Response({
                    'payment': PaymentSerializer(payment).data,
                    'checkout_url': checkout_session.url
                })
                
            except stripe.error.StripeError as e:
                PaymentLog.objects.create(
                    payment=payment,
                    action='create_checkout_session',
                    request_data={'order_id': str(order.id)},
                    response_data={},
                    is_success=False,
                    error_message=str(e)
                )
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        elif method == 'vnpay':
            # Create VNPay payment URL
            vnpay_service = VNPayService()
            # SECURITY: Use server-configured return URL to prevent Open Redirect
            client_ip = self._get_client_ip(request)
            
            try:
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
                PaymentLog.objects.create(
                    payment=payment,
                    action='create_vnpay_url',
                    request_data={'order_id': str(order.id)},
                    response_data={},
                    is_success=False,
                    error_message=str(e)
                )
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(
            {'error': 'Invalid payment method.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    @transaction.atomic
    def vnpay_return(self, request):
        """Handle VNPay return callback."""
        params = dict(request.GET)
        # Flatten list values
        params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
        
        vnpay_service = VNPayService()
        
        # Verify signature
        if not vnpay_service.verify_callback(params.copy()):
            return Response(
                {'error': 'Invalid signature'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get order and payment
        order_id = params.get('vnp_TxnRef')
        try:
            order = Order.objects.get(id=order_id)
            payment = order.payment
        except (Order.DoesNotExist, Payment.DoesNotExist):
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Idempotency check - prevent duplicate processing
        if payment.status == 'completed':
            return Response({
                'success': True,
                'message': 'Payment already processed',
                'order_id': str(order.id)
            })
        
        # Validate amount matches order total (VNPay sends amount * 100)
        vnp_amount = Decimal(params.get('vnp_Amount', 0)) / 100
        if vnp_amount != order.total.amount:
            return Response(
                {'error': 'Amount mismatch'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Log callback
        response_code = params.get('vnp_ResponseCode')
        is_success = vnpay_service.is_success(response_code)
        
        PaymentLog.objects.create(
            payment=payment,
            action='vnpay_callback',
            request_data=params,
            response_data={'response_code': response_code},
            is_success=is_success
        )
        
        if is_success:
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
                payment = Payment.objects.get(id=payment_id)
                order = payment.order
                
                # Idempotency check - prevent duplicate processing
                if payment.status == 'completed':
                    return Response({'status': 'already_processed'})
                
                payment.status = 'completed'
                payment.transaction_id = session.get('payment_intent', '')
                payment.gateway_response = dict(session)
                payment.completed_at = timezone.now()
                payment.save()
                
                order.payment_status = 'paid'
                order.status = 'confirmed'
                order.confirmed_at = timezone.now()
                order.save()
                
                PaymentLog.objects.create(
                    payment=payment,
                    action='stripe_webhook',
                    request_data={'event_type': event['type']},
                    response_data={'session_id': session['id']},
                    is_success=True
                )
                
            except Payment.DoesNotExist:
                pass
        
        return Response({'status': 'success'})
    
    @action(detail=False, methods=['get', 'post'], permission_classes=[AllowAny])
    @transaction.atomic
    def vnpay_ipn(self, request):
        """
        Handle VNPay IPN (Instant Payment Notification) - Server-to-Server callback.
        
        CRITICAL: This endpoint is called directly by VNPay servers, not by user's browser.
        This ensures payment confirmation even if user closes browser after payment.
        
        VNPay expects specific response format:
        - RspCode=00, Message=Confirm Success - for successful confirmation
        - RspCode=XX - for errors (01=Order not found, 02=Already confirmed, etc.)
        """
        # Support both GET and POST from VNPay
        if request.method == 'POST':
            params = dict(request.POST)
        else:
            params = dict(request.GET)
        
        # Flatten list values
        params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
        
        vnpay_service = VNPayService()
        
        # Verify signature first
        if not vnpay_service.verify_callback(params.copy()):
            return Response({
                'RspCode': '97',
                'Message': 'Invalid Signature'
            })
        
        # Get order and payment
        order_id = params.get('vnp_TxnRef')
        try:
            order = Order.objects.select_for_update().get(id=order_id)
            payment = order.payment
        except Order.DoesNotExist:
            return Response({
                'RspCode': '01',
                'Message': 'Order not found'
            })
        except Payment.DoesNotExist:
            return Response({
                'RspCode': '01',
                'Message': 'Payment not found'
            })
        
        # Idempotency check - already confirmed
        if payment.status == 'completed':
            return Response({
                'RspCode': '02',
                'Message': 'Order already confirmed'
            })
        
        # Validate amount matches order total (VNPay sends amount * 100)
        vnp_amount = Decimal(params.get('vnp_Amount', 0)) / 100
        if vnp_amount != order.total.amount:
            return Response({
                'RspCode': '04',
                'Message': 'Invalid Amount'
            })
        
        # Log callback
        response_code = params.get('vnp_ResponseCode')
        is_success = vnpay_service.is_success(response_code)
        
        PaymentLog.objects.create(
            payment=payment,
            action='vnpay_ipn',
            request_data=params,
            response_data={'response_code': response_code},
            is_success=is_success
        )
        
        if is_success:
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
                'RspCode': '00',
                'Message': 'Confirm Success'
            })
        else:
            payment.status = 'failed'
            payment.gateway_response = params
            payment.save()
            
            return Response({
                'RspCode': '00',
                'Message': 'Confirm Success'  # VNPay expects 00 even for failed payments
            })
