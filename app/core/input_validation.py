from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB limit


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects incoming requests exceeding maximum allowed content length (10MB).
    """

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_PAYLOAD_BYTES:
            return JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={
                    "detail": "Request payload exceeds maximum allowed limit (10MB)."
                },
            )
        return await call_next(request)
