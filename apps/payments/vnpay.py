"""
VNPay Payment Gateway Integration
Docs: https://sandbox.vnpayment.vn/apis/docs/thanh-toan-pay/pay.html
Refund Docs: https://sandbox.vnpayment.vn/apis/docs/hoan-tien/
"""

import hashlib
import hmac
import urllib.parse
import requests
import logging
from datetime import datetime
from django.conf import settings

# Import local models inside functions to avoid circular imports if necessary
# or use apps.get_model if this utility is imported in models.py

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

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

# ==============================================================================
# VNPAY HELPER CLASS
# ==============================================================================

class VNPay:
    """VNPay Payment Gateway Helper"""

    def __init__(self):
        self.request_data = {}
        self.response_data = {}

    def _build_query_string(self, data):
        """
        Builds a sorted query string from a dictionary.
        Used for both generating payment URLs and hashing.
        """
        # Sắp xếp parameters theo key
        sorted_data = sorted(data.items())
        
        # Tạo list các chuỗi "key=value" đã được URL encode
        elements = [
            f"{key}={urllib.parse.quote_plus(str(val))}" 
            for key, val in sorted_data
        ]
        
        # Nối lại bằng '&'
        return '&'.join(elements)

    def _generate_signature(self, data_str, secret_key):
        """
        Generates HMAC-SHA512 signature.
        """
        return hmac.new(
            secret_key.encode('utf-8'),
            data_str.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

    def get_payment_url(self, base_url, secret_key):
        """
        Tạo URL thanh toán VNPay
        """
        # 1. Tạo chuỗi dữ liệu (hash data)
        query_string = self._build_query_string(self.request_data)
        
        # 2. Tạo chữ ký bảo mật
        secure_hash = self._generate_signature(query_string, secret_key)
        
        # 3. Trả về URL đầy đủ
        return f"{base_url}?{query_string}&vnp_SecureHash={secure_hash}"

    def validate_response(self, secret_key):
        """
        Validate VNPay IPN/Return response signature
        """
        # Lấy chữ ký từ response và loại bỏ khỏi data cần hash
        vnp_secure_hash = self.response_data.pop('vnp_SecureHash', None)
        
        # Nếu response cũng chứa vnp_SecureHashType thì bỏ qua luôn (tùy version API)
        self.response_data.pop('vnp_SecureHashType', None)
        
        if not vnp_secure_hash:
            return False
            
        # 1. Tạo lại chuỗi dữ liệu từ response data
        # Lưu ý: Cần lọc bỏ các field rỗng hoặc None nếu VNPay yêu cầu (thường là không cần với IPN v2)
        clean_data = {k: v for k, v in self.response_data.items() if v != ''}
        hash_data = self._build_query_string(clean_data)
        
        # 2. Tạo chữ ký mong đợi
        expected_hash = self._generate_signature(hash_data, secret_key)
        
        # 3. So sánh (nên dùng compare_digest để tránh timing attacks)
        return hmac.compare_digest(vnp_secure_hash, expected_hash)

    def send_refund_request(self, refund_url, secret_key):
        """
        Gửi yêu cầu hoàn tiền đến VNPay API.
        
        Returns:
            dict: Parsed JSON response from VNPay
        """
        # 1. Tạo chữ ký cho request data
        hash_data = self._build_query_string(self.request_data)
        secure_hash = self._generate_signature(hash_data, secret_key)
        
        # 2. Thêm chữ ký vào request data
        self.request_data['vnp_SecureHash'] = secure_hash
        
        # 3. Gửi request
        try:
            response = requests.post(
                refund_url,
                json=self.request_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"VNPay Refund API Error: {str(e)}")
            raise

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_client_ip(request):
    """Lấy IP address từ request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_vnpay_response_message(code):
    """Lấy message từ response code"""
    return VNPAY_RESPONSE_CODES.get(code, 'Lỗi không xác định')


def create_vnpay_payment_url(payment, request):
    """
    Tạo VNPay payment URL từ Payment object
    """
    vnpay = VNPay()
    
    # VNPay yêu cầu amount * 100 (VND không có decimal)
    amount = int(payment.amount * 100)
    
    # Tạo transaction reference (unique)
    txn_ref = str(payment.transaction_id)
    
    # Return URL
    return_url = settings.VNPAY_RETURN_URL
    if not return_url:
        # Fallback to dynamic build if not in settings (Legacy support)
        return_url = request.build_absolute_uri('/api/v1/payments/vnpay/return/')

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
        'vnp_ReturnUrl': return_url,
    }
    
    # Lưu VNPay transaction record
    # Import bên trong để tránh circular dependency
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


def process_vnpay_refund(transaction_id, amount, refund_reason='Customer request'):
    """
    Process VNPay refund request via official VNPay Refund API.
    
    SECURITY FIX: Implements actual VNPay refund API call to prevent 'Zombie Refunds'.
    This ensures money is actually returned to customer.
    
    Args:
        transaction_id: Payment transaction UUID (vnp_TxnRef)
        amount: Refund amount in VND (Decimal)
        refund_reason: Reason for refund (optional)
    """
    from .models import Payment
    
    try:
        # 1. Get payment and original transaction info
        payment = Payment.objects.select_related('vnpay_transaction').get(
            transaction_id=transaction_id
        )
        vnpay_transaction = payment.vnpay_transaction
        
        if not vnpay_transaction or not vnpay_transaction.vnp_TransactionNo:
            return {
                'success': False,
                'error': 'Original VNPay transaction not found or incomplete',
                'message': 'Cannot process refund without valid VNPay transaction reference'
            }
        
        # 2. Build refund request data using Helper Class
        vnpay = VNPay()
        create_date = datetime.now().strftime('%Y%m%d%H%M%S')
        refund_amount = int(amount * 100)
        
        vnpay.request_data = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'refund',
            'vnp_TmnCode': settings.VNPAY_TMN_CODE,
            'vnp_TransactionType': '02',  # 02: Full refund, 03: Partial refund
            'vnp_TxnRef': str(transaction_id),
            'vnp_Amount': refund_amount,
            'vnp_OrderInfo': f'Hoan tien: {refund_reason}',
            'vnp_TransactionNo': vnpay_transaction.vnp_TransactionNo,
            'vnp_TransactionDate': vnpay_transaction.created_at.strftime('%Y%m%d%H%M%S'),
            'vnp_CreateDate': create_date,
            'vnp_CreateBy': 'admin',
            'vnp_IpAddr': '127.0.0.1', # Server IP initiating the request
        }
        
        # 3. Call API using Helper Method
        refund_url = getattr(settings, 'VNPAY_REFUND_URL', 'https://sandbox.vnpayment.vn/merchant_webapi/api/transaction')
        
        logger.info(f"Initiating VNPay refund for {transaction_id}, amount {amount}")
        response_data = vnpay.send_refund_request(refund_url, settings.VNPAY_HASH_SECRET)
        
        # 4. Validate response signature
        # Create a new helper instance for response validation to avoid data pollution
        validator = VNPay()
        validator.response_data = response_data.copy()
        
        if not validator.validate_response(settings.VNPAY_HASH_SECRET):
            logger.error(f"VNPay refund response signature mismatch for {transaction_id}")
            return {
                'success': False,
                'error': 'Invalid response signature from VNPay',
                'message': 'Security validation failed'
            }
        
        # 5. Process Result
        response_code = response_data.get('vnp_ResponseCode')
        
        if response_code == '00':
            logger.info(f"VNPay refund successful for {transaction_id}")
            return {
                'success': True,
                'message': 'Refund processed successfully',
                'transaction_no': response_data.get('vnp_TransactionNo'),
                'response_code': response_code,
                'response_data': response_data
            }
        else:
            error_message = get_vnpay_response_message(response_code)
            logger.warning(f"VNPay refund failed for {transaction_id}: {error_message}")
            return {
                'success': False,
                'error': error_message,
                'response_code': response_code,
                'message': f'VNPay rejected refund: {error_message}'
            }
            
    except Payment.DoesNotExist:
        logger.error(f"Payment not found: {transaction_id}")
        return {'success': False, 'error': 'Payment not found', 'message': 'Payment record missing'}
    except Exception as e:
        logger.exception(f"Unexpected error processing VNPay refund: {str(e)}")
        return {'success': False, 'error': str(e), 'message': 'System error during refund'}