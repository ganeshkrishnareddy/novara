"""HTTP security hardening.

- Conservative response headers on every response, including errors.
- CORS allow-list read from configuration; same-origin only by default.
- A sliding-window rate limiter for unauthenticated auth endpoints.
- A second in-process limiter for document/share endpoints with a canonical
  JSON error envelope (PM-146).

All limits are configurable so a deployment can tighten them without a code
change. Nothing here depends on an external service.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
}

# Generous defaults so local development and the regression suite work.
# Deployments should lower these through NOVARA_AUTH_RATE_LIMIT and
# NOVARA_DOCUMENT_RATE_LIMIT / NOVARA_DOCUMENT_RATE_WINDOW.
DEFAULT_AUTH_LIMIT = 300
DEFAULT_DOCUMENT_LIMIT = 600
DEFAULT_WINDOW_SECONDS = 60

DOCUMENT_PATH_MARKERS = ("/documents", "/storage")
DOCUMENT_RATE_LIMIT_CODE = "RATE_LIMIT_EXCEEDED"
DOCUMENT_RATE_LIMIT_MESSAGE = "document request rate limit exceeded; try again later"

RATE_LIMITED_PATHS = (
    "/api/v1/setup/bootstrap",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/password-reset/request",
)


class SlidingWindowLimiter:
    """Thread-safe in-process limiter. Suitable for one Worker process."""

    def __init__(self, limit: int = DEFAULT_AUTH_LIMIT, window_seconds: int = DEFAULT_WINDOW_SECONDS):
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self.configure(limit, window_seconds)

    def configure(self, limit: int, window_seconds: int = DEFAULT_WINDOW_SECONDS) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window_seconds must be positive")
        with self._lock:
            self.limit = limit
            self.window_seconds = window_seconds

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def remaining(self, key: str) -> int:
        """Requests still permitted for this client in the current window."""
        with self._lock:
            return max(0, self.limit - len(self._events[key]))

    def check(self, key: str) -> bool:
        """Return True when the request is allowed, False when over the limit."""
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            cutoff = now - self.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


def _positive_env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"invalid {name}: {exc}") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be positive")
    return value


auth_limiter = SlidingWindowLimiter()
document_limiter = SlidingWindowLimiter(
    _positive_env_int("NOVARA_DOCUMENT_RATE_LIMIT", DEFAULT_DOCUMENT_LIMIT),
    _positive_env_int("NOVARA_DOCUMENT_RATE_WINDOW", DEFAULT_WINDOW_SECONDS),
)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:100]
    if request.client and request.client.host:
        return request.client.host[:100]
    return "unknown"


def _is_document_path(path: str) -> bool:
    return any(marker in path for marker in DOCUMENT_PATH_MARKERS)


def _document_key(request: Request) -> str:
    """Scope a document budget to the client and, when present, the workspace."""
    client_key = _client_key(request)
    parts = request.url.path.split("/")
    if len(parts) > 4 and parts[1:4] == ["api", "v1", "workspaces"] and parts[4]:
        return f"{client_key}|{parts[4][:100]}"
    return client_key


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_limited = request.url.path in RATE_LIMITED_PATHS
        document_limited = _is_document_path(request.url.path)
        document_key = ""
        if auth_limited:
            client_key = _client_key(request)
            if not auth_limiter.check(client_key):
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "too many authentication attempts; try again later"},
                )
            else:
                response = await call_next(request)
        elif document_limited:
            document_key = _document_key(request)
            if document_limiter.check(document_key):
                response = await call_next(request)
            else:
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": DOCUMENT_RATE_LIMIT_CODE,
                            "message": DOCUMENT_RATE_LIMIT_MESSAGE,
                            "retry_after": document_limiter.window_seconds,
                        }
                    },
                )
        else:
            response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        if auth_limited:
            # Clients can see their budget without probing the limit, and a
            # throttled client gets a concrete retry window (PL-049).
            response.headers["X-RateLimit-Limit"] = str(auth_limiter.limit)
            response.headers["X-RateLimit-Remaining"] = str(
                auth_limiter.remaining(client_key)
            )
            response.headers["X-RateLimit-Window"] = str(auth_limiter.window_seconds)
            if response.status_code == 429:
                response.headers["Retry-After"] = str(auth_limiter.window_seconds)
        elif document_limited:
            response.headers["X-RateLimit-Limit"] = str(document_limiter.limit)
            response.headers["X-RateLimit-Remaining"] = str(
                document_limiter.remaining(document_key)
            )
            response.headers["X-RateLimit-Window"] = str(document_limiter.window_seconds)
            if response.status_code == 429:
                response.headers["Retry-After"] = str(document_limiter.window_seconds)
        return response


def cors_origins_from_env() -> list[str]:
    raw = os.getenv("NOVARA_CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def install_security(app: FastAPI) -> None:
    """Attach hardening middleware using current configuration."""
    configured_limit = os.getenv("NOVARA_AUTH_RATE_LIMIT")
    if configured_limit:
        try:
            auth_limiter.configure(int(configured_limit))
        except ValueError as exc:
            raise RuntimeError(f"invalid NOVARA_AUTH_RATE_LIMIT: {exc}") from exc

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins_from_env(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
