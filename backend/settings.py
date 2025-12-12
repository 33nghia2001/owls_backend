import os
from pathlib import Path
from datetime import timedelta
import environ

# Init Environment
env = environ.Env(DEBUG=(bool, False))
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

# Frontend URL (for redirects after payment, etc.)
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:3000')

# Application Definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',
    'django_filters',
    'mptt',
    'guardian',
    'phonenumber_field',
    'djmoney',
    'import_export',
    'storages',
    'django_celery_results',
    'django_celery_beat',
    'debug_toolbar',
    'channels',  # Django Channels for WebSocket support
]

LOCAL_APPS = [
    'apps.users',
    'apps.vendors',
    'apps.products',
    'apps.cart',
    'apps.orders',
    'apps.payments',
    'apps.reviews',
    'apps.coupons',
    'apps.wishlist',
    'apps.shipping',
    'apps.notifications',
    'apps.analytics',
    'apps.messaging',
    'apps.inventory',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'backend.middleware.JWTCookieMiddleware',  # Extract JWT from httpOnly cookie
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
]

ROOT_URLCONF = 'backend.urls'

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

WSGI_APPLICATION = 'backend.wsgi.application'

DATABASES = {
    'default': env.db(),
}

# Authentication backends
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Modern Storage Configuration (Django 4.2+)
USE_S3 = env.bool('USE_S3', default=False)

if USE_S3:
    AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME', default='ap-southeast-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    AWS_DEFAULT_ACL = 'public-read'
    
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

AUTH_USER_MODEL = 'users.Users'

# CORS Settings - Load from environment for production flexibility
# SECURITY WARNING: In production, ensure CORS_ALLOWED_ORIGINS only contains
# your actual frontend domain(s). NEVER use '*' with CORS_ALLOW_CREDENTIALS=True
# as this creates a severe security vulnerability (CSRF/credential theft).
# Example for production .env:
#   CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
])

INTERNAL_IPS = ["127.0.0.1"]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # Rate limiting to prevent abuse
    # Rates tuned for good UX while preventing abuse (comparable to Shopee/Tiki)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/hour',         # Unauthenticated users: 200 requests/hour
        'user': '2000/hour',        # Authenticated users: 2000 requests/hour
        'login': '5/minute',        # Login attempts: 5 per minute (prevent brute force)
        'registration': '10/hour',  # Registration: 10 per hour per IP
        'sensitive': '60/hour',     # Sensitive operations (coupon, checkout): 60/hour
        'password_reset': '5/hour', # Password reset requests: 5 per hour
    },
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Marketplace API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env.int('ACCESS_TOKEN_LIFETIME', default=60)),
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=env.int('REFRESH_TOKEN_LIFETIME', default=1440)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'SIGNING_KEY': env('JWT_SIGNING_KEY', default=SECRET_KEY),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='django-db')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Celery Beat Schedule (Periodic Tasks)
CELERY_BEAT_SCHEDULE = {
    'cancel-expired-orders': {
        'task': 'apps.orders.tasks.cancel_expired_pending_orders',
        'schedule': 300.0,  # Run every 5 minutes (300 seconds)
    },
    'update-daily-statistics': {
        'task': 'apps.orders.tasks.update_order_statistics',
        'schedule': 86400.0,  # Run once per day (24 hours)
    },
    'release-held-vendor-balances': {
        'task': 'apps.vendors.tasks.release_held_vendor_balances',
        'schedule': 3600.0,  # Run every hour to release held balances
    },
    'sync-product-view-counts': {
        'task': 'apps.products.tasks.sync_view_counts_to_db',
        'schedule': 600.0,  # Run every 10 minutes to sync Redis view counts to DB
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/1'),
    }
}

EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@owlmarket.com')

# Backend URL (for payment callbacks, webhooks, etc.)
BACKEND_URL = env('BACKEND_URL', default='http://localhost:8000')

# Payment Settings (Safe Load)
STRIPE_PUBLIC_KEY = env('STRIPE_PUBLIC_KEY', default='')
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')

VNPAY_TMN_CODE = env('VNPAY_TMN_CODE', default='')
VNPAY_HASH_SECRET = env('VNPAY_HASH_SECRET', default='')
VNPAY_URL = env('VNPAY_URL', default='https://sandbox.vnpayment.vn/paymentv2/vpcpay.html')
# VNPay callback URLs - constructed from BACKEND_URL if not explicitly set
VNPAY_RETURN_URL = env('VNPAY_RETURN_URL', default=f'{BACKEND_URL}/api/v1/payments/payments/vnpay_return/')
VNPAY_IPN_URL = env('VNPAY_IPN_URL', default=f'{BACKEND_URL}/api/v1/payments/payments/vnpay_ipn/')
VNPAY_REFUND_URL = env('VNPAY_REFUND_URL', default='https://sandbox.vnpayment.vn/merchant_webapi/api/transaction')

# Shipping Settings
DEFAULT_SHIPPING_COST = env.int('DEFAULT_SHIPPING_COST', default=30000)  # VND
FREE_SHIPPING_THRESHOLD = env.int('FREE_SHIPPING_THRESHOLD', default=500000)  # Free shipping for orders >= 500k VND

# Order Settings - Denial of Inventory Protection
MAX_PENDING_ORDERS_PER_USER = env.int('MAX_PENDING_ORDERS_PER_USER', default=3)
MAX_PENDING_ORDERS_PER_GUEST = env.int('MAX_PENDING_ORDERS_PER_GUEST', default=2)  # Per email in 24h
MAX_ORDERS_PER_IP_PER_HOUR = env.int('MAX_ORDERS_PER_IP_PER_HOUR', default=5)  # IP-based limit
GUEST_ORDER_RATE_LIMIT = env('GUEST_ORDER_RATE_LIMIT', default='5/hour')  # Throttle rate
PENDING_ORDER_TIMEOUT_MINUTES = env.int('PENDING_ORDER_TIMEOUT_MINUTES', default=15)

# Vendor Payout Settings - Hold period before release
VENDOR_PAYOUT_HOLD_DAYS = env.int('VENDOR_PAYOUT_HOLD_DAYS', default=7)

# ===========================================
# Production Security Settings
# ===========================================
# These settings are enabled when DEBUG=False
if not DEBUG:
    # HTTPS Security
    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Cookie Security
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # HTTP Strict Transport Security (HSTS)
    SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Content Security
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    # Referrer Policy
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Django Channels (WebSocket) Configuration
ASGI_APPLICATION = 'backend.asgi.application'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [env('REDIS_URL', default='redis://localhost:6379/0')],
        },
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'