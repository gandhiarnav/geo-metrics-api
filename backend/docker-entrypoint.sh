#!/bin/sh
set -e

echo "Applying database migrations..."
alembic upgrade head

APP_PORT="${PORT:-8000}"
WORKERS="${GEO_WORKERS:-2}"

echo "Starting Uvicorn server on port ${APP_PORT} with ${WORKERS} workers..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT}" --workers "${WORKERS}"
