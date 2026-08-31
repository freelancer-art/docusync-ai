import contextvars
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable to track correlation IDs across async tasks/threads
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_correlation_id() -> str:
    return correlation_id_ctx.get()


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns or propagates an X-Request-ID header for end-to-end tracing.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = correlation_id_ctx.set(req_id)

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id

        correlation_id_ctx.reset(token)
        return response


class StructuredLogFormatter(logging.Formatter):
    """
    JSON log formatter injecting request context and correlation IDs.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return str(log_data)
