#!/bin/sh
# Container entrypoint: wait for the database, optionally migrate, then run the command.
set -e

if [ -n "${DATABASE_URL:-}" ]; then
    python scripts/wait_for_db.py
fi

# Migrations run only when explicitly requested (RUN_MIGRATIONS=1). In production the
# deploy workflow runs them as a separate, gated step instead.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    flask --app run db upgrade
fi

if [ "$#" -eq 0 ]; then
    set -- gunicorn \
        --bind "0.0.0.0:${PORT:-8000}" \
        --workers "${WEB_CONCURRENCY:-2}" \
        --threads "${GUNICORN_THREADS:-4}" \
        --timeout 60 \
        --preload \
        --access-logfile - \
        --error-logfile - \
        run:app
fi

exec "$@"
