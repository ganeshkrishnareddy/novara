"""Named acceptance tests for the clean-room marketing content cluster.

Every test drives the real FastAPI app with real persisted, workspace-scoped
rows. MT-009, MT-029, MT-031, MT-032, MT-036, MT-037 and MT-048 are proven end
to end. socket.socket.connect is patched to raise so any outbound traffic from
a content endpoint fails the test.
"""

from __future__ import annotations

import socket

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}"


def _ctx(client):
    tokens = bootstrap(client, "ContentLab", "content-owner@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return API.format(wid=wid) + "/marketing-content"


def _no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("a marketing content endpoint attempted outbound traffic")
    monkeypatch.setattr(socket.socket, "connect", blocked)


def test_mt009_visitor_and_known_contact_types(client, monkeypatch):
    """MT-009: contacts are typed visitor/known and can be identified locally."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = client.post(_base(wid) + "/contact-types", headers=h, json={
        "contact_id": "c1", "kind": "visitor",
    })
    assert created.status_code == 201, created.text
    assert created.json()["kind"] == "visitor"
    assert created.json()["identified_at"] is None
    assert client.post(_base(wid) + "/contact-types", headers=h, json={
        "contact_id": "c1", "kind": "visitor",
    }).status_code == 409
    assert client.post(_base(wid) + "/contact-types", headers=h, json={
        "contact_id": "bad", "kind": "robot",
    }).status_code == 422
    identified = client.post(_base(wid) + "/contact-types/c1/identify", headers=h,
                             json={"details": {"email": "c1@example.com"}})
    assert identified.status_code == 200, identified.text
    assert identified.json()["kind"] == "known"
    assert identified.json()["identified_at"] is not None
    assert client.post(_base(wid) + "/contact-types/c1/identify", headers=h,
                       json={}).status_code == 409
    row = client.get(_base(wid) + "/contact-types/c1", headers=h).json()
    assert row["details"]["email"] == "c1@example.com"
    assert client.get(_base(wid) + "/contact-types/missing", headers=h).status_code == 404


def test_mt029_landing_pages_render_and_publish_locally(client, monkeypatch):
    """MT-029: landing pages are local renders with a unique slug and local publish URL."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = client.post(_base(wid) + "/landing-pages", headers=h, json={
        "name": "Launch", "slug": "launch", "html_body": "<h1>Welcome</h1>",
    })
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    assert created.json()["published"] is False
    assert client.post(_base(wid) + "/landing-pages", headers=h, json={
        "name": "Dup", "slug": "launch",
    }).status_code == 409
    assert client.post(_base(wid) + "/landing-pages", headers=h, json={
        "name": "Bad", "slug": "has spaces",
    }).status_code == 422
    preview = client.get(_base(wid) + f"/landing-pages/{pid}/preview", headers=h).json()
    assert preview["html"] == "<h1>Welcome</h1>"
    assert preview["delivery"] == "local-only" and preview["external_calls"] is False
    published = client.put(_base(wid) + f"/landing-pages/{pid}/publication", headers=h,
                           json={"published": True})
    assert published.status_code == 200, published.text
    assert published.json()["local_url"] == "/local/lp/launch"
    assert [p["slug"] for p in client.get(_base(wid) + "/landing-pages", headers=h).json()] == ["launch"]
    assert client.get(_base(wid) + "/landing-pages/missing/preview", headers=h).status_code == 404


def test_mt031_progressive_profiling_fields(client, monkeypatch):
    """MT-031: a form returns only the fields still unknown for a contact."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    client.post(_base(wid) + "/contact-types", headers=h, json={
        "contact_id": "known-1", "kind": "known", "details": {"email": "a@b.c"},
    })
    form = client.post(_base(wid) + "/forms", headers=h, json={
        "name": "Signup", "fields": ["email", "phone", "company"],
    })
    assert form.status_code == 201, form.text
    fid = form.json()["id"]
    assert client.post(_base(wid) + "/forms", headers=h, json={
        "name": "Dup fields", "fields": ["a", "a"],
    }).status_code == 422
    pending = client.get(_base(wid) + f"/forms/{fid}/progressive-fields", headers=h,
                         params={"contact_id": "known-1"}).json()
    assert pending["pending_fields"] == ["phone", "company"]
    assert pending["progressive"] is True
    fresh = client.get(_base(wid) + f"/forms/{fid}/progressive-fields", headers=h,
                       params={"contact_id": "new-visitor"}).json()
    assert fresh["pending_fields"] == ["email", "phone", "company"]


def test_mt032_form_submit_actions_are_local_effects(client, monkeypatch):
    """MT-032: submit actions are recorded as local effects; no delivery occurs."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    form = client.post(_base(wid) + "/forms", headers=h, json={
        "name": "Contact", "fields": ["email", "company"],
    }).json()
    fid = form["id"]
    assert client.post(_base(wid) + f"/forms/{fid}/submit", headers=h, json={
        "contact_id": "c2", "answers": {"unknown": "x"}, "actions": ["tag"],
    }).status_code == 422
    assert client.post(_base(wid) + f"/forms/{fid}/submit", headers=h, json={
        "contact_id": "c2", "answers": {}, "actions": ["send_email"],
    }).status_code == 422
    result = client.post(_base(wid) + f"/forms/{fid}/submit", headers=h, json={
        "contact_id": "c2", "answers": {"email": "c2@example.com"},
        "actions": ["tag", "notify"],
    })
    assert result.status_code == 201, result.text
    body = result.json()
    assert body["external_calls"] is False and body["delivery"] == "local-only"
    assert [e["action"] for e in body["effects"]] == ["tag", "notify"]
    assert all(e["local_only"] is True for e in body["effects"])
    ctype = client.get(_base(wid) + "/contact-types/c2", headers=h).json()
    assert ctype["kind"] == "visitor" and ctype["details"]["email"] == "c2@example.com"


