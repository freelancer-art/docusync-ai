import os
import ssl
from celery import Celery
from app.config import settings

# Retrieve Redis URL from settings or environment
raw_redis_url = getattr(settings, "REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# Automatically enforce TLS (rediss://) if connecting to Upstash
if "upstash.io" in raw_redis_url and raw_redis_url.startswith("redis://"):
    redis_url = raw_redis_url.replace("redis://", "rediss://", 1)
else:
    redis_url = raw_redis_url

celery_app = Celery(
    "docusync_worker",
    broker=redis_url,
    backend=redis_url,
)

# Core configuration options
celery_config = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    # Rate limit LLM calls to prevent API quota exhaustion
    "task_annotations": {"app.worker.process_document_task": {"rate_limit": "30/m"}},
    # Retry defaults & Dead Letter Handling
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
}

# Attach SSL certificate settings required for Upstash TLS connections
if redis_url.startswith("rediss://"):
    celery_config.update(
        {
            "broker_use_ssl": {"ssl_cert_reqs": ssl.CERT_NONE},
            "redis_backend_use_ssl": {"ssl_cert_reqs": ssl.CERT_NONE},
        }
    )

celery_app.conf.update(celery_config)