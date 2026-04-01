#!/bin/sh
set -eu

RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"

if [ "$RUN_MIGRATIONS" = "true" ]; then
  /app/.venv/bin/python -m alembic upgrade head
fi

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf

