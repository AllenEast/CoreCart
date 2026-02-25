#!/usr/bin/env sh
set -e

# Default to production settings inside docker unless explicitly overridden
: "${DJANGO_SETTINGS_MODULE:=karzina.settings.prod}"
export DJANGO_SETTINGS_MODULE

# Apply migrations (safe for idempotent startup)
python manage.py migrate --noinput

# Collect static (rebuild each start so Docker volumes don't keep stale/incomplete files)
python manage.py collectstatic --noinput --clear || true

# Start ASGI server for HTTP+WebSocket
exec daphne -b 0.0.0.0 -p 8000 karzina.asgi:application
