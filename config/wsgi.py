import os

from django.core.wsgi import get_wsgi_application

# Default to production so a missing env var never boots DEBUG/gunicorn unsafe.
# Local: manage.py / .env set DJANGO_SETTINGS_MODULE=config.settings.dev
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')

application = get_wsgi_application()
