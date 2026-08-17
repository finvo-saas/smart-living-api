import os

from .base import *  # noqa: F401, F403
from .base import _env_bool  # noqa: E402

DEBUG = False

# Production storage via S3-compatible backend
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Production defaults — override via env when you want workers/Redis/throttles
USE_REDIS_CACHE = _env_bool('USE_REDIS_CACHE', True)
CELERY_TASK_ALWAYS_EAGER = _env_bool('CELERY_TASK_ALWAYS_EAGER', False)
CELERY_BEAT_ENABLED = _env_bool('CELERY_BEAT_ENABLED', True)
API_THROTTLING_ENABLED = _env_bool('API_THROTTLING_ENABLED', True)
OTP_RATE_LIMIT_ENABLED = _env_bool('OTP_RATE_LIMIT_ENABLED', True)

if USE_REDIS_CACHE:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,  # noqa: F405
        },
    }

if not CELERY_TASK_ALWAYS_EAGER:
    CELERY_BROKER_URL = os.environ.get(
        'CELERY_BROKER_URL',
        'redis://localhost:6379/1',
    )
    CELERY_RESULT_BACKEND = os.environ.get(
        'CELERY_RESULT_BACKEND',
        'redis://localhost:6379/2',
    )

if CELERY_BEAT_ENABLED and not CELERY_BEAT_SCHEDULE:  # noqa: F405
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

if API_THROTTLING_ENABLED:
    REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = (  # noqa: F405
        'core.throttling.ConfigurableAnonRateThrottle',
        'core.throttling.ConfigurableUserRateThrottle',
    )

if os.environ.get('DJANGO_SECRET_KEY', '').startswith('dev-'):
    raise ValueError('Set a strong DJANGO_SECRET_KEY in production')
