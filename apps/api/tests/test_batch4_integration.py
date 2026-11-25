"""Batch 4 cross-module integration smoke tests."""

from __future__ import annotations


def _bootstrap(client):
    from tests.conftest import bootstrap, auth

    tokens = bootstrap(client)
    return tokens["access_token"], auth(tokens["access_token"]), tokens["workspace_id"]


def test_website_form_to_crm_timeline(client):
    token, headers, ws = _bootstrap(client)
    # intake website form
    r = client.post(
        f"/api/v1/workspaces/{ws}/intake/website-form",
        json={"full_name": "Alice", "email": "alice@example.com", "message": "hi", "submission_id": "s1"},
        headers=headers,
    )
    assert r.status_code in (200, 201)
    # contact exists
    contacts = client.get(f"/api/v1/workspaces/{ws}/contacts?search=alice", headers=headers).json()
    assert any(c["email"] == "alice@example.com" for c in contacts)
    # events exist
    ev = client.get(f"/api/v1/workspaces/{ws}/events", headers=headers).json()
    assert len(ev) >= 1
    # timeline correlation present
    corr = ev[0]["correlation_id"]
    assert corr


def test_document_link_view_to_crm_activity(client):
    token, headers, ws = _bootstrap(client)
    doc = client.post(f"/api/v1/workspaces/{ws}/documents", json={"title": "D", "storage_path": "p"}, headers=headers).json()
    link = client.post(f"/api/v1/workspaces/{ws}/documents/{doc['id']}/links", json={}, headers=headers).json()
    tok = link["token"]
    # resolve + visit
    client.get(f"/api/v1/workspaces/{ws}/documents/links/resolve/{tok}", headers=headers)
    v = client.post(f"/api/v1/workspaces/{ws}/documents/links/resolve/{tok}/visits", json={"visitor_name": "Bob"}, headers=headers)
    assert v.status_code == 201
    # event recorded
    ev = client.get(f"/api/v1/workspaces/{ws}/events", headers=headers).json()
    assert any("document" in e["event_type"] for e in ev)


def test_feature_flag_to_analytics(client):
    token, headers, ws = _bootstrap(client)
    client.post(f"/api/v1/workspaces/{ws}/flags", json={"key": "exp", "enabled": True, "rollout_percent": 100}, headers=headers)
    ev = client.post(f"/api/v1/workspaces/{ws}/flags/exp/evaluate", json={"user_key": "u1", "attributes": {}}, headers=headers)
    assert ev.status_code == 200
    # event volume includes flag.evaluated
    vol = client.get(f"/api/v1/workspaces/{ws}/analytics/events/volume", headers=headers).json()
    assert any(v["event_type"] == "flag.evaluated" for v in vol)


def test_project_milestone_event(client):
    token, headers, ws = _bootstrap(client)
    proj = client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "P"}, headers=headers).json()
    pid = proj["id"]
    ms = client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/milestones", json={"name": "M1"}, headers=headers).json()
    mid = ms["id"]
    client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/milestones/{mid}/complete", headers=headers)
    ev = client.get(f"/api/v1/workspaces/{ws}/events", headers=headers).json()
    assert any("project" in e["event_type"] for e in ev)


def test_automation_trigger_to_event(client):
    token, headers, ws = _bootstrap(client)
    auto = client.post(
        f"/api/v1/workspaces/{ws}/automations",
        json={"name": "A", "trigger_type": "manual", "definition": [{"id": "s1", "type": "notify", "channel": "in_app"}]},
        headers=headers,
    ).json()
    aid = auto["id"]
    run = client.post(f"/api/v1/workspaces/{ws}/automations/{aid}/dry_run", json={"trigger_event": "manual", "context": {}}, headers=headers)
    assert run.status_code in (200, 201)
    ev = client.get(f"/api/v1/workspaces/{ws}/events", headers=headers).json()
    assert any("automation" in e["event_type"] for e in ev)