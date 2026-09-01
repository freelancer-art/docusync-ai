#!/usr/bin/env bash

# Start Celery worker in the background
celery -A app.core.celery_app.celery_app worker --loglevel=info -c 2 &

# Start FastAPI Uvicorn server in the foreground
uvicorn app.main:app --host 0.0.0.0 --port $PORT