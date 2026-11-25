"""Named acceptance tests for the Novu-compatible P2 workflow cluster.

Every test drives the real FastAPI app against real persisted, workspace-scoped
rows. No provider is contacted and no app code is mocked. NV-071 is verified
against the existing hashed/rotating ``api_keys`` module.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.models import Event
from novara_core.modules.api_keys import ApiKey
from novara_core.security import hash_token

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/notification-workflows"
KEYS = "/api/v1/workspaces/{wid}/api-keys"
CONTACTS = "/api/v1/workspaces/{wid}/contacts"


def _ctx(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _workflow(client, wid, h, key="alerts", **extra):
    body = {"key": key, "name": key.replace("-", " ").title(), "channel": "in_app"}
    body.update(extra)
    r = client.post(_base(wid) + "/workflows", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _trigger(client, wid, h, workflow_id, **extra):
    body = {"title": "Hello", "html": "<b>World</b>"}
    body.update(extra)
    r = client.post(f"{_base(wid)}/workflows/{workflow_id}/trigger", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_nv006_one_stable_workflow_api(client):
    wid, h = _ctx(client)
    contract = client.get(_base(wid) + "/api-contract", headers=h).json()
    assert contract["version"] == "1"
    assert contract["legacy_versions"] == []
    wf = _workflow(client, wid, h)
    assert wf["key"] == "alerts" and wf["active"] is True
    assert any(w["id"] == wf["id"] for w in client.get(_base(wid) + "/workflows", headers=h).json())
    assert client.post(_base(wid) + "/workflows", headers=h,
                       json={"key": "alerts", "name": "dup"}).status_code == 409
    assert client.post(_base(wid) + "/workflows", headers=h,
                       json={"key": "x", "name": "x", "channel": "carrier-pigeon"}).status_code == 422


def test_nv017_templates_instantiate_real_workflows(client, db_session):
    wid, h = _ctx(client)
    templates = client.get(_base(wid) + "/templates", headers=h).json()
    assert templates and all("clean-room" in t["provenance"] for t in templates)
    security = client.post(_base(wid) + "/templates/security-alert/instantiate", headers=h,
                           json={"name": "Security"}).json()
    assert security["severity"] == "critical" and security["critical"] is True
    assert security["template_key"] == "security-alert"
    digest = client.post(_base(wid) + "/templates/weekly-digest/instantiate", headers=h,
                         json={}).json()
    assert digest["digest_rule"]["frequency"] == "weekly"
    assert client.post(_base(wid) + "/templates/nope/instantiate", headers=h,
                       json={}).status_code == 404
    event = db_session.execute(
        select(Event).where(
            Event.workspace_id == wid,
            Event.event_type == "notification.workflow_created",
        )
    ).scalars().first()
    assert event is not None and event.payload["channel_delivery_claimed"] is False


def test_nv019_critical_flows_cannot_be_muted_by_preference(client):
    wid, h = _ctx(client)
    critical = _workflow(client, wid, h, "critical-flow", severity="critical", critical=True)
    normal = _workflow(client, wid, h, "normal-flow")

    url = f"{_base(wid)}/workflows/{critical['id']}/effective-enabled"
    result = client.post(url, headers=h, json={"subscriber_disabled": True}).json()
    assert result["enabled"] is True and result["source"] == "critical-policy"

    result2 = client.post(f"{_base(wid)}/workflows/{normal['id']}/effective-enabled",
                          headers=h, json={"subscriber_disabled": True}).json()
    assert result2["enabled"] is False and result2["source"] == "subscriber-preference"

    blocked = client.post(f"{_base(wid)}/workflows/{critical['id']}/disable", headers=h,
                          json={"reason": "subscriber_preference"})
    assert blocked.status_code == 409
    assert client.post(f"{_base(wid)}/workflows/{critical['id']}/disable", headers=h,
                       json={"reason": "workspace-policy"}).status_code == 200


def test_nv028_trigger_overrides_are_scoped_and_cannot_inject_secrets(client):
    wid, h = _ctx(client)
    wf = _workflow(client, wid, h, "override-flow", feed_key="alerts")
    msg = _trigger(client, wid, h, wf["id"], overrides={
        "provider": "email", "headers": {"X-Trace": "abc"}, "payload": {"variant": "b"},
    })
    assert msg["overrides"]["provider"] == "email"
    assert msg["overrides"]["headers"] == {"X-Trace": "abc"}

    after = [w for w in client.get(_base(wid) + "/workflows", headers=h).json()
             if w["id"] == wf["id"]][0]
    assert "overrides" not in after and after["feed_key"] == "alerts"

    bad = client.post(f"{_base(wid)}/workflows/{wf['id']}/trigger", headers=h,
                      json={"title": "x", "overrides": {"headers": {"Authorization": "Bearer leak"}}})
    assert bad.status_code == 422
    bad2 = client.post(f"{_base(wid)}/workflows/{wf['id']}/trigger", headers=h,
                       json={"title": "x", "overrides": {"provider": "carrier-pigeon"}})
    assert bad2.status_code == 422


def test_nv013_digest_fires_once_per_window_even_with_many_or_zero_events(client):
    wid, h = _ctx(client)
    wf = client.post(_base(wid) + "/templates/weekly-digest/instantiate", headers=h,
                     json={}).json()
    for i in range(3):
        _trigger(client, wid, h, wf["id"], title=f"Event {i}", window_key="2026-11-23")
    payload = {"workflow_id": wf["id"], "window_key": "2026-11-23"}
    first = client.post(_base(wid) + "/digest/evaluate", headers=h, json=payload).json()
    second = client.post(_base(wid) + "/digest/evaluate", headers=h, json=payload).json()
    assert first["id"] == second["id"]
    assert first["event_count"] == 3
    digests = [m for m in client.get(_base(wid) + "/messages", headers=h).json()
               if m["kind"] == "digest"]
    assert len(digests) == 1
    empty = client.post(_base(wid) + "/digest/evaluate", headers=h,
                        json={"workflow_id": wf["id"], "window_key": "2026-11-24"}).json()
    assert empty["event_count"] == 0 and empty["id"] != first["id"]


def test_nv038_quiet_hours_hold_or_skip(client):
    wid, h = _ctx(client)
    wf = _workflow(client, wid, h, "quiet-flow", delivery_window={
        "start": "09:00", "end": "17:00", "policy": "hold", "timezone": "Asia/Kolkata",
    })
    held = _trigger(client, wid, h, wf["id"], local_time="2026-11-23T02:00:00")
    assert held["status"] == "held"
    skipped_wf = client.patch(f"{_base(wid)}/workflows/{wf['id']}", headers=h,
                              json={"delivery_window": {
                                  "start": "09:00", "end": "17:00", "policy": "skip",
                                  "timezone": "Asia/Kolkata",
                              }}).json()
    assert skipped_wf["delivery_window"]["policy"] == "skip"
    assert _trigger(client, wid, h, wf["id"], local_time="2026-11-23T02:00:00")["status"] == "skipped"
    assert _trigger(client, wid, h, wf["id"], local_time="2026-11-23T11:00:00")["status"] == "delivered"


def test_nv036_inbox_tabs_and_filters_use_stored_fields(client):
    wid, h = _ctx(client)
    sec = _workflow(client, wid, h, "sec", severity="critical", tags=["security"])
    bil = _workflow(client, wid, h, "bil", severity="info", tags=["billing"])
    _trigger(client, wid, h, sec["id"], title="Security event")
    _trigger(client, wid, h, bil["id"], title="Invoice event")
    assert len(client.get(_base(wid) + "/messages", headers=h,
                          params={"tag": "security"}).json()) == 1
    assert len(client.get(_base(wid) + "/messages", headers=h,
                          params={"category": "info"}).json()) == 1
    assert len(client.get(_base(wid) + "/messages", headers=h,
                          params={"unread": "true"}).json()) == 2
    msg = client.get(_base(wid) + "/messages", headers=h, params={"tag": "security"}).json()[0]
    client.patch(f"{_base(wid)}/messages/{msg['id']}/read", headers=h, json={"read": True})
    assert len(client.get(_base(wid) + "/messages", headers=h,
                          params={"unread": "true"}).json()) == 1


def test_nv040_rich_content_is_sanitised_and_custom_fields_render(client):
    wid, h = _ctx(client)
    wf = _workflow(client, wid, h, "rich-flow")
    msg = _trigger(client, wid, h, wf["id"],
                   html="<script>steal()</script><b onclick='x()'>Order</b><iframe src='x'></iframe>",
                   data={"order_id": "NV-42", "amount": "10"})
    assert "<script" not in msg["html_body"].lower()
    assert "onclick" not in msg["html_body"].lower()
    assert "iframe" not in msg["html_body"].lower()
    assert "<b>Order</b>" in msg["html_body"]
    assert msg["data"]["order_id"] == "NV-42"


def test_nv044_notification_actions_only_open_authorised_local_routes(client):
    wid, h = _ctx(client)
    wf = _workflow(client, wid, h, "action-flow")
    good = _trigger(client, wid, h, wf["id"], action_url="#/contacts/123")
    out = client.post(f"{_base(wid)}/messages/{good['id']}/action", headers=h).json()
    assert out["authorised"] is True and out["route"] == "#/contacts/123"
    for hostile in ("https://evil.example", "javascript:alert(1)", "#/../../evil", "//evil"):
        assert client.post(f"{_base(wid)}/workflows/{wf['id']}/trigger", headers=h,
                           json={"title": "x", "action_url": hostile}).status_code == 422


def test_nv086_feeds_isolate_stored_messages(client):
    wid, h = _ctx(client)
    for key in ("alerts", "billing"):
        assert client.post(_base(wid) + "/feeds", headers=h,
                           json={"key": key, "name": key.title()}).status_code == 201
    a = _workflow(client, wid, h, "a", feed_key="alerts")
    b = _workflow(client, wid, h, "b", feed_key="billing")
    _trigger(client, wid, h, a["id"], title="A message")
    _trigger(client, wid, h, b["id"], title="B message")
    feed_a = client.get(_base(wid) + "/messages", headers=h, params={"feed": "alerts"}).json()
    assert len(feed_a) == 1 and feed_a[0]["title"] == "A message"
    assert len(client.get(_base(wid) + "/messages", headers=h,
                          params={"feed": "billing"}).json()) == 1
    assert client.post(_base(wid) + "/feeds", headers=h,
                       json={"key": "alerts", "name": "dup"}).status_code == 409


def test_nv073_contexts_isolate_inbox_and_preference_state(client):
    wid, h = _ctx(client)
    for key in ("tenant-a", "tenant-b"):
        assert client.post(_base(wid) + "/contexts", headers=h,
                           json={"key": key, "name": key}).status_code == 201
    a = _workflow(client, wid, h, "ca", context_key="tenant-a")
    b = _workflow(client, wid, h, "cb", context_key="tenant-b")
    _trigger(client, wid, h, a["id"], title="Tenant A")
    _trigger(client, wid, h, b["id"], title="Tenant B")
    assert len(client.get(_base(wid) + "/messages", headers=h,
                          params={"context": "tenant-a"}).json()) == 1
    summary = client.get(_base(wid) + "/contexts/tenant-a/summary", headers=h).json()
    assert summary["message_count"] == 1
    assert client.get(_base(wid) + "/contexts/tenant-b/summary", headers=h).json()["message_count"] == 1


def test_nv087_layouts_render_without_script_injection(client):
    wid, h = _ctx(client)
    created = client.post(_base(wid) + "/layouts", headers=h,
                          json={"key": "brand", "name": "Brand",
                                "body": "<section><script>bad()</script>{{content}}</section>"})
    assert created.status_code == 201
    layout = created.json()
    assert "<script" not in layout["body"].lower()
    wf = _workflow(client, wid, h, "layout-flow", layout_key="brand")
    assert wf["layout_key"] == "brand"
    rendered = client.post(_base(wid) + "/layouts/render", headers=h,
                           json={"layout_id": layout["id"],
                                 "content_html": "<img src=x onerror=evil()><b>Hi</b>"}).json()
    assert rendered["script_free"] is True
    assert "onerror" not in rendered["rendered"].lower()
    assert "<b>Hi</b>" in rendered["rendered"]
    assert "{{content}}" not in rendered["rendered"]


def test_nv054_webhook_endpoints_registry_and_ssrf_controls(client):
    wid, h = _ctx(client)
    created = client.post(_base(wid) + "/webhooks/endpoints", headers=h,
                          json={"name": "local", "url": "/api/hooks/local",
                                "event_types": ["workflow.created"]})
    assert created.status_code == 201, created.text
    endpoint = created.json()
    assert client.post(_base(wid) + "/webhooks/endpoints", headers=h,
                       json={"name": "local", "url": "/api/hooks/local"}).status_code == 409
    for hostile in ("https://evil.example/hook", "http://user:pass@127.0.0.1/x", "ftp://x/y"):
        assert client.post(_base(wid) + "/webhooks/endpoints", headers=h,
                           json={"name": "bad" + hostile[:5], "url": hostile}).status_code == 422
    dispatched = client.post(f"{_base(wid)}/webhooks/endpoints/{endpoint['id']}/dispatch", headers=h,
                             json={"event_type": "workflow.created", "payload": {"id": "w1"}})
    assert dispatched.status_code == 201, dispatched.text
    body = dispatched.json()
    assert body["signature"].startswith("sha256=")
    assert "one_time_secret" in body and "secret" not in body["payload"]
    deliveries = client.get(_base(wid) + "/webhooks/deliveries", headers=h).json()
    assert len(deliveries) == 1
    assert deliveries[0]["signature_prefix"] == body["signature"][:16]
    assert "one_time_secret" not in deliveries[0]


def test_nv056_signature_tamper_replay_and_failed_recovery(client, db_session):
    wid, h = _ctx(client)
    endpoint = client.post(_base(wid) + "/webhooks/endpoints", headers=h,
                           json={"name": "signed", "url": "http://127.0.0.1:9000/hook"}).json()
    good = client.post(f"{_base(wid)}/webhooks/endpoints/{endpoint['id']}/dispatch", headers=h,
                       json={"event_type": "message.created", "payload": {"n": 1}}).json()
    raw = "message.created." + __import__("json").dumps({"n": 1}, sort_keys=True)
    secret = good["one_time_secret"]
    assert client.post(_base(wid) + "/webhooks/verify", headers=h,
                       json={"raw_body": raw, "signature": good["signature"],
                             "secret": secret, "nonce": "n1"}).json()["valid"] is True
    bad = client.post(_base(wid) + "/webhooks/verify", headers=h,
                      json={"raw_body": raw + " ", "signature": good["signature"],
                            "secret": secret, "nonce": "n2"}).json()
    assert bad["valid"] is False and bad["reason"] == "bad_signature"
    replay = client.post(_base(wid) + "/webhooks/verify", headers=h,
                         json={"raw_body": raw, "signature": good["signature"],
                               "secret": secret, "nonce": "n1"}).json()
    assert replay["valid"] is False and replay["reason"] == "replay"

    failed = client.post(f"{_base(wid)}/webhooks/endpoints/{endpoint['id']}/dispatch", headers=h,
                         json={"event_type": "message.created", "payload": {"n": 2},
                               "force_status": "failed"}).json()
    first = client.post(f"{_base(wid)}/webhooks/deliveries/{failed['id']}/replay", headers=h)
    assert first.status_code == 200 and first.json()["attempts"] == 2
    assert first.json()["replayed"] is True
    assert client.post(f"{_base(wid)}/webhooks/deliveries/{failed['id']}/replay",
                       headers=h).status_code == 409
    assert client.post(f"{_base(wid)}/webhooks/deliveries/{good['id']}/replay",
                       headers=h).status_code == 409


def test_nv071_api_keys_are_hashed_rotated_and_revoked(client, db_session):
    wid, h = _ctx(client)
    issued = client.post(KEYS.format(wid=wid), headers=h,
                         json={"name": "notifier", "scopes": ["contact:read"]}).json()
    secret = issued["secret"]
    row = db_session.execute(select(ApiKey).where(ApiKey.id == issued["id"])).scalar_one()
    assert row.secret_hash == hash_token(secret) and row.secret_hash != secret
    assert client.get(CONTACTS.format(wid=wid), headers={"X-API-Key": secret}).status_code == 200

    rotated = client.post(KEYS.format(wid=wid) + f"/{issued['id']}/rotate", headers=h,
                          json={}).json()
    assert client.get(CONTACTS.format(wid=wid), headers={"X-API-Key": secret}).status_code == 401
    assert client.get(CONTACTS.format(wid=wid),
                      headers={"X-API-Key": rotated["secret"]}).status_code == 200
    client.delete(KEYS.format(wid=wid) + f"/{issued['id']}", headers=h)
    assert client.get(CONTACTS.format(wid=wid),
                      headers={"X-API-Key": rotated["secret"]}).status_code == 401


def test_notification_workflows_workspace_isolation(client):
    wid, h = _ctx(client)
    wf = _workflow(client, wid, h, "secret-flow")
    _trigger(client, wid, h, wf["id"], title="Secret")
    client.post(_base(wid) + "/feeds", headers=h, json={"key": "secret", "name": "Secret"})
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh, owid = auth(other["access_token"]), other["workspace_id"]
    assert client.get(_base(owid) + "/workflows", headers=oh).json() == []
    assert client.get(_base(owid) + "/messages", headers=oh).json() == []
    assert client.get(_base(owid) + "/feeds", headers=oh).json() == []
    assert client.post(f"{_base(owid)}/workflows/{wf['id']}/trigger", headers=oh,
                       json={"title": "x"}).status_code == 404