def test_mt036_dynamic_content_resolves_deterministically(client, monkeypatch):
    """MT-036: segment-field variants resolve deterministically from local attributes."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = client.post(_base(wid) + "/dynamic-content", headers=h, json={
        "name": "Hero", "segment_field": "plan",
        "variants": {"default": "Hello", "vip": "Welcome VIP"},
    })
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    assert created.json()["variants"] == ["default", "vip"]
    assert client.post(_base(wid) + "/dynamic-content", headers=h, json={
        "name": "Empty", "segment_field": "plan", "variants": {},
    }).status_code == 422
    vip = client.post(_base(wid) + f"/dynamic-content/{cid}/resolve", headers=h,
                      json={"attributes": {"plan": "vip"}}).json()
    assert vip["variant"] == "vip" and vip["content"] == "Welcome VIP"
    assert vip["deterministic"] is True
    default = client.post(_base(wid) + f"/dynamic-content/{cid}/resolve", headers=h,
                          json={"attributes": {"plan": "unknown"}}).json()
    assert default["variant"] == "default"
    assert client.post(_base(wid) + "/dynamic-content/missing/resolve", headers=h,
                       json={}).status_code == 404


def test_mt037_asset_bundle_validates_base64(client, monkeypatch):
    """MT-037: asset bundles are stored locally with validated base64 payloads."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = client.post(_base(wid) + "/assets", headers=h, json={
        "name": "logo.png", "content_type": "image/png", "content_base64": "iVBORw0KGgo=",
    })
    assert created.status_code == 201, created.text
    assert created.json()["size_bytes"] == 8 and len(created.json()["content_hash"]) == 64
    assert client.post(_base(wid) + "/assets", headers=h, json={
        "name": "bad", "content_base64": "!!!not-base64!!!",
    }).status_code == 422
    rows = client.get(_base(wid) + "/assets", headers=h).json()
    assert len(rows) == 1 and rows[0]["name"] == "logo.png"


def test_mt048_dashboard_bundle_aggregates_local_rows(client, monkeypatch):
    """MT-048: dashboard widgets aggregate only locally recorded rows."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    client.post(_base(wid) + "/contact-types", headers=h, json={"contact_id": "a", "kind": "visitor"})
    client.post(_base(wid) + "/contact-types", headers=h, json={"contact_id": "b", "kind": "known"})
    client.post(_base(wid) + "/landing-pages", headers=h, json={"name": "LP", "slug": "lp"})
    counter = client.post(_base(wid) + "/dashboard-widgets", headers=h, json={
        "name": "Pages", "widget_type": "counter", "config": {"source": "landing_pages"},
    })
    assert counter.status_code == 201, counter.text
    breakdown = client.post(_base(wid) + "/dashboard-widgets", headers=h, json={
        "name": "Contacts", "widget_type": "breakdown", "config": {},
    })
    assert breakdown.status_code == 201, breakdown.text
    assert client.post(_base(wid) + "/dashboard-widgets", headers=h, json={
        "name": "Bad", "widget_type": "pie",
    }).status_code == 422
    assert client.post(_base(wid) + "/dashboard-widgets", headers=h, json={
        "name": "Pages", "widget_type": "counter",
    }).status_code == 409
    dash = client.get(_base(wid) + "/dashboard", headers=h).json()
    assert dash["source"] == "local-records-only" and dash["external_calls"] is False
    values = {w["name"]: w["value"] for w in dash["widgets"]}
    assert values["Pages"] == 1
    assert values["Contacts"] == {"visitor": 1, "known": 1}


def test_marketing_content_contract_and_workspace_isolation(client, monkeypatch):
    """Contract denies external delivery and a second workspace sees no content."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    client.post(_base(wid) + "/landing-pages", headers=h, json={"name": "LP", "slug": "lp"})
    contract = client.get(_base(wid) + "/api-contract", headers=h).json()
    assert contract["version"] == "1" and contract["legacy_versions"] == []
    assert contract["external_calls"] is False and contract["external_delivery"] is False
    assert contract["email_sent"] is False and contract["sms_sent"] is False
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other content"})
    assert other.status_code == 200, other.text
    owid, oh = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(owid) + "/landing-pages", headers=oh).json() == []
    assert client.get(_base(owid) + "/assets", headers=oh).json() == []
    assert client.get(_base(owid) + "/dashboard", headers=oh).json()["widgets"] == []
    assert client.get(_base(owid) + "/contact-types/a", headers=oh).status_code == 404


def test_marketing_content_writes_require_contact_write(client, monkeypatch):
    """Reads use CONTACT_READ; unauthenticated writes are refused."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    assert client.get(_base(wid) + "/api-contract", headers=h).status_code == 200
    assert client.post(_base(wid) + "/landing-pages", headers={},
                       json={"name": "x", "slug": "x"}).status_code in (401, 403)
    assert client.post(_base(wid) + "/assets", headers={},
                       json={"name": "x", "content_base64": "aGVsbG8="}).status_code in (401, 403)
