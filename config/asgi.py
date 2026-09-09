import os

from django.core.asgi import get_asgi_application

# Default to production so a missing env var never boots DEBUG unsafe.
# Local: manage.py / .env set DJANGO_SETTINGS_MODULE=config.settings.dev
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')

application = get_asgi_application()
