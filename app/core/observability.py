"""Lightweight metrics, tracing, and optional alert delivery for operations."""

import json
import logging
import time
from collections import Counter
from threading import Lock
from urllib.request import Request, urlopen

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from app.config import settings
from app.core.logging import get_correlation_id

logger = logging.getLogger(__name__)


class RequestMetrics:
    """Thread-safe in-process counters suitable for Prometheus scraping."""

    def __init__(self):
        self._lock = Lock()
        self.requests = Counter()
        self.errors = Counter()
        self.duration_seconds = Counter()

    def observe(self, method: str, path: str, status_code: int, duration: float):
        key = (method, path)
        with self._lock:
            self.requests[key] += 1
            if status_code >= 500:
                self.errors[key] += 1
            self.duration_seconds[key] += duration

    def prometheus(self) -> str:
        lines = [
            "# HELP docusync_http_requests_total HTTP requests handled.",
            "# TYPE docusync_http_requests_total counter",
        ]
        with self._lock:
            for (method, path), count in sorted(self.requests.items()):
                labels = f'method="{method}",path="{path}"'
                lines.append(f"docusync_http_requests_total{{{labels}}} {count}")
            lines.extend(
                [
                    "# HELP docusync_http_errors_total HTTP 5xx responses.",
                    "# TYPE docusync_http_errors_total counter",
                ]
            )
            for (method, path), count in sorted(self.errors.items()):
                labels = f'method="{method}",path="{path}"'
                lines.append(f"docusync_http_errors_total{{{labels}}} {count}")
        return "\n".join(lines) + "\n"


metrics = RequestMetrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request counts and durations without exposing document contents."""

    async def dispatch(self, request: StarletteRequest, call_next) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        metrics.observe(
            request.method,
            request.url.path,
            response.status_code,
            time.perf_counter() - started,
        )
        return response


def send_alert(message: str) -> None:
    """Send an optional JSON alert without making application flow depend on it."""
    webhook_url = settings.OBSERVABILITY_ALERT_WEBHOOK_URL
    if not webhook_url:
        return
    try:
        payload = json.dumps({"text": message}).encode("utf-8")
        request = Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=3):
            return
    except Exception:
        logger.exception("Observability alert delivery failed")


def trace_context() -> dict[str, str]:
    """Return the current request trace identifier for structured event logs."""
    return {"trace_id": get_correlation_id()}
