"""Named acceptance tests for the PL clean-room P1 rows.

PL-019, PL-028, PL-116 and PL-117 are implemented from their acceptance
criteria alone (no upstream Plane code). Every test drives the real FastAPI app
with real workspace-scoped persistence, real roles and real append-only events.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

API = "/api/v1"


def _setup(client, name="Extensions", email="ext-owner@example.com"):
    tokens = bootstrap(client, name, email)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    created = client.post(f"{API}/workspaces/{wid}/projects", headers=headers,
                          json={"name": name})
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    return wid, headers, pid


def _extensions(wid):
    return f"{API}/workspaces/{wid}/extensions"


def _item(client, wid, headers, pid, title):
    res = client.post(f"{API}/workspaces/{wid}/projects/{pid}/items", headers=headers,
                      json={"title": title})
    assert res.status_code == 201, res.text
    return res.json()


def _member(client, wid, headers, email, role="read_only"):
    invite = client.post(f"{API}/workspaces/{wid}/invitations", headers=headers,
                         json={"email": email, "role": role})
    assert invite.status_code == 200, invite.text
    registered = client.post(f"{API}/auth/register", json={
        "email": email, "password": "Password123!", "display_name": email.split("@")[0],
    })
    assert registered.status_code == 200, registered.text
    accepted = client.post(f"{API}/invitations/accept",
                           headers=auth(registered.json()["access_token"]),
                           json={"token": invite.json()["invite_token"]})
    assert accepted.status_code == 200, accepted.text
    member_headers = auth(accepted.json()["access_token"])
    me = client.get(f"{API}/auth/me", headers=member_headers).json()
    return member_headers, me["user"]["id"]


def test_pl019_milestones_link_work_and_render_on_a_timeline(client):
    wid, h, pid = _setup(client)
    milestone = client.post(f"{API}/workspaces/{wid}/projects/{pid}/milestones", headers=h,
                            json={"name": "Launch", "due_at": "2026-12-01T00:00:00+00:00"})
    assert milestone.status_code == 201, milestone.text
    mid = milestone.json()["id"]
    item = _item(client, wid, h, pid, "Ship it")
    base = f"{_extensions(wid)}/projects/{pid}/milestones/{mid}/work"
    assert client.get(base, headers=h).json() == []
    linked = client.post(base, headers=h, json={"item_id": item["id"]})
    assert linked.status_code == 201 and linked.json()["linked"] is True
    assert client.post(base, headers=h, json={"item_id": item["id"]}).status_code == 409
    assert [r["item_id"] for r in client.get(base, headers=h).json()] == [item["id"]]
    timeline = client.get(f"{_extensions(wid)}/projects/{pid}/milestones/timeline",
                          headers=h).json()
    row = next(r for r in timeline if r["id"] == mid)
    assert row["name"] == "Launch" and row["work_item_ids"] == [item["id"]]
    assert row["due_at"] is not None and row["completed_at"] is None
    # Cross-workspace reads are refused.
    other = client.post(f"{API}/workspaces", headers=h, json={"name": "Other"}).json()
    assert client.get(f"{API}/workspaces/{other['workspace_id']}/extensions/projects/{pid}/milestones/timeline",
                      headers=h).status_code in (403, 404)


def test_pl028_custom_properties_enforce_types_and_mandatory_rules(client):
    wid, h, pid = _setup(client)
    base = _extensions(wid) + "/properties"
    text = client.post(base, headers=h, json={
        "key": "tier", "name": "Tier", "type": "select", "required": True,
        "options": ["gold", "silver"],
    })
    assert text.status_code == 201, text.text
    number = client.post(base, headers=h, json={"key": "score", "name": "Score", "type": "number"})
    assert number.status_code == 201, number.text
    assert client.post(base, headers=h, json={
        "key": "tier", "name": "Dup", "type": "text"}).status_code == 409
    assert client.post(base, headers=h, json={
        "key": "bad", "name": "Bad", "type": "select"}).status_code == 422
    item = _item(client, wid, h, pid, "Property subject")
    values_url = base + "/values"

    def set_values(payload):
        return client.post(values_url, headers=h, json={"item_id": item["id"], "values": payload})

    assert set_values({"score": 7}).status_code == 422          # missing mandatory tier
    assert set_values({"tier": "gold", "bogus": 1}).status_code == 422
    assert set_values({"tier": "bronze"}).status_code == 422     # not an option
    assert set_values({"tier": "gold", "score": "high"}).status_code == 422
    saved = set_values({"tier": "gold", "score": 9})
    assert saved.status_code == 200 and saved.json()["saved"] == ["score", "tier"]
    fetched = client.get(values_url, headers=h, params={"item_id": item["id"]}).json()
    assert fetched["values"] == {"tier": "gold", "score": 9}


def test_pl116_resource_grants_override_role_defaults_and_deny_wins(client):
    wid, h, pid = _setup(client)
    base = _extensions(wid) + "/access"
    owner = client.get(f"{API}/auth/me", headers=h).json()["user"]["id"]
    reader_headers, _ = _member(client, wid, h, "extensions-reader@example.com", "read_only")
    reader_grant = client.post(base + "/grants", headers=h, json={
        "user_id": client.get(f"{API}/auth/me", headers=reader_headers).json()["user"]["id"],
        "resource_type": "project", "resource_id": pid,
        "permission": "task:write", "effect": "allow",
    })
    assert reader_grant.status_code == 201

    def check(headers, permission="task:write"):
        return client.post(base + "/check", headers=headers, json={
            "resource_type": "project", "resource_id": pid, "permission": permission,
        }).json()

    baseline = check(h)
    assert baseline["allowed"] is True and baseline["source"] == "role"
    deny = client.post(base + "/grants", headers=h, json={
        "user_id": owner, "resource_type": "project", "resource_id": pid,
        "permission": "task:write", "effect": "deny",
    })
    assert deny.status_code == 201, deny.text
    blocked = check(h)
    assert blocked["allowed"] is False and blocked["source"] == "grant:deny"
    grants = client.get(base + "/grants", headers=h).json()
    assert any(g["effect"] == "deny" and g["user_id"] == owner for g in grants)

    member_headers, _ = _member(client, wid, h, "extensions-allow@example.com", "read_only")
    member_id = client.get(f"{API}/auth/me", headers=member_headers).json()["user"]["id"]
    assert check(member_headers)["source"] == "role"  # a grant for another user does not leak
    allow = client.post(base + "/grants", headers=h, json={
        "user_id": member_id, "resource_type": "project", "resource_id": pid,
        "permission": "task:write", "effect": "allow",
    })
    assert allow.status_code == 201, allow.text
    granted = check(member_headers)
    assert granted["allowed"] is True and granted["source"] == "grant:allow"


def test_pl117_audit_view_is_admin_only_filterable_and_exportable(client):
    wid, h, pid = _setup(client)
    item = _item(client, wid, h, pid, "Audited item")
    base = _extensions(wid) + "/audit"
    all_rows = client.get(base, headers=h).json()
    assert all_rows and all_rows == sorted(all_rows, key=lambda row: row["seq"])
    by_type = client.get(base, headers=h, params={"event_type": "project.created"}).json()
    assert by_type and all(r["event_type"] == "project.created" for r in by_type)
    by_entity = client.get(base, headers=h, params={"entity_id": item["id"]}).json()
    assert by_entity and all(r["entity_id"] == item["id"] for r in by_entity)

    exported = client.get(base + "/export", headers=h,
                          params={"event_type": "project.created"})
    assert exported.status_code == 200 and exported.headers["content-type"].startswith("text/csv")
    assert "seq,event_type,entity_id,actor_id,occurred_at" in exported.text
    assert "project.created" in exported.text

    member_headers, _ = _member(client, wid, h, "extensions-auditor@example.com", "read_only")
    assert client.get(base, headers=member_headers).status_code == 403
    assert client.get(base + "/export", headers=member_headers).status_code == 403
    other = client.post(f"{API}/workspaces", headers=h, json={"name": "Other"}).json()
    assert client.get(f"{API}/workspaces/{other['workspace_id']}/extensions/audit",
                      headers=h).status_code in (403, 404)
