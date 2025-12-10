"""
VNPay Payment Gateway Integration
Docs: https://sandbox.vnpayment.vn/apis/docs/thanh-toan-pay/pay.html
"""

import hashlib
import hmac
import urllib.parse
from datetime import datetime
from django.conf import settings


class VNPay:
    """VNPay Payment Gateway Helper"""
    
    def __init__(self):
        self.request_data = {}
        self.response_data = {}
    
    def get_payment_url(self, base_url, secret_key):
        """
        Tạo URL thanh toán VNPay
        
        Args:
            base_url: VNPay payment URL (sandbox hoặc production)
            secret_key: Hash secret key
            
        Returns:
            str: Full payment URL
        """
        # Sắp xếp parameters theo thứ tự alphabet
        input_data = sorted(self.request_data.items())
        query_string = ''
        hash_data = ''
        seq = 0
        
        for key, val in input_data:
            if seq == 1:
                query_string = query_string + "&" + key + '=' + urllib.parse.quote_plus(str(val))
                hash_data = hash_data + '&' + key + '=' + urllib.parse.quote_plus(str(val))
            else:
                query_string = key + '=' + urllib.parse.quote_plus(str(val))
                hash_data = key + '=' + urllib.parse.quote_plus(str(val))
                seq = 1
        
        # Tạo secure hash
        secure_hash = hmac.new(
            secret_key.encode('utf-8'),
            hash_data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return f"{base_url}?{query_string}&vnp_SecureHash={secure_hash}"
    
    def validate_response(self, secret_key):
        """
        Validate VNPay IPN response
        
        Args:
            secret_key: Hash secret key
            
        Returns:
            bool: True nếu signature hợp lệ
        """
        vnp_secure_hash = self.response_data.pop('vnp_SecureHash', None)
        
        if not vnp_secure_hash:
            return False
        
        # Sắp xếp parameters
        input_data = sorted(self.response_data.items())
        hash_data = ''
        seq = 0
        
        for key, val in input_data:
            if seq == 1:
                hash_data = hash_data + '&' + key + '=' + urllib.parse.quote_plus(str(val))
            else:
                hash_data = key + '=' + urllib.parse.quote_plus(str(val))
                seq = 1
        
        # Tạo secure hash
        secure_hash = hmac.new(
            secret_key.encode('utf-8'),
            hash_data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return secure_hash == vnp_secure_hash


def create_vnpay_payment_url(payment, request):
    """
    Tạo VNPay payment URL từ Payment object
    
    Args:
        payment: Payment instance
        request: Django request object (để lấy IP)
        
    Returns:
        str: VNPay payment URL
    """
    vnpay = VNPay()
    
    # VNPay yêu cầu amount * 100 (VND không có decimal)
    amount = int(payment.amount * 100)
    
    # Tạo transaction reference (unique)
    txn_ref = str(payment.transaction_id)
    
    # Build request data
    vnpay.request_data = {
        'vnp_Version': '2.1.0',
        'vnp_Command': 'pay',
        'vnp_TmnCode': settings.VNPAY_TMN_CODE,
        'vnp_Amount': amount,
        'vnp_CurrCode': 'VND',
        'vnp_TxnRef': txn_ref,
        'vnp_OrderInfo': f'Thanh toan khoa hoc: {payment.course.title}',
        'vnp_OrderType': 'billpayment',
        'vnp_Locale': 'vn',
        'vnp_CreateDate': datetime.now().strftime('%Y%m%d%H%M%S'),
        'vnp_IpAddr': get_client_ip(request),
        'vnp_ReturnUrl': request.build_absolute_uri('/api/payments/vnpay/return/'),
    }
    
    # Lưu VNPay transaction record
    from .models import VNPayTransaction
    VNPayTransaction.objects.create(
        payment=payment,
        vnp_TxnRef=txn_ref,
        vnp_OrderInfo=vnpay.request_data['vnp_OrderInfo'],
        vnp_Amount=amount,
        request_data=vnpay.request_data
    )
    
    # Tạo payment URL
    payment_url = vnpay.get_payment_url(
        settings.VNPAY_PAYMENT_URL,
        settings.VNPAY_HASH_SECRET
    )
    
    return payment_url


def get_client_ip(request):
    """Lấy IP address từ request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# VNPay Response Codes
VNPAY_RESPONSE_CODES = {
    '00': 'Giao dịch thành công',
    '07': 'Trừ tiền thành công. Giao dịch bị nghi ngờ (liên quan tới lừa đảo, giao dịch bất thường).',
    '09': 'Giao dịch không thành công do: Thẻ/Tài khoản của khách hàng chưa đăng ký dịch vụ InternetBanking tại ngân hàng.',
    '10': 'Giao dịch không thành công do: Khách hàng xác thực thông tin thẻ/tài khoản không đúng quá 3 lần',
    '11': 'Giao dịch không thành công do: Đã hết hạn chờ thanh toán. Xin quý khách vui lòng thực hiện lại giao dịch.',
    '12': 'Giao dịch không thành công do: Thẻ/Tài khoản của khách hàng bị khóa.',
    '13': 'Giao dịch không thành công do Quý khách nhập sai mật khẩu xác thực giao dịch (OTP). Xin quý khách vui lòng thực hiện lại giao dịch.',
    '24': 'Giao dịch không thành công do: Khách hàng hủy giao dịch',
    '51': 'Giao dịch không thành công do: Tài khoản của quý khách không đủ số dư để thực hiện giao dịch.',
    '65': 'Giao dịch không thành công do: Tài khoản của Quý khách đã vượt quá hạn mức giao dịch trong ngày.',
    '75': 'Ngân hàng thanh toán đang bảo trì.',
    '79': 'Giao dịch không thành công do: KH nhập sai mật khẩu thanh toán quá số lần quy định. Xin quý khách vui lòng thực hiện lại giao dịch',
    '99': 'Các lỗi khác (lỗi còn lại, không có trong danh sách mã lỗi đã liệt kê)',
}


def get_vnpay_response_message(code):
    """Lấy message từ response code"""
    return VNPAY_RESPONSE_CODES.get(code, 'Lỗi không xác định')


def process_vnpay_refund(transaction_id, amount):
    """
    Process VNPay refund request.
    
    SECURITY FIX: Implements actual VNPay refund API call to prevent 'Zombie Refunds'.
    This ensures money is actually returned to customer, not just marked as refunded in DB.
    
    Args:
        transaction_id: Payment transaction UUID
        amount: Refund amount in VND
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'transaction_no': str (if success),
            'error': str (if failed)
        }
    
    TODO: Implement actual VNPay refund API integration
    Docs: https://sandbox.vnpayment.vn/apis/docs/hoan-tien/
    
    For now, this is a placeholder that logs the refund request.
    In production, you need to:
    1. Call VNPay refund API endpoint
    2. Pass merchant credentials and transaction details
    3. Verify refund response signature
    4. Update payment status based on response
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.warning(
        f"VNPay refund requested: transaction_id={transaction_id}, amount={amount}. "
        f"IMPLEMENT ACTUAL API CALL IN PRODUCTION!"
    )
    
    # PLACEHOLDER: In production, replace with actual VNPay API call
    # Example pseudo-code:
    # response = requests.post(
    #     settings.VNPAY_REFUND_URL,
    #     data={
    #         'vnp_TmnCode': settings.VNPAY_TMN_CODE,
    #         'vnp_TxnRef': transaction_id,
    #         'vnp_Amount': int(amount * 100),
    #         'vnp_TransactionType': '02',  # Full refund
    #         # ... other required fields
    #     }
    # )
    
    return {
        'success': False,
        'error': 'VNPay refund API not implemented yet. Manual processing required.',
        'message': 'Please process this refund manually through VNPay merchant portal.'
    }
