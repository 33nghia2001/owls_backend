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


def process_vnpay_refund(transaction_id, amount, refund_reason='Customer request'):
    """
    Process VNPay refund request via official VNPay Refund API.
    
    SECURITY FIX: Implements actual VNPay refund API call to prevent 'Zombie Refunds'.
    This ensures money is actually returned to customer, not just marked as refunded in DB.
    
    Args:
        transaction_id: Payment transaction UUID (vnp_TxnRef)
        amount: Refund amount in VND (Decimal)
        refund_reason: Reason for refund (optional)
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'transaction_no': str (if success),
            'response_code': str,
            'error': str (if failed)
        }
    
    Implementation based on VNPay Refund API v2.1.0
    Docs: https://sandbox.vnpayment.vn/apis/docs/hoan-tien/
    """
    import requests
    import logging
    from .models import Payment, VNPayTransaction
    
    logger = logging.getLogger(__name__)
    
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
        
        # 2. Build refund request data
        vnpay = VNPay()
        create_date = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # VNPay requires amount in smallest currency unit (VND * 100)
        refund_amount = int(amount * 100)
        
        vnpay.request_data = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'refund',
            'vnp_TmnCode': settings.VNPAY_TMN_CODE,
            'vnp_TransactionType': '02',  # 02: Full refund, 03: Partial refund
            'vnp_TxnRef': str(transaction_id),  # Original transaction reference
            'vnp_Amount': refund_amount,
            'vnp_OrderInfo': f'Hoan tien: {refund_reason}',
            'vnp_TransactionNo': vnpay_transaction.vnp_TransactionNo,  # VNPay's transaction ID
            'vnp_TransactionDate': vnpay_transaction.created_at.strftime('%Y%m%d%H%M%S'),
            'vnp_CreateDate': create_date,
            'vnp_CreateBy': 'admin',  # User who initiated refund
            'vnp_IpAddr': '127.0.0.1',  # Server IP
        }
        
        # 3. Generate secure hash
        input_data = sorted(vnpay.request_data.items())
        hash_data = '&'.join([f"{key}={urllib.parse.quote_plus(str(val))}" for key, val in input_data])
        
        secure_hash = hmac.new(
            settings.VNPAY_HASH_SECRET.encode('utf-8'),
            hash_data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        vnpay.request_data['vnp_SecureHash'] = secure_hash
        
        # 4. Call VNPay Refund API
        refund_url = settings.VNPAY_REFUND_URL if hasattr(settings, 'VNPAY_REFUND_URL') else \
                     'https://sandbox.vnpayment.vn/merchant_webapi/api/transaction'
        
        logger.info(f"Calling VNPay refund API for transaction {transaction_id}, amount {amount}")
        
        response = requests.post(
            refund_url,
            json=vnpay.request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        response_data = response.json()
        
        # 5. Validate response signature
        vnp_secure_hash = response_data.pop('vnp_SecureHash', None)
        response_hash_data = '&'.join([
            f"{key}={urllib.parse.quote_plus(str(val))}" 
            for key, val in sorted(response_data.items())
        ])
        
        expected_hash = hmac.new(
            settings.VNPAY_HASH_SECRET.encode('utf-8'),
            response_hash_data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        if vnp_secure_hash != expected_hash:
            logger.error(f"VNPay refund response signature mismatch for {transaction_id}")
            return {
                'success': False,
                'error': 'Invalid response signature from VNPay',
                'message': 'Security validation failed'
            }
        
        # 6. Process response
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
        return {
            'success': False,
            'error': 'Payment not found',
            'message': f'No payment found with transaction ID: {transaction_id}'
        }
    except requests.RequestException as e:
        logger.error(f"VNPay API request failed: {str(e)}")
        return {
            'success': False,
            'error': f'Network error: {str(e)}',
            'message': 'Failed to connect to VNPay refund API'
        }
    except Exception as e:
        logger.exception(f"Unexpected error processing VNPay refund: {str(e)}")
        return {
            'success': False,
            'error': f'System error: {str(e)}',
            'message': 'An unexpected error occurred during refund processing'
        }
