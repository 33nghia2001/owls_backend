from .base import *

# Override for Development
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Email in Console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# VNPay Local URL
VNPAY_RETURN_URL = env('VNPAY_RETURN_URL', default='http://localhost:8000/api/v1/payments/vnpay/return/')

# Turnstile Test Mode
TURNSTILE_TEST_MODE = True