import time

import redis
from fastapi import HTTPException, Request, status

from app.config import settings

# Global Redis client initialization with standard timeout
try:
    redis_client = redis.Redis.from_url(
        getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
        socket_timeout=2,
    )
except (redis.RedisError, ConnectionError):
    redis_client = None

# Fallback in-memory storage for test/offline environments
_in_memory_buckets = {}


def rate_limiter(requests_limit: int = 100, window_seconds: int = 60):
    """
    Sliding window rate-limiting dependency for FastAPI routes.
    Identifies clients via client IP address.
    """

    async def _rate_limit_check(request: Request):
        client_ip = request.client.host if request.client else "127.0.0.1"
        key = f"rate_limit:{request.url.path}:{client_ip}"
        now = time.time()
        window_start = now - window_seconds

        if redis_client:
            try:
                pipe = redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, window_seconds)
                results = pipe.execute()
                request_count = results[2]
            except redis.RedisError:
                request_count = _fallback_in_memory(key, now, window_start)
        else:
            request_count = _fallback_in_memory(key, now, window_start)

        if request_count > requests_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please retry later.",
                headers={"Retry-After": str(window_seconds)},
            )

    return _rate_limit_check


def _fallback_in_memory(key: str, now: float, window_start: float) -> int:
    """Helper for fallback rate-limiting when Redis is unreachable."""
    timestamps = _in_memory_buckets.get(key, [])
    timestamps = [t for t in timestamps if t > window_start]
    timestamps.append(now)
    _in_memory_buckets[key] = timestamps
    return len(timestamps)