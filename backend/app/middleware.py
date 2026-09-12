"""HTTP middleware for CryptoTrace.

Three request-lifetime middlewares plus a CORS configuration helper:

- ``RateLimitMiddleware``  - in-memory fixed-window per (client_ip, scope)
- ``SecurityHeadersMiddleware`` - security-relevant response headers
- ``RequestIdMiddleware`` - X-Request-Id injection + safe request logging

State is intentionally in-memory and single-instance. That is honest and
sufficient for the SIH demo; a distributed store (Redis) would be the
production upgrade and is called out in the code comment.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Callable, Dict, List, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject an X-Request-Id header and log only safe diagnostics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        if response.status_code >= 400:
            # Never log bodies, headers, secrets, query strings, or identities.
            method = request.method
            path = request.url.path
            status = response.status_code
            print(
                f"[cryptotrace] request {request_id} {method} {path} -> {status}",
                flush=True,
            )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Set security-relevant response headers on every response.

    ``/docs`` and ``/openapi.json`` get a relaxed Content-Security-Policy that
    allows the Swagger UI CDN (cdn.jsdelivr.net) so the interactive docs render;
    every API response keeps the strict policy.
    """

    _HEADERS: Dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
    }

    _DOCS_CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'; frame-ancestors 'none'"
    )

    @staticmethod
    def _is_docs_path(path: str) -> bool:
        return (
            path in ("/docs", "/redoc", "/openapi.json")
            or path.startswith("/oauth2-redirect")
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        csp = self._DOCS_CSP if self._is_docs_path(request.url.path) else self._HEADERS["Content-Security-Policy"]
        response = await call_next(request)
        for name, value in self._HEADERS.items():
            # Let an explicit upstream value win (e.g. static assets later).
            if name not in response.headers:
                if name == "Content-Security-Policy":
                    value = csp
                response.headers[name] = value
        return response


class RateLimitExceeded(Exception):
    """Raised internally when a request exceeds its rate-limit window."""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window in-memory rate limiting keyed by client IP and scope.

    ``limits`` maps a URL scope to ``(max_requests, window_seconds)``. A
    ``scope`` of ``"*"`` is the default for anything not explicitly listed.
    Health/root endpoints are exempt so the frontend boot probe always works.
    """

    def __init__(
        self,
        app,
        limits: Dict[str, Tuple[int, int]],
        default: Tuple[int, int] = (120, 60),
        exempt_prefixes: Tuple[str, ...] = ("/api/v1/health", "/"),
    ) -> None:
        super().__init__(app)
        self._limits = limits
        self._default = default
        self._exempt_prefixes = exempt_prefixes
        self._hits: Dict[Tuple[str, str], List[float]] = defaultdict(list)

    def _scope_for(self, path: str) -> str:
        for prefix in self._limits:
            if path.startswith(prefix):
                return prefix
        return "*"

    def _client_ip(self, request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def _is_exempt(self, path: str) -> bool:
        # Careful: a bare "/" prefix must only exempt the root path itself,
        # never every route (every path starts with "/").
        for prefix in self._exempt_prefixes:
            if prefix == "/":
                if path == "/":
                    return True
            elif path.startswith(prefix):
                return True
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if self._is_exempt(path):
            return await call_next(request)

        scope = self._scope_for(path)
        max_requests, window = self._limits.get(scope, self._default)
        key = (self._client_ip(request), scope)
        now = time.monotonic()

        window_hits = [t for t in self._hits[key] if now - t < window]
        if len(window_hits) >= max_requests:
            retry_after = max(1, int(window - (now - window_hits[0])))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please wait and retry.",
                },
                headers={"Retry-After": str(retry_after)},
            )

        window_hits.append(now)
        self._hits[key] = window_hits
        return await call_next(request)


def cors_configuration(
    origins: List[str],
    allow_credentials: bool = False,
) -> Dict:
    """Return keyword args for FastAPI's CORSMiddleware.

    Credentials are deliberately disabled: auth uses an Authorization Bearer
    header, never cookies, so there is no CSRF surface from cross-origin
    requests.
    """
    return {
        "allow_origins": [o for o in origins if o],
        "allow_credentials": allow_credentials,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Authorization", "Content-Type", "X-Request-Id", "Accept"],
        "expose_headers": ["X-Request-Id"],
        "max_age": 600,
    }