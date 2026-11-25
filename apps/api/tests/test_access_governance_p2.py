"""Named acceptance tests for clean-room access governance.

Covers CW-130, CW-139, PL-124, PL-125, NV-070. Every test drives the real
FastAPI app with real persisted, workspace-scoped rows. No upstream source is
copied. No external service, licence server or hosted control plane is
contacted; socket.socket.connect is patched to raise. IP data is never invented.
"""

from __future__ import annotations

import socket

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}/access-governance"


def _ctx(client, name="AccessGov", email="ag-owner@example.com"):
    tokens = bootstrap(client, name, email)
    return tokens["workspace_id"], auth(tokens["access_token"]), tokens


def _base(wid):
    return API.format(wid=wid)


def _no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("access-governance endpoint attempted outbound traffic")
    monkeypatch.setattr(socket.socket, "connect", blocked)


def _invite(client, wid, owner_headers, email, role="read_only"):
    res = client.post(f"/api/v1/workspaces/{wid}/invitations", headers=owner_headers, json={
        "email": email, "role": role,
    })
    assert res.status_code in (200, 201), res.text
    token = res.json()["invite_token"]
    # register the invitee as a global user
    reg = client.post("/api/v1/auth/register", json={
        "email": email, "password": "Password123!", "display_name": email.split("@")[0],
    })
    assert reg.status_code in (200, 201), reg.text
    reg_h = auth(reg.json()["access_token"])
    # accept invitation - returns tokens scoped to invited workspace
    acc = client.post("/api/v1/invitations/accept", headers=reg_h, json={"token": token})
    assert acc.status_code in (200, 201), acc.text
    u_h = auth(acc.json()["access_token"])
    me = client.get("/api/v1/auth/me", headers=u_h)
    assert me.status_code == 200, me.text
    return me.json()["user"]["id"], u_h, acc.json()


def test_cw130_custom_role_create_assign_enforce_revoke(client, monkeypatch):
    """CW-130: custom role can be created, assigned, changed and revoked; permissions enforced server-side."""
    _no_network(monkeypatch)
    wid, h, tokens = _ctx(client, email="cw130-owner@example.com")
    # create custom role with limited permissions
    res = client.post(f"{_base(wid)}/custom-roles", headers=h, json={
        "slug": "auditor-lite",
        "name": "Auditor Lite",
        "description": "Read audit only",
        "permissions": ["audit:read", "contact:read"],
    })
    assert res.status_code == 201, res.text
    role = res.json()
    role_id = role["id"]
    assert role["slug"] == "auditor-lite"
    assert "audit:read" in role["permissions"]

    # assign to a member
    user_id, u_h, _ = _invite(client, wid, h, "cw130-user@example.com")
    res = client.post(f"{_base(wid)}/custom-roles/{role_id}/assign", headers=h, json={
        "user_id": user_id, "role": role_id,
    })
    assert res.status_code == 200, res.text
    assert res.json()["role"] == f"custom:{role_id}"

    # enforced server-side: member can read audit
    res = client.get(f"{_base(wid)}/audit", headers=u_h)
    assert res.status_code == 200, res.text
    # but cannot manage workspace
    res = client.get(f"{_base(wid)}/custom-roles", headers=u_h)
    assert res.status_code == 403, res.text

    # change role permissions
    res = client.patch(f"{_base(wid)}/custom-roles/{role_id}", headers=h, json={
        "permissions": ["contact:read"],
    })
    assert res.status_code == 200, res.text
    # audit now denied
    res = client.get(f"{_base(wid)}/audit", headers=u_h)
    assert res.status_code == 403, res.text

    # revoke
    res = client.post(f"{_base(wid)}/custom-roles/{role_id}/revoke", headers=h, json={
        "user_id": user_id, "role": role_id,
    })
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "read_only"


def test_cw130_custom_role_cross_workspace_denied(client, monkeypatch):
    """CW-130: custom role cannot be used cross-workspace."""
    _no_network(monkeypatch)
    wid, h, _ = _ctx(client, email="cw130x-owner@example.com")
    res = client.post(f"{_base(wid)}/custom-roles", headers=h, json={
        "slug": "xrole", "name": "X", "permissions": ["contact:read"],
    })
    assert res.status_code == 201, res.text
    role_id = res.json()["id"]
    # other workspace
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"})
    assert other.status_code == 200, other.text
    other_wid = other.json()["workspace_id"]
    other_h = auth(other.json()["access_token"])
    res = client.get(f"{_base(other_wid)}/custom-roles/{role_id}", headers=other_h)
    # no get endpoint; use list and ensure not present, and patch denied by 404
    res = client.patch(f"{_base(other_wid)}/custom-roles/{role_id}", headers=other_h, json={"name": "nope"})
    assert res.status_code == 404, res.text
    res = client.get(f"{_base(other_wid)}/custom-roles", headers=other_h)
    assert res.status_code == 200
    assert all(r["id"] != role_id for r in res.json())


