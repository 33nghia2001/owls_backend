import hashlib
import hmac
import urllib.parse
from datetime import datetime
from django.conf import settings


class VNPayService:
    """Service for VNPay payment integration."""
    
    def __init__(self):
        self.tmn_code = settings.VNPAY_TMN_CODE
        self.hash_secret = settings.VNPAY_HASH_SECRET
        self.url = settings.VNPAY_URL
        self.return_url = settings.VNPAY_RETURN_URL
    
    def create_payment_url(self, order, return_url=None, client_ip=None):
        """Create VNPay payment URL."""
        # IMPORTANT: Use Decimal arithmetic to avoid floating point precision issues
        # VNPay expects amount in smallest currency unit (VND has no decimals)
        from decimal import Decimal, ROUND_HALF_UP
        amount_decimal = Decimal(str(order.total.amount)) * Decimal('100')
        amount_int = int(amount_decimal.to_integral_value(rounding=ROUND_HALF_UP))
        
        vnp_params = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'pay',
            'vnp_TmnCode': self.tmn_code,
            'vnp_Amount': amount_int,  # VNPay requires amount * 100
            'vnp_CurrCode': 'VND',
            'vnp_TxnRef': str(order.id)[:20],  # Max 20 chars
            'vnp_OrderInfo': f'Payment for order {order.order_number}',
            'vnp_OrderType': 'other',
            'vnp_Locale': 'vn',
            'vnp_ReturnUrl': return_url or self.return_url,
            'vnp_IpAddr': client_ip or '127.0.0.1',
            'vnp_CreateDate': datetime.now().strftime('%Y%m%d%H%M%S'),
        }
        
        # Sort parameters
        sorted_params = sorted(vnp_params.items())
        
        # Build query string
        query_string = urllib.parse.urlencode(sorted_params)
        
        # Create secure hash
        hash_data = query_string
        secure_hash = hmac.new(
            self.hash_secret.encode('utf-8'),
            hash_data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        # Build final URL
        payment_url = f"{self.url}?{query_string}&vnp_SecureHash={secure_hash}"
        
        return payment_url
    
    def verify_callback(self, params):
        """Verify VNPay callback signature."""
        vnp_secure_hash = params.pop('vnp_SecureHash', '')
        params.pop('vnp_SecureHashType', None)
        
        # Sort and build query string
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)
        
        # Calculate hash
        calculated_hash = hmac.new(
            self.hash_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return calculated_hash.lower() == vnp_secure_hash.lower()
    
    def is_success(self, response_code):
        """Check if payment was successful."""
        return response_code == '00'
