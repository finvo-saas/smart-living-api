"""
Base Django settings for Smart Living API.
See docs/BACKEND_DESIGN.md in the frontend repo for architecture.
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
APPS_DIR = BASE_DIR / 'apps'
sys.path.insert(0, str(APPS_DIR))

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-insecure-change-me')
DEBUG = os.environ.get('DJANGO_DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if host.strip()
]

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
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'storages',
]

LOCAL_APPS = [
    'core',
    'accounts.apps.AccountsConfig',
    'listings.apps.ListingsConfig',
    'portfolio.apps.PortfolioConfig',
    'bookings.apps.BookingsConfig',
    'billing.apps.BillingConfig',
    'payments.apps.PaymentsConfig',
    'mess.apps.MessConfig',
    'hotels.apps.HotelsConfig',
    'messaging.apps.MessagingConfig',
    'support.apps.SupportConfig',
    'documents.apps.DocumentsConfig',
    'discovery.apps.DiscoveryConfig',
    'subscriptions.apps.SubscriptionsConfig',
    'reports.apps.ReportsConfig',
    'audit.apps.AuditConfig',
    'admin_api.apps.AdminApiConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

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

# Database: prefer DB_* env vars, then DATABASE_URL, else SQLite
_db_name = os.environ.get('DB_NAME', '').strip()
_db_user = os.environ.get('DB_USER', '').strip()
_db_password = os.environ.get('DB_PASSWORD', '')
_db_host = os.environ.get('DB_HOST', 'localhost').strip()
_db_port = os.environ.get('DB_PORT', '5432').strip()

if _db_name and _db_user:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _db_name,
            'USER': _db_user,
            'PASSWORD': _db_password,
            'HOST': _db_host or 'localhost',
            'PORT': _db_port or '5432',
            'CONN_MAX_AGE': 600,
            'OPTIONS': {
                'connect_timeout': 10,
            },
        },
    }
elif os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ['DATABASE_URL'],
            conn_max_age=600,
        ),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        },
    }

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS — Next.js frontend
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000',
    ).split(',')
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


# Redis / cache — USE_REDIS_CACHE=false avoids hanging when Redis is down (dev default via settings.dev)
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
USE_REDIS_CACHE = _env_bool('USE_REDIS_CACHE', False)
if USE_REDIS_CACHE:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        },
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'smart-living-local',
        },
    }

# Celery — CELERY_TASK_ALWAYS_EAGER=true runs tasks in-process (no broker required)
CELERY_TASK_ALWAYS_EAGER = _env_bool('CELERY_TASK_ALWAYS_EAGER', DEBUG)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = os.environ.get(
    'CELERY_BROKER_URL',
    'memory://' if CELERY_TASK_ALWAYS_EAGER else 'redis://localhost:6379/1',
)
CELERY_RESULT_BACKEND = os.environ.get(
    'CELERY_RESULT_BACKEND',
    'cache+memory://' if CELERY_TASK_ALWAYS_EAGER else 'redis://localhost:6379/2',
)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_ENABLED = _env_bool('CELERY_BEAT_ENABLED', False)
if CELERY_BEAT_ENABLED:
    CELERY_BEAT_SCHEDULE = {
        'mark-overdue-bills-hourly': {
            'task': 'billing.mark_overdue_bills',
            'schedule': 3600.0,
        },
        'dispatch-due-reminders-every-5-min': {
            'task': 'reports.dispatch_due_reminders',
            'schedule': 300.0,
        },
    }
else:
    CELERY_BEAT_SCHEDULE = {}

# API hardening toggles (off in DEBUG by default so local work never hangs)
API_THROTTLING_ENABLED = _env_bool('API_THROTTLING_ENABLED', not DEBUG)
OTP_RATE_LIMIT_ENABLED = _env_bool('OTP_RATE_LIMIT_ENABLED', True)
OTP_RATE_LIMIT = int(os.environ.get('OTP_RATE_LIMIT', '5'))
OTP_RATE_WINDOW_SECONDS = int(os.environ.get('OTP_RATE_WINDOW_SECONDS', '3600'))

# S3 / MinIO storage (phase 0 placeholder — local filesystem fallback in dev)
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'smart-living-media')
AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL', '')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
AWS_S3_USE_SSL = os.environ.get('AWS_S3_USE_SSL', 'true').lower() == 'true'
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False

# DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'core.renderers.EnvelopeRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    # Pagination opt-in per GenericAPIView via pagination_class = EnvelopePagination
    'DEFAULT_PAGINATION_CLASS': None,
    'EXCEPTION_HANDLER': 'core.exceptions.envelope_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.environ.get('THROTTLE_ANON', '60/hour'),
        'user': os.environ.get('THROTTLE_USER', '1000/hour'),
        'otp': os.environ.get('THROTTLE_OTP', '5/hour'),
    },
}
API_PAGE_SIZE = int(os.environ.get('API_PAGE_SIZE', '20'))
if API_THROTTLING_ENABLED:
    REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = (
        'core.throttling.ConfigurableAnonRateThrottle',
        'core.throttling.ConfigurableUserRateThrottle',
    )

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=int(os.environ.get('JWT_ACCESS_MINUTES', '15')),
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=int(os.environ.get('JWT_REFRESH_DAYS', '7')),
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# OTP — fixed code only when DEBUG (SMS console stub)
OTP_DEV_FIXED_CODE = os.environ.get('OTP_DEV_FIXED_CODE', '123456')

SPECTACULAR_SETTINGS = {
    'TITLE': 'Smart Living API',
    'DESCRIPTION': 'REST API for Smart Living System (Bangladesh rental platform)',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/v1/',
}

# Platform
COMMISSION_RATE = float(os.environ.get('COMMISSION_RATE', '0.05'))
DEFAULT_CURRENCY = os.environ.get('DEFAULT_CURRENCY', 'BDT')

# Payments
PAYMENT_SANDBOX_AUTO_COMPLETE = os.environ.get(
    'PAYMENT_SANDBOX_AUTO_COMPLETE',
    'true' if DEBUG else 'false',
).lower() == 'true'
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
BKASH_APP_KEY = os.environ.get('BKASH_APP_KEY', '')
BKASH_APP_SECRET = os.environ.get('BKASH_APP_SECRET', '')
BKASH_USERNAME = os.environ.get('BKASH_USERNAME', '')
BKASH_PASSWORD = os.environ.get('BKASH_PASSWORD', '')
BKASH_BASE_URL = os.environ.get(
    'BKASH_BASE_URL',
    'https://tokenized.sandbox.bka.sh/v1.2.0-beta',
)
BKASH_WEBHOOK_SECRET = os.environ.get('BKASH_WEBHOOK_SECRET', '')
NAGAD_MERCHANT_ID = os.environ.get('NAGAD_MERCHANT_ID', '')
NAGAD_MERCHANT_PRIVATE_KEY = os.environ.get('NAGAD_MERCHANT_PRIVATE_KEY', '')
NAGAD_BASE_URL = os.environ.get('NAGAD_BASE_URL', 'https://api.mynagad.com')
ROCKET_MERCHANT_ID = os.environ.get('ROCKET_MERCHANT_ID', '')
ROCKET_API_PASSWORD = os.environ.get('ROCKET_API_PASSWORD', '')
ROCKET_BASE_URL = os.environ.get('ROCKET_BASE_URL', 'https://sandbox.rocket.com.bd')

# SMS (dev stub logs to console)
SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'console')
SMS_API_KEY = os.environ.get('SMS_API_KEY', '')
SMS_SENDER_ID = os.environ.get('SMS_SENDER_ID', 'SmartLiving')

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
        'level': 'INFO',
    },
}
