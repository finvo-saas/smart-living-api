#!/bin/sh
set -eu

cd /app

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"

# Named volumes often mount as root — make them writable for appuser
mkdir -p /app/staticfiles /app/media /app/logs
chown -R appuser:appuser /app/staticfiles /app/media /app/logs 2>/dev/null || true

run_as_app() {
  if [ "$(id -u)" = "0" ]; then
    exec gosu appuser "$@"
  else
    exec "$@"
  fi
}

as_app() {
  if [ "$(id -u)" = "0" ]; then
    gosu appuser "$@"
  else
    "$@"
  fi
}

echo "[api] waiting for database..."
as_app python <<'PY'
import os, sys, time
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings.prod"))
django.setup()
from django.db import connection
from django.db.utils import OperationalError

for i in range(60):
    try:
        connection.ensure_connection()
        print("[api] database ready")
        sys.exit(0)
    except OperationalError as exc:
        print(f"[api] db not ready ({i+1}/60): {exc}")
        time.sleep(2)
print("[api] database never became ready", file=sys.stderr)
sys.exit(1)
PY

ROLE="${1:-gunicorn}"

if [ "$ROLE" = "gunicorn" ] || [ "$ROLE" = "migrate" ]; then
  echo "[api] applying migrations..."
  as_app python manage.py migrate --noinput
  echo "[api] collecting static..."
  as_app python manage.py collectstatic --noinput
fi

if [ "$ROLE" = "migrate" ]; then
  exit 0
fi

if [ "$ROLE" = "gunicorn" ]; then
  WORKERS="${GUNICORN_WORKERS:-3}"
  TIMEOUT="${GUNICORN_TIMEOUT:-120}"
  BIND="${GUNICORN_BIND:-0.0.0.0:8000}"
  echo "[api] starting gunicorn workers=$WORKERS bind=$BIND"
  run_as_app gunicorn config.wsgi:application \
    --bind "$BIND" \
    --workers "$WORKERS" \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout "$TIMEOUT" \
    --access-logfile - \
    --error-logfile - \
    --capture-output
fi

if [ "$ROLE" = "worker" ]; then
  echo "[api] starting celery worker"
  run_as_app celery -A config worker -l INFO --concurrency "${CELERY_CONCURRENCY:-2}"
fi

if [ "$ROLE" = "beat" ]; then
  echo "[api] starting celery beat"
  run_as_app celery -A config beat -l INFO \
    --schedule /tmp/celerybeat-schedule \
    --pidfile /tmp/celerybeat.pid
fi

echo "[api] unknown role: $ROLE" >&2
exit 1
