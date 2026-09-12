"""Rate-limit and security-header middleware tests.

Rate limiting runs on a purpose-built app so each test gets a fresh middleware
state (the production app shares one global middleware instance).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware, cors_configuration


@pytest.fixture
def limited_app():
    app = FastAPI()

    @app.get("/api/v1/auth/login")
    def fake_login():
        return {"ok": True}

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    @app.get("/anything")
    def anything():
        return {"ok": True}

    app.add_middleware(
        RateLimitMiddleware,
        limits={"/api/v1/auth/login": (2, 60)},
        default=(3, 60),
        exempt_prefixes=("/api/v1/health", "/"),
    )
    return app


class TestRateLimit:
    def test_limit_exceeded_returns_429(self, limited_app):
        client = TestClient(limited_app)
        assert client.get("/api/v1/auth/login").status_code == 200
        assert client.get("/api/v1/auth/login").status_code == 200
        res = client.get("/api/v1/auth/login")
        assert res.status_code == 429
        assert "Retry-After" in res.headers

    def test_exempt_health_never_limited(self, limited_app):
        client = TestClient(limited_app)
        for _ in range(10):
            assert client.get("/api/v1/health").status_code == 200

    def test_window_recovery(self, limited_app, monkeypatch):
        client = TestClient(limited_app)
        assert client.get("/api/v1/auth/login").status_code == 200
        assert client.get("/api/v1/auth/login").status_code == 200

        # Fast-forward the middleware clock to age out the window.
        import app.middleware as middleware_mod

        real_monotonic = middleware_mod.time.monotonic
        state = {"now": real_monotonic() + 61}

        def fake_monotonic():
            return state["now"]

        monkeypatch.setattr(middleware_mod.time, "monotonic", fake_monotonic)
        assert client.get("/api/v1/auth/login").status_code == 200


@pytest.fixture
def headers_app():
    app = FastAPI()

    @app.get("/x")
    def x():
        return {"ok": True}

    app.add_middleware(SecurityHeadersMiddleware)
    return app


class TestSecurityHeaders:
    def test_security_headers_present(self, headers_app):
        client = TestClient(headers_app)
        res = client.get("/x")
        assert res.headers["X-Content-Type-Options"] == "nosniff"
        assert res.headers["X-Frame-Options"] == "DENY"
        assert res.headers["Referrer-Policy"] == "no-referrer"
        assert "default-src 'self'" in res.headers["Content-Security-Policy"]
        assert res.headers["Cache-Control"] == "no-store"
        assert res.headers["Pragma"] == "no-cache"

    def test_explicit_upstream_header_wins(self):
        app = FastAPI()

        @app.get("/y")
        def y():
            from starlette.responses import JSONResponse

            return JSONResponse(
                {"ok": True}, headers={"Content-Security-Policy": "default-src 'self' http://override"}
            )

        app.add_middleware(SecurityHeadersMiddleware)
        res = TestClient(app).get("/y")
        assert res.headers["Content-Security-Policy"] == "default-src 'self' http://override"

    def test_docs_paths_get_relaxed_csp(self, headers_app):
        client = TestClient(headers_app)
        for url in ("/docs", "/redoc", "/openapi.json"):
            res = client.get(url)
            csp = res.headers["Content-Security-Policy"]
            assert "https://cdn.jsdelivr.net" in csp
            assert "frame-ancestors 'none'" in csp
            # The strict firewall rules must remain intact on the API itself.
            assert res.headers["X-Frame-Options"] == "DENY"

    def test_oauth2_redirect_gets_relaxed_csp(self, headers_app):
        client = TestClient(headers_app)
        res = client.get("/oauth2-redirect?code=abc&state=xyz")
        assert "https://cdn.jsdelivr.net" in res.headers["Content-Security-Policy"]

    def test_api_paths_keep_strict_csp(self, headers_app):
        client = TestClient(headers_app)
        res = client.get("/x")
        assert res.headers["Content-Security-Policy"] == "default-src 'self'; frame-ancestors 'none'"


class TestCorsConfiguration:
    def test_credentials_disabled_by_default(self):
        cfg = cors_configuration(["http://localhost:5173"])
        assert cfg["allow_credentials"] is False
        assert "Authorization" in cfg["allow_headers"]
        assert cfg["expose_headers"] == ["X-Request-Id"]

    def test_empty_origins_filtered(self):
        cfg = cors_configuration(["", "http://a.example"])
        assert cfg["allow_origins"] == ["http://a.example"]