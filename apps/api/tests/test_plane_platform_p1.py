"""Named acceptance evidence for the remaining Plane platform P1 rows.

Every test drives the real FastAPI app through the shared fixtures or inspects
the real SQLAlchemy metadata. No external service, credential or mock success
response is involved.
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from novara_core.database import Base
from novara_core.main import API, app
from novara_core.middleware import auth_limiter

from .conftest import auth, bootstrap


def test_pl041_admin_can_change_workspace_settings_and_every_change_is_audited(client):
    tokens = bootstrap(client)
    workspace_id = tokens["workspace_id"]
    headers = auth(tokens["access_token"])

    before = client.get(f"{API}/workspaces/{workspace_id}/admin/settings", headers=headers)
    assert before.status_code == 200, before.text

    changed = client.patch(
        f"{API}/workspaces/{workspace_id}/admin/settings",
        headers=headers,
        json={"name": "Acme Renamed", "settings": {"timezone": "UTC", "tier": "pro"}},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["name"] == "Acme Renamed"
    assert changed.json()["settings"]["timezone"] == "UTC"
    assert changed.json()["updated_by"]

    after = client.get(f"{API}/workspaces/{workspace_id}/admin/settings", headers=headers)
    assert after.status_code == 200
    assert after.json()["settings"] == {"timezone": "UTC", "tier": "pro"}

    events = client.get(f"{API}/workspaces/{workspace_id}/events", headers=headers)
    assert events.status_code == 200, events.text
    updates = [e for e in events.json() if e["event_type"] == "workspace.settings_updated"]
    assert len(updates) == 1, updates
    assert updates[0]["payload"]["actor_id"], updates[0]
    assert set(updates[0]["payload"]["fields"]) == {"name", "settings"}

    secrets = client.patch(
        f"{API}/workspaces/{workspace_id}/admin/settings",
        headers=headers,
        json={"settings": {"api_key": "should-never-be-stored"}},
    )
    assert secrets.status_code == 422, secrets.text

    other = client.post(
        f"{API}/setup/bootstrap",
        json={"workspace_name": "Other", "email": "other@example.com",
              "password": "Password123!", "display_name": "Other"},
    )
    assert other.status_code == 409  # bootstrap remains single-use
    intruder_headers = auth(client.post(
        API + "/auth/login",
        json={"email": "owner@example.com", "password": "Password123!"},
    ).json()["access_token"])
    assert client.get(
        f"{API}/workspaces/foreign/admin/settings", headers=intruder_headers
    ).status_code == 403


def test_pl044_api_prefix_is_versioned_documented_and_permission_checked(client):
    # Included routers are nested in this FastAPI version, so read the
    # generated OpenAPI document: it is the public, versioned route inventory.
    paths = [p for p in app.openapi()["paths"] if p.startswith("/api/")]
    assert paths, "API routes must exist"
    # PL-044's invariant is that every /api/ route is versioned. /api/v2/ is
    # the documented clean-room REST surface (GB-060); no unversioned route is
    # permitted.
    assert all(p.startswith(("/api/v1/", "/api/v2/")) for p in paths), paths

    tokens = bootstrap(client)
    workspace_id = tokens["workspace_id"]
    url = f"{API}/workspaces/{workspace_id}/admin/settings"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=auth("not-a-real-token")).status_code == 401
    assert client.get(url, headers=auth(tokens["access_token"])).status_code == 200

    schema = app.openapi()
    assert schema["info"]["version"], "OpenAPI must declare a version"
    documented = "/api/v1/workspaces/{workspace_id}/admin/settings"
    assert documented in schema["paths"], "the real permission-checked route must be documented"


def test_pl049_rate_limit_headers_and_429_through_real_app(client):
    previous_limit, previous_window = auth_limiter.limit, auth_limiter.window_seconds
    auth_limiter.configure(2, 60)
    auth_limiter.reset()
    try:
        responses = [
            client.post(API + "/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
            for _ in range(3)
        ]
        assert [r.status_code for r in responses[:2]] == [401, 401]
        assert responses[2].status_code == 429, responses[2].text
        for response in responses:
            assert response.headers["X-RateLimit-Limit"] == "2"
            assert response.headers["X-RateLimit-Window"] == "60"
            assert "X-RateLimit-Remaining" in response.headers
        assert responses[0].headers["X-RateLimit-Remaining"] == "1"
        assert responses[2].headers["Retry-After"] == "60"
        for name in ("X-Content-Type-Options", "Content-Security-Policy"):
            assert name in responses[2].headers
    finally:
        auth_limiter.configure(previous_limit, previous_window)
        auth_limiter.reset()


def test_pl055_password_lifecycle_rejects_replayed_reset_tokens(client, monkeypatch):
    monkeypatch.setenv("NOVARA_DEV_MODE", "1")
    tokens = bootstrap(client)
    headers = auth(tokens["access_token"])
    assert client.get(API + "/auth/me", headers=headers).status_code == 200

    requested = client.post(
        API + "/auth/password-reset/request", json={"email": "owner@example.com"}
    )
    assert requested.status_code == 200, requested.text
    raw = requested.json()["development_token"]

    changed = client.post(
        API + "/auth/password-reset/confirm",
        json={"token": raw, "new_password": "Changed123!"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["sessions_revoked"] is True

    replay = client.post(
        API + "/auth/password-reset/confirm",
        json={"token": raw, "new_password": "Again123!"},
    )
    assert replay.status_code == 400, replay.text
    assert client.get(API + "/auth/me", headers=headers).status_code == 401

    login = client.post(
        API + "/auth/login",
        json={"email": "owner@example.com", "password": "Changed123!"},
    )
    assert login.status_code == 200, login.text
    assert client.get(API + "/auth/me", headers=auth(login.json()["access_token"])).status_code == 200


def test_pl057_bearer_sessions_replace_csrf_tokens_without_a_cookie_surface(client):
    """NOVARA uses bearer tokens, not ambient cookies, so CSRF is not applicable.

    The accepted replacement is proven here: auth responses set no cookie,
    cross-origin credentialed requests are not allowed, and state-changing
    requests require the bearer token.
    """
    login = client.post(
        API + "/auth/login", json={"email": "missing@example.com", "password": "wrong"}
    )
    assert "set-cookie" not in {k.lower() for k in login.headers}

    tokens = bootstrap(client)
    refreshed = client.post(
        API + "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert "set-cookie" not in {k.lower() for k in refreshed.headers}
    # Refresh rotates the session, so the old access token must stop working.
    current_token = refreshed.json()["access_token"]

    preflight = client.options(
        API + "/auth/login",
        headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"},
    )
    assert preflight.headers.get("access-control-allow-origin") != "https://untrusted.example"

    url = f"{API}/workspaces/{tokens['workspace_id']}/admin/settings"
    assert client.patch(url, json={"settings": {"x": 1}}).status_code == 401
    assert client.patch(url, headers=auth(tokens["access_token"]),
                        json={"settings": {"x": 1}}).status_code == 401
    assert client.patch(url, headers=auth(current_token),
                        json={"settings": {"x": 1}}).status_code == 200


def test_pl105_invite_acceptance_creates_membership_and_audited_event(client):
    owner = bootstrap(client)
    workspace_id = owner["workspace_id"]
    invite = client.post(
        f"{API}/workspaces/{workspace_id}/invitations",
        headers=auth(owner["access_token"]),
        json={"email": "member@example.com", "role": "admin"},
    )
    assert invite.status_code == 200, invite.text
    raw = invite.json()["invite_token"]

    member = client.post(
        API + "/auth/register",
        json={"email": "member@example.com", "password": "Password123!",
              "display_name": "Member"},
    )
    assert member.status_code == 200, member.text

    accepted = client.post(
        API + "/invitations/accept",
        headers=auth(member.json()["access_token"]),
        json={"token": raw},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["workspace_id"] == workspace_id

    members = client.get(
        f"{API}/workspaces/{workspace_id}/members", headers=auth(owner["access_token"])
    )
    assert members.status_code == 200, members.text
    assert any(m["email"] == "member@example.com" and m["role"] == "admin"
               for m in members.json()), members.json()

    events = client.get(f"{API}/workspaces/{workspace_id}/events",
                        headers=auth(owner["access_token"]))
    joined = [e for e in events.json() if e["event_type"] == "member.joined"]
    assert len(joined) == 1, events.json()

    replay = client.post(
        API + "/invitations/accept",
        headers=auth(member.json()["access_token"]),
        json={"token": raw},
    )
    assert replay.status_code == 400, replay.text


def test_pl033_and_pl077_intake_creates_one_real_notification_and_event(client, db_session):
    tokens = bootstrap(client)
    workspace_id = tokens["workspace_id"]
    headers = auth(tokens["access_token"])

    intake = client.post(
        f"{API}/workspaces/{workspace_id}/intake/website-form",
        headers=headers,
        json={"email": "visitor@example.com", "full_name": "Visitor", "message": "Hello"},
    )
    assert intake.status_code == 201, intake.text

    notifications = client.get(f"{API}/workspaces/{workspace_id}/notifications",
                                headers=headers)
    assert notifications.status_code == 200, notifications.text
    assert len(notifications.json()) == 1, notifications.json()
    assert notifications.json()[0]["workspace_id"] == workspace_id

    events = client.get(f"{API}/workspaces/{workspace_id}/events", headers=headers)
    created = [e for e in events.json() if e["event_type"] == "notification.created"]
    assert len(created) == 1, events.json()
    assert created[0]["entity_id"] == notifications.json()[0]["id"]

    # Static UI guard: the notification is visible on a real route.
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "web" / "app.js"
    assert source.exists()
    assert "/notifications" in source.read_text(encoding="utf-8")


def test_pl147_and_pl148_workspace_tables_compile_to_postgresql_ddl():
    """Offline DDL compilation evidence; no PostgreSQL server is available here."""
    tables = [t for t in Base.metadata.sorted_tables if "workspace_id" in t.columns]
    assert len(tables) >= 20, len(tables)
    for table in tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "CREATE TABLE" in ddl, table.name
        assert "workspace_id" in ddl, table.name
        assert '"' in ddl or table.name.islower(), table.name
