import os

from celery import Celery

# Redis broker/backend configuration with defaults
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "docusync_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Rate limit LLM calls to prevent API quota exhaustion
    task_annotations={"app.worker.process_document_task": {"rate_limit": "30/m"}},
    # Retry defaults & Dead Letter Handling
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
