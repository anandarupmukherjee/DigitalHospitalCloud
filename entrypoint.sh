#!/bin/sh

set -e

ROLE="${SERVICE_ROLE:-web}"

python manage.py migrate --noinput

if [ "$ROLE" = "listener" ]; then
  exec python manage.py run_tray_listener
fi

if [ "$ROLE" = "notifier" ]; then
  exec python manage.py notify_active_trays
fi

if [ "${DJANGO_COLLECTSTATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec gunicorn logistics_tracker.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
