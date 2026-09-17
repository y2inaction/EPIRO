"""Request rate limiting.

Guards the two endpoints reachable without credentials: login, which is
otherwise brute-forceable, and public question submission, which is otherwise
a spam channel.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings

# Defaults to in-process counters. Deployments running more than one worker
# should point RATE_LIMIT_STORAGE_URI at Redis, or each worker will enforce
# its own separate allowance.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.rate_limit_storage_uri,
    enabled=settings.rate_limit_enabled,
)

LOGIN_LIMIT = f"{settings.rate_limit_login_per_minute}/minute"
PUBLIC_WRITE_LIMIT = f"{settings.rate_limit_public_write_per_minute}/minute"


async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return 429 with a Retry-After hint."""
    detail = getattr(exc, "detail", "Rate limit exceeded")
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": f"Rate limit exceeded: {detail}"},
    )
    # _inject_headers adds X-RateLimit-* and Retry-After. It is slowapi's
    # documented hook for custom handlers despite the underscore, and it ships
    # no type information.
    with_headers: JSONResponse = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return with_headers


__all__ = [
    "LOGIN_LIMIT",
    "PUBLIC_WRITE_LIMIT",
    "RateLimitExceeded",
    "limiter",
    "rate_limit_exceeded_handler",
]
