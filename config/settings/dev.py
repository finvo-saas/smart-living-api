from .base import *  # noqa: F401, F403
from .base import _env_bool

DEBUG = True

INSTALLED_APPS += ['debug_toolbar']  # noqa: F405

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    *MIDDLEWARE,  # noqa: F405
]

INTERNAL_IPS = ['127.0.0.1', 'localhost']

# Dev: use local media storage (cache/Celery toggles come from base + .env)
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Safe defaults when .env omits them — never block on Redis/broker in local runserver
CELERY_TASK_ALWAYS_EAGER = _env_bool('CELERY_TASK_ALWAYS_EAGER', True)
API_THROTTLING_ENABLED = _env_bool('API_THROTTLING_ENABLED', False)
