"""
Django settings for backend project.
Optimized for Mini LMS Project (Django 6.0 + Remix).
"""

from pathlib import Path
import os
from datetime import timedelta
import environ

# 1. Định nghĩa BASE_DIR (Đặt lên đầu tiên)
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# 2. Setup Environment Variables
# ------------------------------------------------------------------------------
env = environ.Env()
# Đọc file .env tại thư mục gốc
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))


# 3. General Settings
# ------------------------------------------------------------------------------
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Custom User Model
AUTH_USER_MODEL = 'users.User'


# 4. Apps Definition
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles', # Cần thiết cho whitenoise và admin UI
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',
    'cloudinary_storage',
    'cloudinary',
]

LOCAL_APPS = [
    'apps.users',
    'apps.courses',
    'apps.enrollments',
    'apps.payments',
    'apps.reviews',
    'apps.notifications',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # [OPTIONAL] Thêm dòng này để serve static file khi deploy
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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


# 5. Database
# ------------------------------------------------------------------------------
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR}/db.sqlite3')
}


# 6. Password Validation
# ------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# 7. Internationalization
# ------------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# 8. Files Storage (Static & Media) - Updated for Django 6.0
# ------------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Cloudinary Configuration
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': env('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY': env('CLOUDINARY_API_KEY', default=''),
    'API_SECRET': env('CLOUDINARY_API_SECRET', default=''),
}

# Cấu hình STORAGES mới (Thay thế DEFAULT_FILE_STORAGE cũ)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Nếu có Cloudinary, chuyển Backend lưu trữ media sang Cloud
if CLOUDINARY_STORAGE['CLOUD_NAME']:
    STORAGES["default"]["BACKEND"] = 'cloudinary_storage.storage.MediaCloudinaryStorage'
else:
    # Nếu chạy local không có Cloudinary
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'


# 9. Django REST Framework & JWT
# ------------------------------------------------------------------------------
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
    
    # Throttling - Giới hạn request để chống spam
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',           # User chưa đăng nhập: 100 requests/ngày
        'user': '1000/day',          # User đã đăng nhập: 1000 requests/ngày
        'review_create': '10/day',   # Tạo review: 10 lần/ngày
        'payment': '20/hour',        # Payment: 20 lần/giờ
    }
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}


# 10. CORS Configuration
# ------------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=["http://localhost:3000"])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]


# 11. API Documentation
# ------------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    'TITLE': 'Mini LMS API',
    'DESCRIPTION': 'API documentation for the Online Learning Platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# 12. VNPay Payment Gateway Configuration
# ------------------------------------------------------------------------------
VNPAY_TMN_CODE = env('VNPAY_TMN_CODE', default='')
VNPAY_HASH_SECRET = env('VNPAY_HASH_SECRET', default='')
VNPAY_PAYMENT_URL = env('VNPAY_PAYMENT_URL', default='https://sandbox.vnpayment.vn/paymentv2/vpcpay.html')
VNPAY_RETURN_URL = env('VNPAY_RETURN_URL', default='http://localhost:8000/api/payments/vnpay/callback')
VNPAY_API_URL = env('VNPAY_API_URL', default='https://sandbox.vnpayment.vn/merchant_webapi/api/transaction')


# 13. Security (Production)
# ------------------------------------------------------------------------------
if not DEBUG:
    # Bật các tính năng bảo mật khi deploy
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # SECURE_SSL_REDIRECT = True # Bật cái này nếu server có HTTPS
    # SESSION_COOKIE_SECURE = True
    # CSRF_COOKIE_SECURE = True