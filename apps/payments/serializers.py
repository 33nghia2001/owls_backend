from rest_framework import serializers
from .models import Payment, PaymentLog


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payments."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'order_number', 'method', 'status',
            'amount', 'transaction_id', 'created_at', 'completed_at'
        ]
        read_only_fields = ['id', 'transaction_id', 'created_at', 'completed_at']


class PaymentLogSerializer(serializers.ModelSerializer):
    """Serializer for payment logs."""
    
    class Meta:
        model = PaymentLog
        fields = ['id', 'action', 'is_success', 'error_message', 'created_at']


class CreatePaymentSerializer(serializers.Serializer):
    """Serializer for creating a payment."""
    order_id = serializers.UUIDField()
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    # SECURITY: return_url removed to prevent Open Redirect attacks
    # All redirects now use settings.FRONTEND_URL


class VNPayCallbackSerializer(serializers.Serializer):
    """Serializer for VNPay callback data."""
    vnp_TmnCode = serializers.CharField()
    vnp_Amount = serializers.CharField()
    vnp_BankCode = serializers.CharField(required=False)
    vnp_BankTranNo = serializers.CharField(required=False)
    vnp_CardType = serializers.CharField(required=False)
    vnp_PayDate = serializers.CharField(required=False)
    vnp_OrderInfo = serializers.CharField()
    vnp_TransactionNo = serializers.CharField()
    vnp_ResponseCode = serializers.CharField()
    vnp_TransactionStatus = serializers.CharField()
    vnp_TxnRef = serializers.CharField()
    vnp_SecureHash = serializers.CharField()
