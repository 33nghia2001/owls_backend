import hashlib
import hmac
import urllib.parse
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any

import requests
from django.conf import settings


# VNPay Refund API requires fields in this exact order for checksum calculation
# Reference: VNPay API Documentation v2.1.0
VNPAY_REFUND_HASH_FIELDS = [
    'vnp_RequestId',
    'vnp_Version', 
    'vnp_Command',
    'vnp_TmnCode',
    'vnp_TransactionType',
    'vnp_TxnRef',
    'vnp_Amount',
    'vnp_TransactionNo',
    'vnp_TransactionDate',
    'vnp_CreateBy',
    'vnp_CreateDate',
    'vnp_IpAddr',
    'vnp_OrderInfo',
]


class VNPayService:
    """Service for VNPay payment integration."""
    
    def __init__(self):
        self.tmn_code = settings.VNPAY_TMN_CODE
        self.hash_secret = settings.VNPAY_HASH_SECRET
        self.url = settings.VNPAY_URL
        self.return_url = settings.VNPAY_RETURN_URL
        self.refund_url = settings.VNPAY_REFUND_URL

    def create_payment_url(self, order, return_url=None, client_ip=None):
        """Create VNPay payment URL."""
        
        # VNPay yêu cầu số tiền * 100 và không có phần thập phân
        amount_decimal = Decimal(str(order.total.amount)) * Decimal('100')
        amount_int = int(amount_decimal.to_integral_value(rounding=ROUND_HALF_UP))
        
        # Cắt ID hoặc mã đơn hàng để vừa với giới hạn 20 ký tự của VNPay
        txn_ref = str(order.id)[:20]

        vnp_params = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'pay',
            'vnp_TmnCode': self.tmn_code,
            'vnp_Amount': amount_int,
            'vnp_CurrCode': 'VND',
            'vnp_TxnRef': txn_ref,
            'vnp_OrderInfo': f'Payment for order {order.order_number}',
            'vnp_OrderType': 'other',
            'vnp_Locale': 'vn',
            'vnp_ReturnUrl': return_url or self.return_url,
            'vnp_IpAddr': client_ip or '127.0.0.1',
            'vnp_CreateDate': datetime.now().strftime('%Y%m%d%H%M%S'),
        }
        
        # 1. Sắp xếp tham số theo bảng chữ cái
        sorted_params = sorted(vnp_params.items())
        
        # 2. Tạo query string
        query_string = urllib.parse.urlencode(sorted_params)
        
        # 3. Tạo secure hash (HMAC-SHA512)
        secure_hash = hmac.new(
            self.hash_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        # 4. Tạo URL cuối cùng
        payment_url = f"{self.url}?{query_string}&vnp_SecureHash={secure_hash}"
        
        return payment_url

    def verify_callback(self, params):
        """Verify VNPay callback signature."""
        # Lấy secure hash từ params trả về và loại bỏ nó khỏi dict để tính toán lại
        vnp_secure_hash = params.pop('vnp_SecureHash', '')
        params.pop('vnp_SecureHashType', None)
        
        # Sắp xếp và tạo query string từ dữ liệu nhận được
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)
        
        # Tính toán lại hash
        calculated_hash = hmac.new(
            self.hash_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        # So sánh hash với timing-safe comparison để chống timing attack
        return hmac.compare_digest(calculated_hash.lower(), vnp_secure_hash.lower())

    def is_success(self, response_code):
        """Check if payment was successful (Code 00)."""
        return response_code == '00'

    def refund(self, payment, amount, reason, user_ip, user_name='AdminSystem'):
        """
        Gửi yêu cầu hoàn tiền sang VNPay API.
        
        Args:
            payment: Payment object with transaction details
            amount: Amount to refund (in VND, not multiplied by 100)
            reason: Refund reason description
            user_ip: IP address of the user requesting refund
            user_name: Name of the user/admin requesting refund
            
        Returns:
            dict: VNPay API response
        """
        request_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(uuid.uuid4())[:4]
        vnp_create_date = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # 02: Hoàn tiền một phần, 03: Hoàn toàn bộ
        tr_type = '02' if amount < payment.amount.amount else '03'
        
        # Build params dict - all values must be strings for hash consistency
        vnp_params = {
            'vnp_RequestId': request_id,
            'vnp_Version': '2.1.0',
            'vnp_Command': 'refund',
            'vnp_TmnCode': self.tmn_code,
            'vnp_TransactionType': tr_type,
            'vnp_TxnRef': str(payment.order.id)[:20],
            'vnp_Amount': str(int(amount * 100)),  # VNPay expects amount * 100
            'vnp_TransactionNo': str(payment.transaction_id or ''),
            'vnp_TransactionDate': payment.created_at.strftime('%Y%m%d%H%M%S'),
            'vnp_CreateBy': user_name,
            'vnp_CreateDate': vnp_create_date,
            'vnp_IpAddr': user_ip,
            'vnp_OrderInfo': f"Refund: {reason}"[:255],  # Max 255 chars per VNPay spec
        }

        # Build checksum using the defined field order
        # This ensures consistency even if VNPay adds new fields
        secure_hash = self._build_refund_checksum(vnp_params)
        vnp_params['vnp_SecureHash'] = secure_hash

        try:
            response = requests.post(self.refund_url, json=vnp_params, timeout=30)
            return response.json()
        except requests.RequestException as e:
            return {'vnp_ResponseCode': '99', 'vnp_Message': str(e)}
    
    def _build_refund_checksum(self, params: Dict[str, Any]) -> str:
        """
        Build HMAC-SHA512 checksum for refund API.
        
        VNPay refund API requires fields joined by '|' in a specific order.
        This method uses VNPAY_REFUND_HASH_FIELDS constant to ensure
        correct field ordering and makes it easy to update if VNPay changes specs.
        
        Args:
            params: Dictionary of VNPay parameters
            
        Returns:
            str: HMAC-SHA512 hash in lowercase hex
        """
        # Build hash data from fields in the correct order
        hash_values = []
        for field in VNPAY_REFUND_HASH_FIELDS:
            value = params.get(field)
            # Convert to string, handle None explicitly
            if value is None:
                hash_values.append('')
            else:
                hash_values.append(str(value))
        
        hash_data = '|'.join(hash_values)
        
        return hmac.new(
            self.hash_secret.encode('utf-8'),
            hash_data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()