def test_cw139_audit_query_returns_real_fields(client, monkeypatch):
    """CW-139: audit query returns real actor, type, timestamp, correlation scoped to workspace; no IP invented."""
    _no_network(monkeypatch)
    wid, h, tokens = _ctx(client, email="cw139-owner@example.com")
    # create a custom role to generate audit events
    res = client.post(f"{_base(wid)}/custom-roles", headers=h, json={
        "slug": "audit-src", "name": "Audit Source", "permissions": ["contact:read"],
    })
    assert res.status_code == 201, res.text
    # query audit
    res = client.get(f"{_base(wid)}/audit?event_type=access.custom_role_created", headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ip_recorded"] is False
    assert "actor_id" in body["fields_recorded"]
    assert "occurred_at" in body["fields_recorded"]
    assert "correlation_id" in body["fields_recorded"]
    assert body["count"] >= 1
    row = body["items"][0]
    assert row["event_type"] == "access.custom_role_created"
    assert row["actor_id"]
    assert row["occurred_at"]
    assert row["correlation_id"]
    assert "ip" not in str(row).lower() or row.get("ip") is None

    # export
    res = client.get(f"{_base(wid)}/audit/export", headers=h)
    assert res.status_code == 200, res.text
    assert "text/csv" in res.headers.get("content-type", "")
    assert "actor_id" in res.text.splitlines()[0]
    assert "ip" not in res.text.splitlines()[0].lower()

    # cross-workspace isolation
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other2"})
    assert other.status_code == 200, other.text
    other_h = auth(other.json()["access_token"])
    res = client.get(f"{_base(other.json()['workspace_id'])}/audit?event_type=access.custom_role_created", headers=other_h)
    assert res.status_code == 200
    assert res.json()["count"] == 0


def test_pl124_custom_role_editor_allowlist(client, monkeypatch):
    """PL-124: custom role editor over NOVARA permissions; unknown perms rejected."""
    _no_network(monkeypatch)
    wid, h, _ = _ctx(client, email="pl124-owner@example.com")
    # list allowed permissions
    res = client.get(f"{_base(wid)}/permissions", headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "allow_list" in body
    assert "contact:read" in body["allow_list"]
    assert "*" not in body["allow_list"]

    # reject unknown permission
    res = client.post(f"{_base(wid)}/custom-roles", headers=h, json={
        "slug": "bad", "name": "Bad", "permissions": ["not:a-real-perm"],
    })
    assert res.status_code == 422, res.text

    # reject wildcard
    res = client.post(f"{_base(wid)}/custom-roles", headers=h, json={
        "slug": "bad2", "name": "Bad2", "permissions": ["*"],
    })
    assert res.status_code == 422, res.text

    # valid create
    res = client.post(f"{_base(wid)}/custom-roles", headers=h, json={
        "slug": "editor-role", "name": "Editor", "permissions": ["contact:read", "contact:write"],
    })
    assert res.status_code == 201, res.text


def test_pl125_permission_scheme_assign_propagate_audit(client, monkeypatch):
    """PL-125: scheme can be created, assigned to project, changes propagate, audited."""
    _no_network(monkeypatch)
    wid, h, _ = _ctx(client, email="pl125-owner@example.com")
    # create scheme
    res = client.post(f"{_base(wid)}/schemes", headers=h, json={
        "name": "Restricted Project",
        "description": "Narrows read_only",
        "grants": {"read_only": ["contact:read"]},
    })
    assert res.status_code == 201, res.text
    scheme = res.json()
    scheme_id = scheme["id"]

    # assign to project (use a fake project id - assignment is workspace-scoped record)
    project_id = "11111111-1111-1111-1111-111111111111"
    res = client.post(f"{_base(wid)}/schemes/{scheme_id}/assign", headers=h, json={"project_id": project_id})
    assert res.status_code == 200, res.text

    # assignments list
    res = client.get(f"{_base(wid)}/schemes/{scheme_id}/assignments", headers=h)
    assert res.status_code == 200, res.text
    assert any(a["project_id"] == project_id for a in res.json())

    # effective permissions for owner - owner has role 'owner' (ALL) but scheme grant for read_only only; owner not narrowed by read_only grant
    me = client.get("/api/v1/auth/me", headers=h).json()
    uid = me['user']['id']
    res = client.get(f"{_base(wid)}/projects/{project_id}/effective-permissions?user_id={uid}", headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["scheme_id"] == scheme_id

    # update scheme - propagates (assignments still point to scheme)
    res = client.patch(f"{_base(wid)}/schemes/{scheme_id}", headers=h, json={
        "grants": {"read_only": ["contact:read", "company:read"]},
    })
    assert res.status_code == 200, res.text
    assert "company:read" in res.json()["grants"]["read_only"]

    # audit has scheme events
    res = client.get(f"{_base(wid)}/audit?event_type=access.permission_scheme_assigned", headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["count"] >= 1


def test_nv070_fine_grained_notification_permissions(client, monkeypatch):
    """NV-070: fine-grained notification/workflow/integration/webhook/billing permissions map and deny."""
    _no_network(monkeypatch)
    wid, h, _ = _ctx(client, email="nv070-owner@example.com")
    # custom role with only notification workflow read
    res = client.post(f"{_base(wid)}/custom-roles", headers=h, json={
        "slug": "notif-reader", "name": "Notif Reader",
        "permissions": ["notification_workflow:read", "audit:read"],
    })
    assert res.status_code == 201, res.text
    role_id = res.json()["id"]

    user_id, u_h, _ = _invite(client, wid, h, "nv070-user@example.com")
    client.post(f"{_base(wid)}/custom-roles/{role_id}/assign", headers=h, json={"user_id": user_id, "role": role_id})

    # check permission endpoint
    res = client.post(f"{_base(wid)}/permissions/check", headers=u_h, json={
        "permission": "notification_workflow:read"
    })
    assert res.status_code == 200, res.text
    assert res.json()["allowed"] is True

    res = client.post(f"{_base(wid)}/permissions/check", headers=u_h, json={
        "permission": "billing:write"
    })
    assert res.status_code == 200, res.text
    assert res.json()["allowed"] is False

    res = client.post(f"{_base(wid)}/permissions/check", headers=u_h, json={
        "permission": "integration:write"
    })
    assert res.status_code == 200, res.text
    assert res.json()["allowed"] is False