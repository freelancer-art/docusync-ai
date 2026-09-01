#!/usr/bin/env bash

# Set default PORT to 10000 if not set by environment
PORT="${PORT:-10000}"

# Start Celery worker in the background
celery -A app.core.celery_app.celery_app worker --loglevel=info -c 2 &

# Start FastAPI Uvicorn server in the foreground bound to $PORT
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"