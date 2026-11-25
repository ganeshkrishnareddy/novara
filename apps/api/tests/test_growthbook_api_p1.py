"""Named acceptance evidence for clean-room GrowthBook P1 rows.

NOVARA exposes its own versioned, workspace-scoped API and local account/workspace
lifecycle instead of vendoring GrowthBook source or requiring MongoDB. Each test
proves the equivalent guarantee against the real app; no external call is made.
"""

from __future__ import annotations

from pathlib import Path

from novara_core.main import API, app
from novara_core.modules import adapters, integrations

from .conftest import auth, bootstrap

WEB = Path(__file__).resolve().parents[2] / "web" / "app.js"


def _login(client, email, password, workspace_id=None):
    body = {"email": email, "password": password}
    if workspace_id:
        body["workspace_id"] = workspace_id
    response = client.post(API + "/auth/login", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _web_source():
    return WEB.read_text(encoding="utf-8")


def test_gb059_versioned_rest_api_is_validated_permission_checked_and_wired(client):
    """GB-059: one documented, versioned REST surface with real auth and validation."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    schema = app.openapi()
    assert schema["info"]["version"]
    paths = [p for p in schema["paths"] if p.startswith("/api/")]
    # GB-059's invariant is a versioned API surface; /api/v2/ is the documented
    # clean-room REST surface (GB-060) and is versioned too.
    assert paths and all(p.startswith(("/api/v1/", "/api/v2/")) for p in paths)

    url = f"{API}/workspaces/{wid}/admin/settings"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=auth("forged")).status_code == 401
    assert client.get(url, headers=headers).status_code == 200

    bad = client.patch(url, headers=headers,
                       json={"settings": {"apiKey": "must-not-be-stored"}})
    assert bad.status_code == 422, bad.text
    good = client.patch(url, headers=headers,
                        json={"settings": {"timezone": "Asia/Calcutta"}})
    assert good.status_code == 200, good.text
    assert good.json()["settings"]["timezone"] == "Asia/Calcutta"

    source = _web_source()
    assert "/api/v1/workspaces/" in source and "apiW(" in source
    assert "Admin" in source


def test_gb063_organisations_are_workspaces_with_members_and_isolation(client):
    """GB-063: the organisation equivalent is a real, switchable workspace."""
    first = bootstrap(client)
    wid, headers = first["workspace_id"], auth(first["access_token"])

    second = client.post(API + "/workspaces", headers=headers, json={"name": "Org Two"})
    assert second.status_code == 200, second.text
    wid2 = second.json()["workspace_id"]

    listed = client.get(API + "/workspaces", headers=headers)
    assert listed.status_code == 200, listed.text
    names = {row["name"] for row in listed.json()}
    assert {"Acme", "Org Two"} <= names

    switched = _login(client, "owner@example.com", "Password123!", wid2)
    headers2 = auth(switched["access_token"])
    assert client.get(f"{API}/workspaces/{wid2}/admin/settings", headers=headers2).status_code == 200
    assert client.get(f"{API}/workspaces/{wid}/admin/settings", headers=headers2).status_code == 403
    assert client.get(f"{API}/workspaces/{wid2}/members", headers=headers).status_code == 403

    members = client.get(f"{API}/workspaces/{wid2}/members", headers=headers2).json()
    assert any(m["email"] == "owner@example.com" and m["role"] == "owner" for m in members)

    source = _web_source()
    assert "route: 'workspaces'" in source and "loadWorkspacesPage" in source


def test_gb064_local_email_and_password_accounts_validate_and_scope_sessions(client):
    """GB-064: local accounts, password lifecycle and workspace-scoped sessions."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    assert client.post(API + "/auth/login", json={
        "email": "owner@example.com", "password": "wrong",
    }).status_code == 401
    assert client.post(API + "/auth/login", json={
        "email": "not-an-email", "password": "Password123!",
    }).status_code == 422

    other_session = _login(client, "owner@example.com", "Password123!", wid)
    assert client.get(API + "/auth/me", headers=auth(other_session["access_token"])).status_code == 200

    changed = client.post(API + "/auth/change-password", headers=headers, json={
        "current_password": "Password123!", "new_password": "Changed123!",
    })
    assert changed.status_code == 200, changed.text
    assert client.get(API + "/auth/me",
                      headers=auth(other_session["access_token"])).status_code == 401
    assert client.get(API + "/auth/me", headers=headers).status_code == 200
    assert client.post(API + "/auth/login", json={
        "email": "owner@example.com", "password": "Password123!",
    }).status_code == 401
    assert _login(client, "owner@example.com", "Changed123!", wid)["workspace_id"] == wid

    source = _web_source()
    assert 'data-form="change-password"' in source


def test_gb117_configured_flag_provider_does_not_claim_delivery(client, db_session):
    """GB-117: a configured status describes local capability, never a live send."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    rejected = client.put(f"{API}/workspaces/{wid}/integrations", headers=headers, json={
        "provider": "growthbook", "config": {"apiKey": "must-not-be-stored"},
    })
    assert rejected.status_code == 422, rejected.text

    accepted = client.put(f"{API}/workspaces/{wid}/integrations", headers=headers, json={
        "provider": "growthbook", "config": {"host": "https://flags.example"},
    })
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "configured"
    assert "apiKey" not in accepted.json()["config"]

    capabilities = client.get(f"{API}/workspaces/{wid}/integrations/capabilities",
                              headers=headers)
    assert capabilities.status_code == 200, capabilities.text
    entry = next(p for p in capabilities.json()["providers"] if p["provider"] == "growthbook")
    assert entry["configured"] is True

    adapter_state = client.get(f"{API}/workspaces/{wid}/adapters/capabilities",
                               headers=headers)
    assert adapter_state.status_code == 200, adapter_state.text
    assert adapter_state.json()["configurable_provider_count"] >= 1
    assert "delivered" not in str(adapter_state.json()).lower()

    assert integrations.SUPPORTED_PROVIDERS["growthbook"] == "GrowthBook"
    assert adapters.PROVIDER_KINDS["growthbook"] == "flags"
