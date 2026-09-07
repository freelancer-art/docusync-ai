#!/usr/bin/env bash

# Set default PORT to DEFAULT_PLATFORM_PORT if not set by environment
PORT="${PORT:-${DEFAULT_PLATFORM_PORT:-10000}}"

# Keep the Render web process lightweight. Run Celery as a separate background
# worker service, or explicitly opt in for local all-in-one deployments.
if [[ "${START_CELERY_WORKER:-false}" == "true" ]]; then
	CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-1}"
	celery -A app.core.celery_app.celery_app worker \
		--loglevel="${CELERY_LOG_LEVEL:-info}" \
		--concurrency="$CELERY_CONCURRENCY" &
fi

# Start FastAPI Uvicorn server in the foreground bound to $PORT
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
