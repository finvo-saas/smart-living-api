import os

from .base import *  # noqa: F401, F403
from .base import _env_bool  # noqa: E402

DEBUG = False

# WhiteNoise — serve Django admin / staticfiles behind gunicorn (nginx still fronts the app)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    *[m for m in MIDDLEWARE if m != 'django.middleware.security.SecurityMiddleware'],  # noqa: F405
]
STORAGES = {
    **STORAGES,  # noqa: F405
    'staticfiles': {
        # Compressed (non-manifest) avoids collectstatic failures on missing hashed refs
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

# Never auto-complete gateway payments in production unless explicitly allowed
# for a staging box (ALLOW_PAYMENT_SANDBOX_IN_PROD=true).
if _env_bool('ALLOW_PAYMENT_SANDBOX_IN_PROD', False):
    PAYMENT_SANDBOX_AUTO_COMPLETE = _env_bool('PAYMENT_SANDBOX_AUTO_COMPLETE', False)
else:
    PAYMENT_SANDBOX_AUTO_COMPLETE = False

# Object storage is configured in base.py via STORAGES (DigitalOcean Spaces).

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Behind nginx/Contabo TLS terminator you can set SECURE_SSL_REDIRECT=false
# and let the proxy redirect HTTP→HTTPS.
SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', True)
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', True)
SECURE_HSTS_PRELOAD = _env_bool('SECURE_HSTS_PRELOAD', False)
SECURE_REFERRER_POLICY = os.environ.get(
    'SECURE_REFERRER_POLICY',
    'same-origin',
)

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
        'send-heartbeats-hourly-window': {
            'task': 'discovery.send_weekly_heartbeats',
            'schedule': 3600.0,
        },
    }

if API_THROTTLING_ENABLED:
    REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = (  # noqa: F405
        'core.throttling.ConfigurableAnonRateThrottle',
        'core.throttling.ConfigurableUserRateThrottle',
    )
    # Cloudflare, then nginx. Used when CF-Connecting-IP is not forwarded.
    REST_FRAMEWORK['NUM_PROXIES'] = int(os.environ.get('NUM_PROXIES', '2'))

_secret = os.environ.get('DJANGO_SECRET_KEY', '')
if not _secret or _secret.startswith('dev-') or _secret == 'change-me-in-production':
    raise ValueError('Set a strong DJANGO_SECRET_KEY in production')
if len(_secret) < 50 or len(set(_secret)) < 5:
    raise ValueError(
        'DJANGO_SECRET_KEY must be at least 50 characters with 5+ unique characters'
    )
