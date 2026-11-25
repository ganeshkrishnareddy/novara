"""Named acceptance tests for the T-060 P0 cluster.

PL-001: a workspace can be created, switched and administered with persistent
members and cross-workspace reads denied.
PL-043: an explicitly configured Plane-compatible adapter records CRUD calls
without embedding Plane or contacting it.
MT-072: contacts, forms and pages are documented API contexts with real get,
getList, create, edit and delete semantics, validation and permissions.
NV-057: every notification/workflow route is in the production OpenAPI document
and declares the shared bearer + workspace contract, enforced at runtime.

No test here sends an external message or makes an outbound network call.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from novara_core.main import API, app
from novara_core.models import Event
from novara_core.modules import api_resources, adapters, workspace_admin

from .conftest import auth, bootstrap


ADAPTERS_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "novara_core" / "modules" / "adapters.py"
)


# ---------------------------------------------------------------------------
# PL-001 — workspace administration
# ---------------------------------------------------------------------------


def test_workspace_can_be_created_switched_and_administered(client, db_session):
    first = bootstrap(client)
    wid, headers = first["workspace_id"], auth(first["access_token"])

    # A second workspace is created by the same identity, then switched to by
    # signing in with its id — membership and sessions are both persistent.
    second = client.post(f"{API}/workspaces", headers=headers, json={"name": "Second"})
    assert second.status_code == 200, second.text
    wid2 = second.json()["workspace_id"]
    switched = client.post(f"{API}/auth/login", json={
        "email": "owner@example.com", "password": "Password123!", "workspace_id": wid2,
    })
    assert switched.status_code == 200, switched.text
    headers2 = auth(switched.json()["access_token"])

    members = client.get(f"{API}/workspaces/{wid}/members", headers=headers)
    assert members.status_code == 200 and len(members.json()) == 1
    assert members.json()[0]["role"] == "owner"

    base = f"{API}/workspaces/{wid}/admin"
    defaults = client.get(f"{base}/settings", headers=headers)
    assert defaults.status_code == 200, defaults.text
    assert defaults.json()["settings"] == {}

    saved = client.patch(f"{base}/settings", headers=headers, json={
        "name": "Acme Admin", "settings": {"timezone": "Asia/Calcutta", "currency": "INR"},
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["name"] == "Acme Admin"
    again = client.get(f"{base}/settings", headers=headers)
    assert again.json()["settings"] == {"timezone": "Asia/Calcutta", "currency": "INR"}

    # Secrets are rejected before they reach the settings row.
    bad = client.patch(f"{base}/settings", headers=headers, json={
        "settings": {"apiKey": "must-not-be-stored"},
    })
    assert bad.status_code == 422

    summary = client.get(f"{base}/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["active_members"] == 1
    assert summary.json()["name"] == "Acme Admin"

    # Cross-workspace reads are denied for every admin surface, including an
    # id that exists but belongs to the other session's workspace.
    for path in (f"{base}/settings", f"{base}/summary", f"{API}/workspaces/{wid}/members"):
        assert client.get(path, headers=headers2).status_code == 403, path
    assert client.get(f"{API}/workspaces/{wid2}/admin/settings", headers=headers).status_code == 403

    types = {e.event_type for e in db_session.execute(select(Event)).scalars().all()}
    assert workspace_admin.WORKSPACE_SETTINGS_UPDATED in types


# ---------------------------------------------------------------------------
# PL-043 — opt-in Plane-compatible adapter
# ---------------------------------------------------------------------------


def test_plane_adapter_records_crud_calls_only_when_configured(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"{API}/workspaces/{wid}"
    invoke_url = f"{base}/adapters/plane/invoke"

    # No configuration: the call is rejected and still recorded for audit.
    before = client.post(invoke_url, headers=headers, json={
        "operation": "getlist", "request": {"context": "projects"},
    })
    assert before.status_code == 200, before.text
    assert before.json()["status"] == "rejected"
    assert before.json()["response"]["delivered"] is False

    configured = client.put(f"{base}/integrations", headers=headers, json={
        "provider": "plane",
        "config": {"base_url": "https://plane.example/api/", "scope": "projects"},
    })
    assert configured.status_code == 200, configured.text
    assert configured.json()["status"] == "configured"

    calls = []
    for verb in ("get", "getlist", "create", "edit", "delete"):
        result = client.post(invoke_url, headers=headers, json={
            "operation": verb,
            "request": {"context": "projects", "entity": "work-items", "entity_id": "PL-1"},
        })
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["status"] == "recorded"
        assert body["kind"] == "project_management"
        assert body["response"]["mode"] == "local_mock"
        assert body["response"]["delivered"] is False
        assert body["response"]["external"] is False
        calls.append(body["call_id"])

    recorded = client.get(f"{base}/adapters/calls?provider=plane", headers=headers).json()
    assert {row["id"] for row in recorded} >= set(calls)
    assert all(row["operation"] in adapters.CRUD_OPERATIONS for row in recorded)

    # The adapter is our own local seam: no HTTP client and no embedded source.
    source = ADAPTERS_SOURCE.read_text(encoding="utf-8")
    assert "import httpx" not in source and "import requests" not in source
    assert "plane.so" not in source


# ---------------------------------------------------------------------------
# MT-072 — documented API contexts with full CRUD
# ---------------------------------------------------------------------------


def _crud_roundtrip(client, base, headers, context, create_body, edit_body, identity):
    created = client.post(f"{base}/{context}", headers=headers, json=create_body)
    assert created.status_code == 201, created.text
    resource_id = created.json()["id"]
    assert created.json()[identity] == create_body[identity]

    listing = client.get(f"{base}/{context}", headers=headers)
    assert listing.status_code == 200 and resource_id in [r["id"] for r in listing.json()]

    fetched = client.get(f"{base}/{context}/{resource_id}", headers=headers)
    assert fetched.status_code == 200 and fetched.json()["id"] == resource_id

    edited = client.patch(f"{base}/{context}/{resource_id}", headers=headers, json=edit_body)
    assert edited.status_code == 200, edited.text
    for key, value in edit_body.items():
        assert edited.json()[key] == value

    duplicate = client.post(f"{base}/{context}", headers=headers, json=create_body)
    assert duplicate.status_code == 409

    deleted = client.delete(f"{base}/{context}/{resource_id}", headers=headers)
    assert deleted.status_code == 200 and deleted.json() == {
        "deleted": True, "context": context, "id": resource_id,
    }
    assert client.get(f"{base}/{context}/{resource_id}", headers=headers).status_code == 404
    return resource_id


def test_api_contexts_expose_full_crud_with_validation_and_permissions(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"{API}/workspaces/{wid}/api"

    _crud_roundtrip(
        client, base, headers, "contacts",
        {"email": "api-contact@example.com", "full_name": "API Contact"},
        {"full_name": "Renamed Contact", "lifecycle_stage": "customer"},
        "email",
    )
    _crud_roundtrip(
        client, base, headers, "forms",
        {"name": "Signup", "fields": [{"name": "email", "type": "email"}]},
        {"status": "published", "description": "Live form"},
        "name",
    )
    _crud_roundtrip(
        client, base, headers, "pages",
        {"title": "Launch", "slug": "launch", "content": "Hello"},
        {"title": "Launch 2", "status": "published"},
        "slug",
    )

    # Validation is real, not a 200 with an empty body.
    assert client.post(f"{base}/contacts", headers=headers,
                       json={"email": "not-an-email"}).status_code == 422
    assert client.post(f"{base}/forms", headers=headers,
                       json={"name": "Bad", "status": "live"}).status_code == 422
    assert client.post(f"{base}/pages", headers=headers,
                       json={"title": "Bad", "slug": "not a slug"}).status_code == 422

    # getList honours paging, and auth/workspace rules are shared.
    paged = client.get(f"{base}/contacts?limit=1&offset=0", headers=headers)
    assert paged.status_code == 200 and len(paged.json()) <= 1
    assert client.get(f"{base}/forms").status_code == 401
    other = client.post(f"{API}/workspaces", headers=headers, json={"name": "Other"})
    other_headers = auth(other.json()["access_token"])
    created_form = client.post(f"{base}/forms", headers=headers,
                               json={"name": "Private form"}).json()
    assert client.get(f"{base}/forms/{created_form['id']}",
                      headers=other_headers).status_code == 403

    types = {e.event_type for e in db_session.execute(select(Event)).scalars().all()}
    assert {api_resources.RESOURCE_CREATED, api_resources.RESOURCE_UPDATED,
            api_resources.RESOURCE_DELETED} <= types


# ---------------------------------------------------------------------------
# NV-057 — one documented, auth-declared API surface
# ---------------------------------------------------------------------------


def test_notification_and_workflow_routes_are_documented_and_workspace_scoped(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    schema = response.json()
    schemes = schema["components"]["securitySchemes"]
    assert schemes["BearerAuth"]["scheme"] == "bearer"

    documented = set(schema["paths"])
    live = set()
    for entry in app.routes:
        # Module routers are attached as one entry that expands at schema time.
        routes = [entry]
        inner = getattr(entry, "original_router", None)
        if inner is not None:
            routes.extend(getattr(inner, "routes", ()))
        for route in routes:
            tags = set(getattr(route, "tags", ()) or ())
            path = getattr(route, "path", "")
            if (
                tags & {"activity", "workflow", "notification-preferences", "jobs"}
                or "/notifications" in path
                or "/notification-preferences" in path
                or "/jobs" in path
            ):
                live.add(path)
    canonical = {
        f"{API}/workspaces/{{workspace_id}}/notifications",
        f"{API}/workspaces/{{workspace_id}}/notifications/counts",
        f"{API}/workspaces/{{workspace_id}}/notifications/{{notification_id}}/read",
        f"{API}/workspaces/{{workspace_id}}/notification-settings",
        f"{API}/workspaces/{{workspace_id}}/notification-preferences",
        f"{API}/workspaces/{{workspace_id}}/jobs",
        f"{API}/workspaces/{{workspace_id}}/outreach-drafts",
    }
    assert canonical <= live
    assert live <= documented, f"undocumented routes: {sorted(live - documented)}"
    for path in live:
        for operation in schema["paths"][path].values():
            if isinstance(operation, dict):
                assert operation.get("security") == [{"BearerAuth": []}], path

    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    checks = (
        f"{API}/workspaces/{wid}/notifications",
        f"{API}/workspaces/{wid}/notification-settings",
        f"{API}/workspaces/{wid}/notification-preferences",
        f"{API}/workspaces/{wid}/jobs",
        f"{API}/workspaces/{wid}/outreach-drafts",
    )
    for path in checks:
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers=headers).status_code == 200, path

    other = client.post(f"{API}/workspaces", headers=headers, json={"name": "Other"})
    other_headers = auth(other.json()["access_token"])
    for path in checks:
        assert client.get(path, headers=other_headers).status_code == 403, path
