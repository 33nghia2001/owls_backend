"""
Base Settings for Mini LMS Project.
Common configuration shared between development and production.
"""
from pathlib import Path
import os
from datetime import timedelta
import environ

# 1. Base Directory
# Lưu ý: Vì file này nằm trong thư mục settings/, nên phải .parent 3 lần để ra root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 2. Environment Variables
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# 3. Core Settings
SECRET_KEY = env('DJANGO_SECRET_KEY')
# Mặc định False để an toàn, Local sẽ override thành True
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=[])

AUTH_USER_MODEL = 'users.User'
ROOT_URLCONF = 'backend.urls'
WSGI_APPLICATION = 'backend.wsgi.application'
ASGI_APPLICATION = 'backend.asgi.application'

# 4. Apps Definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'daphne',       # OPTIMIZATION: Must be at the very top for ASGI
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    'cloudinary_storage',
    'cloudinary',
    'turnstile',
    'social_django',
    'channels',
]

LOCAL_APPS = [
    'apps.users',
    'apps.courses',
    'apps.enrollments',
    'apps.payments',
    'apps.reviews',
    'apps.notifications',
]

# OPTIMIZATION: Daphne phải đứng đầu list INSTALLED_APPS
INSTALLED_APPS = ['daphne'] + DJANGO_APPS + [app for app in THIRD_PARTY_APPS if app != 'daphne'] + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'backend.middleware.AdminIPWhitelistMiddleware',
]

# 5. Templates & Password Validation
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# 6. Database
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR}/db.sqlite3')
}

# Test database configuration - avoid locking issues
if env.bool('DJANGO_DEBUG', default=False):
    DATABASES['default']['TEST'] = {
        'NAME': 'test_owls_db',  # Use different name to avoid conflicts
    }

# 7. Localization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 8. Static & Media Files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': env('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY': env('CLOUDINARY_API_KEY', default=''),
    'API_SECRET': env('CLOUDINARY_API_SECRET', default=''),
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

if CLOUDINARY_STORAGE['CLOUD_NAME']:
    STORAGES["default"]["BACKEND"] = 'cloudinary_storage.storage.MediaCloudinaryStorage'
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

# 9. DRF & JWT
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'review_create': '10/day',
        'payment': '5/hour',
        'register': '5/hour',
        'ws_ticket': '10/min',  # WebSocket ticket generation
    }
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'UPDATE_LAST_LOGIN': True,
}

# 10. CORS & Frontend
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=["http://localhost:3000"])
CORS_ALLOW_CREDENTIALS = True
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:3000')

# Backend URL (for OAuth redirects - prevent Host Header Injection)
BACKEND_URL = env('BACKEND_URL', default='http://localhost:8000')

# WebSocket Base URL (for mobile/web clients)
# Development: ws://localhost:8000
# Production: wss://api.yourdomain.com
WS_BASE_URL = env('WS_BASE_URL', default='ws://localhost:8000')

# 10.5. IP Address Detection (for rate limiting behind proxies/CDN)
# SECURITY FIX: Configure trusted proxies to prevent IP spoofing
# Used by django-ipware for accurate client IP detection
IPWARE_META_PRECEDENCE_ORDER = (
    'HTTP_X_FORWARDED_FOR',  # Standard proxy header
    'X_FORWARDED_FOR',
    'HTTP_CLIENT_IP',
    'HTTP_X_REAL_IP',
    'HTTP_X_FORWARDED',
    'HTTP_X_CLUSTER_CLIENT_IP',
    'HTTP_FORWARDED_FOR',
    'HTTP_FORWARDED',
    'REMOTE_ADDR',  # Fallback to direct connection IP
)

# Only trust proxy headers if behind a known proxy (Cloudflare, Nginx, etc.)
# In production, set IPWARE_TRUSTED_PROXY_LIST in environment variables
IPWARE_TRUSTED_PROXY_LIST = env.list('IPWARE_TRUSTED_PROXY_LIST', default=[])

# SECURITY WARNING (Gemini Audit): Validate proxy configuration in production!
# If deploying behind Cloudflare/Nginx without setting IPWARE_TRUSTED_PROXY_LIST:
# 1. get_client_ip() may return proxy IP (10.0.0.1) for all requests
# 2. Attackers can spoof X-Forwarded-For: 127.0.0.1 to bypass IP whitelist
# 
# For Cloudflare, set in .env:
# IPWARE_TRUSTED_PROXY_LIST=173.245.48.0/20,103.21.244.0/22,103.22.200.0/22,103.31.4.0/22,141.101.64.0/18,108.162.192.0/18,190.93.240.0/20,188.114.96.0/20,197.234.240.0/22,198.41.128.0/17,162.158.0.0/15,104.16.0.0/13,104.24.0.0/14,172.64.0.0/13,131.0.72.0/22
#
# For AWS ALB/NLB, set your load balancer's private IP range
# IPWARE_TRUSTED_PROXY_LIST=10.0.0.0/8,172.16.0.0/12
#
# WARNING: Leaving this empty in production with a reverse proxy is a SECURITY RISK!

# 11. Redis & Celery & Channels
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
        'KEY_PREFIX': 'lms',
        'TIMEOUT': 60 * 15,
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'cleanup-expired-payments': {
        'task': 'apps.payments.tasks.cleanup_expired_payments',
        'schedule': crontab(minute='*/30'),
    },
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [REDIS_URL]},
    },
}

# 12. External Services
# Social Auth
AUTHENTICATION_BACKENDS = [
    'social_core.backends.google.GoogleOAuth2',
    'django.contrib.auth.backends.ModelBackend',
]
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env('GOOGLE_OAUTH2_KEY', default='')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env('GOOGLE_OAUTH2_SECRET', default='')

# Email
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@example.com')
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

# Documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'Mini LMS API',
    'DESCRIPTION': 'API documentation for the Online Learning Platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# VNPay Payment Gateway
VNPAY_TMN_CODE = env('VNPAY_TMN_CODE', default='')
VNPAY_HASH_SECRET = env('VNPAY_HASH_SECRET', default='')
VNPAY_PAYMENT_URL = env('VNPAY_PAYMENT_URL', default='https://sandbox.vnpayment.vn/paymentv2/vpcpay.html')
VNPAY_API_URL = env('VNPAY_API_URL', default='https://sandbox.vnpayment.vn/merchant_webapi/api/transaction')
# Refund API endpoint (same as API_URL in VNPay v2.1.0)
VNPAY_REFUND_URL = env('VNPAY_REFUND_URL', default='https://sandbox.vnpayment.vn/merchant_webapi/api/transaction')
# Logic VNPAY_RETURN_URL sẽ được xử lý ở production.py/local.py để an toàn hơn

# Turnstile
TURNSTILE_SITEKEY = env('TURNSTILE_SITEKEY', default='')
TURNSTILE_SECRET = env('TURNSTILE_SECRET', default='')
TURNSTILE_TEST_MODE = env.bool('TURNSTILE_TEST_MODE', default=False)

# Security (Defaults)
ADMIN_IP_WHITELIST = env('ADMIN_IP_WHITELIST', default='')
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# OPTIMIZATION: Thêm Logging (Cực kỳ quan trọng cho Production)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.payments': {  # Log riêng cho module thanh toán
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}