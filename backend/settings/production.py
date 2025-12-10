# backend/settings/production.py

from .base import *

"""
PRODUCTION SETTINGS
Configurations for the live server environment.
Security is paramount here.
"""

# 1. Critical Settings
# ------------------------------------------------------------------------------
DEBUG = False

# Bắt buộc phải lấy từ biến môi trường, không có giá trị mặc định để tránh sơ suất
SECRET_KEY = env('DJANGO_SECRET_KEY')
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS')


# 2. Security Hardening (HTTPS & Headers)
# ------------------------------------------------------------------------------
# Chuyển hướng mọi request HTTP sang HTTPS
SECURE_SSL_REDIRECT = env.bool('DJANGO_SECURE_SSL_REDIRECT', default=True)

# Bảo vệ Cookies (chỉ gửi qua HTTPS)
SESSION_COOKIE_SECURE = env.bool('DJANGO_SESSION_COOKIE_SECURE', default=True)
CSRF_COOKIE_SECURE = env.bool('DJANGO_CSRF_COOKIE_SECURE', default=True)

# Browser Security Headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'  # Chống Clickjacking (không cho nhúng iframe)

# HTTP Strict Transport Security (HSTS)
# Bắt buộc trình duyệt luôn dùng HTTPS trong thời gian dài (tránh SSL Stripping)
# Lưu ý: Chỉ bật khi bạn chắc chắn đã có SSL/HTTPS hoạt động ổn định
SECURE_HSTS_SECONDS = 31536000  # 1 năm
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True


# 3. Email Configuration (SMTP)
# ------------------------------------------------------------------------------
# Sử dụng SMTP thật (Gmail, AWS SES, SendGrid...) thay vì Console
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_TIMEOUT = 5


# 4. Third-Party Integrations
# ------------------------------------------------------------------------------

# VNPay
# Bắt buộc lấy từ Env để đảm bảo redirect đúng về domain thật (vd: yourdomain.com)
# Tuyệt đối không để default là localhost ở đây
VNPAY_RETURN_URL = env('VNPAY_RETURN_URL')

# Cloudflare Turnstile
# Tắt chế độ Test để bắt buộc xác thực Captcha thật
TURNSTILE_TEST_MODE = False


# 5. Error Tracking & Monitoring (Sentry)
# ------------------------------------------------------------------------------
SENTRY_DSN = env('SENTRY_DSN', default=None)

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            RedisIntegration(),
            CeleryIntegration(),
        ],
        # Set to 0.0 ~ 0.2 in production to avoid performance impact
        traces_sample_rate=env.float('SENTRY_TRACES_SAMPLE_RATE', default=0.1),
        # If True, might log sensitive data like user emails. Use with caution.
        send_default_pii=True,
        environment="production",
    )