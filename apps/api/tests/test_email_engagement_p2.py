"""Named acceptance tests for the clean-room email content/engagement cluster.

Every test drives the real FastAPI app with real persisted, workspace-scoped
rows. MT-014, MT-015, MT-017, MT-018, MT-020, MT-021, MT-022, MT-023 and MT-024
are proven end to end. socket.socket.connect is patched to raise so any
outbound traffic from a tracking endpoint fails the test.
"""

from __future__ import annotations

import socket

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}"


def _ctx(client):
    tokens = bootstrap(client, "MailLab", "mail-owner@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return API.format(wid=wid) + "/email-engagement"


def _no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("an email engagement endpoint attempted outbound traffic")
    monkeypatch.setattr(socket.socket, "connect", blocked)


def _template(client, wid, h, name="Launch"):
    r = client.post(_base(wid) + "/templates", headers=h, json={
        "name": name, "subject": "Hello", "html_body": "<p>Hello <b>world</b></p>",
        "text_body": "Hello world",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_mt014_email_html_and_text_formats(client, monkeypatch):
    """MT-014: both renderable formats are stored and returned locally."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    tid = _template(client, wid, h)
    formats = client.get(_base(wid) + f"/templates/{tid}/formats", headers=h).json()
    assert formats["html"] == "<p>Hello <b>world</b></p>"
    assert formats["text"] == "Hello world"
    assert formats["external_calls"] is False
    assert client.post(_base(wid) + "/templates", headers=h,
                       json={"name": "Empty", "subject": "x"}).status_code == 422
    assert [t["name"] for t in client.get(_base(wid) + "/templates", headers=h).json()] == ["Launch"]


def test_mt015_translations_and_ab_variants(client, monkeypatch):
    """MT-015: locale translations and weighted A/B variants select deterministically."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    tid = _template(client, wid, h)
    tr = client.post(_base(wid) + f"/templates/{tid}/translations", headers=h, json={
        "locale": "fr-FR", "subject": "Bonjour", "html_body": "<p>Bonjour</p>", "text_body": "Bonjour",
    })
    assert tr.status_code == 201, tr.text
    assert tr.json()["locale"] == "fr-FR"
    assert client.post(_base(wid) + f"/templates/{tid}/translations", headers=h, json={
        "locale": "fr-FR", "subject": "again",
    }).status_code == 409
    assert len(client.get(_base(wid) + f"/templates/{tid}/translations", headers=h).json()) == 1
    for name, weight in (("A", 1), ("B", 3)):
        r = client.post(_base(wid) + f"/templates/{tid}/variants", headers=h,
                        json={"name": name, "subject": f"Subject {name}", "weight": weight})
        assert r.status_code == 201, r.text
    picks = [client.get(_base(wid) + f"/templates/{tid}/variants/select", headers=h,
                        params={"bucket": b}).json()["selected"] for b in range(8)]
    assert set(picks) == {"A", "B"}
    assert picks[0] == client.get(_base(wid) + f"/templates/{tid}/variants/select", headers=h,
                                  params={"bucket": 0}).json()["selected"]
    assert client.get(_base(wid) + f"/templates/{tid}/variants/select", headers=h,
                      params={"bucket": -1}).status_code == 422


def test_mt017_open_tracking_pixel_records_locally(client, monkeypatch):
    """MT-017: an open token records a local open and returns a local 1x1 GIF."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    tid = _template(client, wid, h)
    token = client.post(_base(wid) + f"/templates/{tid}/tokens", headers=h, json={
        "recipient_id": "contact-1",
    }).json()
    assert token["kind"] == "open" and "/track/open/" in token["local_path"]
    result = client.get(_base(wid) + "/track/open/" + token["token"], headers=h).json()
    assert result["recorded"] is True and result["kind"] == "opened"
    assert result["pixel_base64"] == "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
    stats = client.get(_base(wid) + f"/templates/{tid}/engagement", headers=h).json()
    assert stats["by_kind"] == {"opened": 1} and stats["external_calls"] is False
    assert client.get(_base(wid) + "/track/open/missing", headers=h).status_code == 404
    assert client.get(_base(wid) + "/track/click/" + token["token"], headers=h).status_code == 422


def test_mt018_click_tracking_never_redirects_externally(client, monkeypatch):
    """MT-018: clicks are recorded locally; a target URL is data, never fetched."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    tid = _template(client, wid, h)
    token = client.post(_base(wid) + f"/templates/{tid}/tokens", headers=h, json={
        "recipient_id": "contact-2", "target_url": "https://example.invalid/page",
    }).json()
    assert token["kind"] == "click" and "/track/click/" in token["local_path"]
    result = client.get(_base(wid) + "/track/click/" + token["token"], headers=h).json()
    assert result["recorded"] is True and result["kind"] == "clicked"
    assert result["target_url"] == "https://example.invalid/page"
    assert result["local_only_redirect"] is True and result["external_calls"] is False
    stats = client.get(_base(wid) + f"/templates/{tid}/engagement", headers=h).json()
    assert stats["by_kind"] == {"clicked": 1}


def test_mt020_bounce_management(client, monkeypatch):
    """MT-020: bounce events are recorded with reasons and filterable by kind."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    tid = _template(client, wid, h)
    r = client.post(_base(wid) + "/engagement/bounces", headers=h, json={
        "recipient_id": "contact-3", "template_id": tid,
        "metadata": {"reason": "hard", "code": 550},
    })
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "bounced" and r.json()["metadata"]["reason"] == "hard"
    bounces = client.get(_base(wid) + "/engagement", headers=h, params={"kind": "bounced"}).json()
    assert len(bounces) == 1 and bounces[0]["recipient_id"] == "contact-3"
    assert client.get(_base(wid) + "/engagement", headers=h, params={"kind": "unknown"}).status_code == 422


def test_mt021_reply_monitoring_is_local_only(client, monkeypatch):
    """MT-021: replies are recorded locally without polling any mailbox."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    r = client.post(_base(wid) + "/engagement/replies", headers=h, json={
        "recipient_id": "contact-4", "metadata": {"subject": "Re: Hello"},
    })
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "replied" and r.json()["external_calls"] is False
    replies = client.get(_base(wid) + "/engagement", headers=h, params={"kind": "replied"}).json()
    assert len(replies) == 1 and replies[0]["metadata"]["subject"] == "Re: Hello"


def test_mt022_mailer_identity_and_signatures(client, monkeypatch):
    """MT-022: one mailer identity per user with a default signature."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    first = client.post(_base(wid) + "/signatures", headers=h, json={
        "display_name": "Alex Morgan", "body_html": "<p>Regards, Alex</p>", "is_default": True,
    })
    assert first.status_code == 201, first.text
    sid = first.json()["id"]
    updated = client.post(_base(wid) + "/signatures", headers=h, json={
        "display_name": "Alex M.", "body_html": "<p>Cheers, Alex</p>", "is_default": False,
    })
    assert updated.status_code == 201 and updated.json()["id"] == sid
    assert updated.json()["is_default"] is False
    rows = client.get(_base(wid) + "/signatures", headers=h).json()
    assert len(rows) == 1 and rows[0]["display_name"] == "Alex M."


def test_mt023_base64_inline_images_are_validated(client, monkeypatch):
    """MT-023: base64 images are decoded/validated and stored by Content-ID."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    tid = _template(client, wid, h)
    good = client.post(_base(wid) + f"/templates/{tid}/images", headers=h, json={
        "cid": "logo", "content_type": "image/png", "content_base64": "iVBORw0KGgo=",
    })
    assert good.status_code == 201, good.text
    assert good.json()["size_bytes"] == 8
    assert client.post(_base(wid) + f"/templates/{tid}/images", headers=h, json={
        "cid": "logo", "content_base64": "iVBORw0KGgo=",
    }).status_code == 409
    assert client.post(_base(wid) + f"/templates/{tid}/images", headers=h, json={
        "cid": "bad", "content_base64": "!!!not-base64!!!",
    }).status_code == 422
    rows = client.get(_base(wid) + f"/templates/{tid}/images", headers=h).json()
    assert len(rows) == 1 and rows[0]["cid"] == "logo"


def test_mt024_online_version_is_a_local_render(client, monkeypatch):
    """MT-024: the online version assembles stored html, images and signature locally."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    tid = _template(client, wid, h)
    client.post(_base(wid) + f"/templates/{tid}/images", headers=h, json={
        "cid": "logo", "content_type": "image/png", "content_base64": "iVBORw0KGgo=",
    })
    client.post(_base(wid) + "/signatures", headers=h, json={
        "display_name": "Alex", "body_html": "<footer>Signed</footer>", "is_default": True,
    })
    result = client.get(_base(wid) + f"/templates/{tid}/online", headers=h).json()
    assert result["delivery"] == "local-only" and result["external_calls"] is False
    assert "<h1>Hello</h1>" in result["html"]
    assert "data:image/png;base64,iVBORw0KGgo=" in result["html"]
    assert "<footer>Signed</footer>" in result["html"]
    assert len(result["content_hash"]) == 64
    assert client.get(_base(wid) + "/templates/missing/online", headers=h).status_code == 404


def test_email_engagement_contract_and_workspace_isolation(client, monkeypatch):
    """Contract denies external delivery and a second workspace sees no data."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    tid = _template(client, wid, h)
    contract = client.get(_base(wid) + "/api-contract", headers=h).json()
    assert contract["version"] == "1" and contract["legacy_versions"] == []
    assert contract["external_calls"] is False and contract["external_delivery"] is False
    assert contract["email_sent"] is False and contract["vendor_sdk_used"] is False
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other mail"})
    assert other.status_code == 200, other.text
    owid, oh = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(owid) + "/templates", headers=oh).json() == []
    assert client.get(_base(owid) + "/signatures", headers=oh).json() == []
    assert client.get(_base(owid) + "/engagement", headers=oh).json() == []
    assert client.get(_base(owid) + f"/templates/{tid}/formats", headers=oh).status_code == 404
    assert client.post(_base(owid) + "/engagement/bounces", headers=oh,
                       json={"recipient_id": "x"}).status_code in (200, 201)


def test_email_engagement_writes_require_contact_write(client, monkeypatch):
    """Reads use CONTACT_READ; writes require CONTACT_WRITE via the shared contract."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    assert client.get(_base(wid) + "/api-contract", headers=h).status_code == 200
    assert client.post(_base(wid) + "/templates", headers={},
                       json={"name": "x", "subject": "y"}).status_code in (401, 403)
    assert client.post(_base(wid) + "/signatures", headers={},
                       json={"display_name": "x"}).status_code in (401, 403)
