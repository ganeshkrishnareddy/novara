"""Phase 2 P2-8: HTTP security hardening tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from novara_core.middleware import (
    SECURITY_HEADERS,
    auth_limiter,
    cors_origins_from_env,
    install_security,
)

from .conftest import auth, bootstrap


def test_security_headers_on_success_and_error_responses(client):
    ok = client.get("/health")
    assert ok.status_code == 200
    for name, value in SECURITY_HEADERS.items():
        assert ok.headers[name] == value

    denied = client.get("/api/v1/auth/me")
    assert denied.status_code == 401
    assert denied.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in denied.headers["Content-Security-Policy"]


def test_validation_errors_never_reflect_submitted_values(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    response = client.put(
        f"/api/v1/workspaces/{wid}/integrations",
        headers=headers,
        json={"provider": "gmail", "status": "configured", "config": {"api_key": "never-echo-me"}},
    )
    assert response.status_code == 422
    assert "never-echo-me" not in response.text
    assert "secret field is not accepted" in response.text
    assert "api_key" in response.text  # actionable field path is retained


def test_auth_rate_limiter_returns_429_with_security_headers(client):
    auth_limiter.reset()
    auth_limiter.configure(2, 60)
    try:
        for _ in range(2):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.test", "password": "WrongPassword1!"},
            )
            assert response.status_code == 401
        blocked = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.test", "password": "WrongPassword1!"},
        )
        assert blocked.status_code == 429
        assert blocked.headers["X-Content-Type-Options"] == "nosniff"
        assert "too many authentication attempts" in blocked.text
    finally:
        auth_limiter.reset()
        auth_limiter.configure(300, 60)


def test_cors_allowlist_defaults_to_same_origin(monkeypatch):
    monkeypatch.delenv("NOVARA_CORS_ORIGINS", raising=False)
    assert cors_origins_from_env() == []

    monkeypatch.setenv(
        "NOVARA_CORS_ORIGINS", "https://app.example.test, https://admin.example.test"
    )
    assert cors_origins_from_env() == [
        "https://app.example.test",
        "https://admin.example.test",
    ]

    app = FastAPI()
    install_security(app)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    with TestClient(app) as test_client:
        foreign = test_client.get("/ping", headers={"Origin": "https://evil.example.test"})
        assert "access-control-allow-origin" not in foreign.headers
        allowed = test_client.get("/ping", headers={"Origin": "https://app.example.test"})
        assert allowed.headers["access-control-allow-origin"] == "https://app.example.test"
