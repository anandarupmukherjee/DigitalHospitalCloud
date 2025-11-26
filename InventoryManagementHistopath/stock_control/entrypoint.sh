#!/bin/bash

# Fail fast and surface pipeline errors
set -euo pipefail

DATA_OUTPUT_PID=""
SERVER_PID=""
PORT=${PORT:-8001}
ENABLE_DATA_OUTPUT_LISTENER=${ENABLE_DATA_OUTPUT_LISTENER:-0}

cleanup() {
  echo "Shutting down services..."
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    echo "Stopping Django server (PID ${SERVER_PID})"
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
  fi

  if [[ -n "${DATA_OUTPUT_PID}" ]] && kill -0 "${DATA_OUTPUT_PID}" >/dev/null 2>&1; then
    echo "Stopping data_output listener (PID ${DATA_OUTPUT_PID})"
    kill "${DATA_OUTPUT_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

echo "1. Ensuring permissions and directories..."
mkdir -p /code/staticfiles
chmod -R 755 /code/staticfiles
ls -la /code/staticfiles

echo "2. Running migrations..."
python manage.py migrate

echo "3. Ensuring Django superuser exists..."
python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "shoestring")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")

if not password:
    raise SystemExit("DJANGO_SUPERUSER_PASSWORD must be provided.")

User = get_user_model()
if User.objects.filter(username=username).exists():
    print(f"Superuser '{username}' already exists.")
else:
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser '{username}' created.")
PY

echo "4. Running collectstatic with simple storage..."
python manage.py collectstatic --noinput --verbosity 2

echo "5. Checking staticfiles directory after collectstatic..."
ls -la /code/staticfiles

if [[ "${ENABLE_DATA_OUTPUT_LISTENER}" == "1" ]]; then
  echo "7. Starting data_output listener..."
  python manage.py data_output_listener &
  DATA_OUTPUT_PID=$!
  echo "data_output listener running as PID ${DATA_OUTPUT_PID}"
else
  echo "7. Skipping data_output listener (ENABLE_DATA_OUTPUT_LISTENER=${ENABLE_DATA_OUTPUT_LISTENER})"
fi

echo "8. Starting Django development server..."
python manage.py runserver 0.0.0.0:${PORT} &
SERVER_PID=$!

wait "${SERVER_PID}"
