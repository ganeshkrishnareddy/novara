"""Clean-room P2 Papermark share-link presentation acceptance tests.

Named rows: PM-023, PM-035, PM-036, PM-037, PM-043, PM-044, PM-046, PM-071.
No upstream source copied. No external service contacted.
"""

from __future__ import annotations

import socket

import pytest

from novara_core.main import app
from novara_core.models import new_id

from .conftest import auth, bootstrap

MEMBER_EMAIL = "slp-member@example.com"


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in clean-room P2 acceptance tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


def _has_prefix(routes, prefix: str) -> bool:
    for route in routes:
        if getattr(route, "path", "").startswith(prefix):
            return True
        nested = getattr(route, "original_router", None)
        if nested is not None and _has_prefix(nested.routes, prefix):
            return True
    return False


@pytest.fixture(scope="module", autouse=True)
def _attach_share_link_router():
    prefix = "/api/v1/workspaces/{workspace_id}/share-links"
    if _has_prefix(app.routes, prefix):
        yield
        return
    from novara_core.modules import share_link_presentation

    original = list(app.routes)
    app.include_router(share_link_presentation.router)
    try:
        yield
    finally:
        app.routes[:] = original
        app.router._mark_routes_changed()


def _setup(client):
    owner = bootstrap(client, email="slp-owner@example.com", workspace_name="SLP WS")
    ws = owner["workspace_id"]
    other = client.post("/api/v1/workspaces", headers=auth(owner["access_token"]),
                        json={"name": "Other SLP"})
    assert other.status_code == 200, other.text
    return {
        "ws": ws,
        "h": auth(owner["access_token"]),
        "other_ws": other.json()["workspace_id"],
        "h_other": auth(other.json()["access_token"]),
    }


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/share-links"


def _document(db, ctx, title):
    from novara_core.modules.documents import Document

    row = Document(
        id=new_id(), workspace_id=ctx["ws"], title=title, doc_type="pdf",
        size_bytes=1024, storage_path=f"local://opaque/{new_id()}",
        uploaded_by="slp-owner",
    )
    db.add(row)
    db.commit()
    return row.id


def _link(client, ctx, document_id):
    response = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/documents/{document_id}/links",
        headers=ctx["h"], json={},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _room(client, ctx, name):
    response = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms",
        headers=ctx["h"], json={"name": name, "description": "clean-room room"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _register_and_verify_domain(client, ctx, domain="links.example.com"):
    registered = client.post(_base(ctx) + "/domains", headers=ctx["h"], json={"domain": domain})
    assert registered.status_code == 201, registered.text
    body = registered.json()
    verified = client.post(_base(ctx) + "/domains/verify", headers=ctx["h"], json={
        "domain": domain, "token": body["verification_token"],
    })
    assert verified.status_code == 200, verified.text
    return body


def test_pm023_multi_file_share_respects_per_item_visibility(client, db_session):
    """PM-023: a multi-file share link returns only documents marked visible."""
    ctx = _setup(client)
    shown = _document(db_session, ctx, "Public file")
    hidden = _document(db_session, ctx, "Hidden file")

    created = client.post(_base(ctx) + "/share-sets", headers=ctx["h"],
                          json={"name": "Deal set", "slug": "deal-set"})
    assert created.status_code == 201, created.text
    set_id = created.json()["id"]

    for doc_id in (shown, hidden):
        added = client.post(_base(ctx) + f"/share-sets/{set_id}/items", headers=ctx["h"],
                            json={"document_id": doc_id, "visible": True})
        assert added.status_code == 201, added.text

    resolved = client.get(_base(ctx) + "/public/sets/deal-set").json()
    assert {d["id"] for d in resolved["documents"]} == {shown, hidden}

    hide = client.patch(_base(ctx) + f"/share-sets/{set_id}/items/{hidden}",
                        headers=ctx["h"], json={"visible": False})
    assert hide.status_code == 200 and hide.json()["visible"] is False
    resolved = client.get(_base(ctx) + "/public/sets/deal-set").json()
    assert [d["id"] for d in resolved["documents"]] == [shown]
    assert all("Hidden" not in d["title"] for d in resolved["documents"])

    assert client.post(_base(ctx) + f"/share-sets/{set_id}/revoke", headers=ctx["h"]).status_code == 200
    assert client.get(_base(ctx) + "/public/sets/deal-set").status_code == 404
    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/share-links/public/sets/deal-set"
    )
    assert cross.status_code == 404, cross.text


def test_pm036_domain_verification_accepts_only_matching_token(client, db_session):
    """PM-036: only the exact matching token can mark a domain verified."""
    ctx = _setup(client)
    registered = client.post(_base(ctx) + "/domains", headers=ctx["h"],
                             json={"domain": "Verify.Example.COM"})
    assert registered.status_code == 201, registered.text
    body = registered.json()
    assert body["domain"] == "verify.example.com" and body["verified"] is False
    assert body["verification_token"]

    wrong = client.post(_base(ctx) + "/domains/verify", headers=ctx["h"], json={
        "domain": "verify.example.com", "token": "not-the-token",
    })
    assert wrong.status_code == 403, wrong.text

    correct = client.post(_base(ctx) + "/domains/verify", headers=ctx["h"], json={
        "domain": "verify.example.com", "token": body["verification_token"],
    })
    assert correct.status_code == 200 and correct.json()["verified"] is True

    unknown = client.post(_base(ctx) + "/domains/verify", headers=ctx["h"], json={
        "domain": "missing.example.com", "token": body["verification_token"],
    })
    assert unknown.status_code == 404, unknown.text
    invalid = client.post(_base(ctx) + "/domains", headers=ctx["h"], json={"domain": "not a domain"})
    assert invalid.status_code == 422, invalid.text


def test_pm035_verified_domain_slug_and_revocation_frees_it(client, db_session):
    """PM-035: unverified domains cannot serve links; revoking a link frees its slug."""
    ctx = _setup(client)
    doc1 = _document(db_session, ctx, "One")
    doc2 = _document(db_session, ctx, "Two")
    link1 = _link(client, ctx, doc1)
    link2 = _link(client, ctx, doc2)

    unverified = client.post(_base(ctx) + "/domains", headers=ctx["h"],
                             json={"domain": "pending.example.com"})
    assert unverified.status_code == 201
    early = client.put(_base(ctx) + f"/links/{link1}/slug", headers=ctx["h"], json={
        "domain": "pending.example.com", "slug": "deal",
    })
    assert early.status_code == 409, early.text

    registered = client.post(_base(ctx) + "/domains", headers=ctx["h"],
                             json={"domain": "files.example.com"})
    token = registered.json()["verification_token"]
    assert client.post(_base(ctx) + "/domains/verify", headers=ctx["h"], json={
        "domain": "files.example.com", "token": token,
    }).status_code == 200

    assigned = client.put(_base(ctx) + f"/links/{link1}/slug", headers=ctx["h"], json={
        "domain": "files.example.com", "slug": "deal",
    })
    assert assigned.status_code == 200, assigned.text
    resolved = client.get(_base(ctx) + "/public/domains/files.example.com/links/deal")
    assert resolved.status_code == 200 and resolved.json()["link_id"] == link1

    conflict = client.put(_base(ctx) + f"/links/{link2}/slug", headers=ctx["h"], json={
        "domain": "files.example.com", "slug": "deal",
    })
    assert conflict.status_code == 409, conflict.text

    revoke = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/documents/links/{link1}/revoke", headers=ctx["h"]
    )
    assert revoke.status_code == 200, revoke.text
    assert client.get(_base(ctx) + "/public/domains/files.example.com/links/deal").status_code == 404

    reuse = client.put(_base(ctx) + f"/links/{link2}/slug", headers=ctx["h"], json={
        "domain": "files.example.com", "slug": "deal",
    })
    assert reuse.status_code == 200, reuse.text
    assert client.get(_base(ctx) + "/public/domains/files.example.com/links/deal").json()["link_id"] == link2


def test_pm037_og_preview_contains_only_approved_escaped_metadata(client, db_session):
    """PM-037: an OG preview needs owner approval and never emits raw markup."""
    ctx = _setup(client)
    doc = _document(db_session, ctx, "Preview doc")
    link = _link(client, ctx, doc)

    saved = client.put(_base(ctx) + f"/links/{link}/og", headers=ctx["h"], json={
        "title": "<script>alert(1)</script> Owner title",
        "description": "A <b>description</b>",
        "image_url": "https://cdn.example.com/preview.png",
    })
    assert saved.status_code == 200 and saved.json()["approved"] is False
    assert client.get(_base(ctx) + f"/public/links/{link}/og").status_code == 404

    assert client.post(_base(ctx) + f"/links/{link}/og/approve", headers=ctx["h"]).status_code == 200
    preview = client.get(_base(ctx) + f"/public/links/{link}/og").json()
    assert "<script>" not in str(preview) and "<b>" not in str(preview)
    assert "&lt;script&gt;" in preview["og:title"] and "&lt;b&gt;" in preview["og:description"]
    assert preview["og:image"] == "https://cdn.example.com/preview.png"

    changed = client.put(_base(ctx) + f"/links/{link}/og", headers=ctx["h"], json={
        "title": "Changed", "description": "New", "image_url": "https://cdn.example.com/new.png",
    })
    assert changed.status_code == 200
    assert client.get(_base(ctx) + f"/public/links/{link}/og").status_code == 404


def test_pm043_custom_password_message_renders_without_html_injection(client, db_session):
    """PM-043: the password-screen message is rendered as escaped text."""
    ctx = _setup(client)
    doc = _document(db_session, ctx, "Locked doc")
    link = _link(client, ctx, doc)

    saved = client.put(_base(ctx) + f"/links/{link}/password-screen", headers=ctx["h"], json={
        "message": '<img src=x onerror="steal()"> Call the owner',
    })
    assert saved.status_code == 200, saved.text
    screen = client.get(_base(ctx) + f"/public/links/{link}/password-screen").json()
    assert screen["enabled"] is True
    assert "<img" not in screen["message"]
    assert 'onerror="steal()"' not in screen["message"]
    assert "&lt;img" in screen["message"] and "&quot;steal()&quot;" in screen["message"]
    assert "Call the owner" in screen["message"]

    disabled = client.put(_base(ctx) + f"/links/{link}/password-screen", headers=ctx["h"], json={
        "message": "Hidden", "enabled": False,
    })
    assert disabled.status_code == 200
    assert client.get(_base(ctx) + f"/public/links/{link}/password-screen").status_code == 404


def test_pm044_screenshot_attempts_logged_with_honest_limitation(client, db_session):
    """PM-044: detectable attempts are recorded and the limit is stated honestly."""
    ctx = _setup(client)
    doc = _document(db_session, ctx, "Protected doc")
    link = _link(client, ctx, doc)

    config = client.put(_base(ctx) + f"/links/{link}/screenshot-config", headers=ctx["h"],
                        json={"enabled": True})
    assert config.status_code == 200, config.text
    assert "impossible" in config.json()["limitation"] and "mobile" in config.json()["limitation"]

    for channel, detected in (("print-screen-shortcut", True), ("os-capture", False)):
        logged = client.post(_base(ctx) + f"/public/links/{link}/screenshot-attempts", json={
            "channel": channel, "detected": detected,
        })
        assert logged.status_code == 201, logged.text
    bad = client.post(_base(ctx) + f"/public/links/{link}/screenshot-attempts", json={
        "channel": "<script>", "detected": True,
    })
    assert bad.status_code == 422, bad.text

    report = client.get(_base(ctx) + f"/links/{link}/screenshot-attempts", headers=ctx["h"]).json()
    assert report["enabled"] is True
    assert report["attempts"] == {"print-screen-shortcut": 1, "os-capture": 1}
    assert "cannot be reliably blocked" in report["limits"]
    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/share-links/links/{link}/screenshot-attempts",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 404, cross.text


def test_pm046_watermark_variables_and_style_render_escaped(client, db_session):
    """PM-046: every configured variable renders and viewer text cannot inject markup."""
    ctx = _setup(client)
    doc = _document(db_session, ctx, "Watermarked doc")
    link = _link(client, ctx, doc)

    style = {
        "tiling": True, "position": "bottom-right", "rotation": -30,
        "font_size": 14, "color": "#123456", "opacity": 0.4,
    }
    saved = client.put(_base(ctx) + f"/links/{link}/watermark-profile", headers=ctx["h"], json={
        "variables": ["email", "name", "ip", "date", "time"], "style": style,
    })
    assert saved.status_code == 200, saved.text

    rendered = client.post(_base(ctx) + f"/links/{link}/watermark/render", headers=ctx["h"], json={
        "email": "viewer@example.com", "name": "<b>Alice</b>",
        "ip": "203.0.113.5", "at": "2026-11-24T09:30:00+00:00",
    })
    assert rendered.status_code == 200, rendered.text
    body = rendered.json()
    text = "\n".join(body["lines"])
    assert body["style"] == style
    assert "viewer@example.com" in text and "203.0.113.5" in text
    assert "2026-11-24" in text and "09:30" in text
    assert "&lt;b&gt;Alice&lt;/b&gt;" in text and "<b>" not in text

    invalid = client.put(_base(ctx) + f"/links/{link}/watermark-profile", headers=ctx["h"], json={
        "variables": ["email", "javascript"], "style": style,
    })
    assert invalid.status_code == 422, invalid.text


def test_pm071_branding_resolves_custom_then_pinned_then_default(client, db_session):
    """PM-071: room/link branding resolves custom > pinned > default."""
    ctx = _setup(client)
    doc = _document(db_session, ctx, "Branded doc")
    link = _link(client, ctx, doc)
    room = _room(client, ctx, "Branded room")
    base = _base(ctx)

    default = client.get(base + f"/branding/effective/room/{room}", headers=ctx["h"]).json()
    assert default["source"] == "default" and default["brand_name"] == "NOVARA"

    pinned = client.put(base + "/branding/pinned/room", headers=ctx["h"], json={
        "brand_name": "Pinned Co", "accent": "#111111", "logo_url": "https://cdn.example.com/p.png",
    })
    assert pinned.status_code == 200, pinned.text
    resolved = client.get(base + f"/branding/effective/room/{room}", headers=ctx["h"]).json()
    assert resolved["source"] == "pinned" and resolved["brand_name"] == "Pinned Co"
    assert resolved["accent"] == "#111111" and resolved["preview_url"] == ""

    custom = client.put(base + f"/branding/room/{room}", headers=ctx["h"], json={
        "brand_name": "Custom Co", "accent": "#222222",
        "banner_url": "https://cdn.example.com/banner.png",
    })
    assert custom.status_code == 200, custom.text
    resolved = client.get(base + f"/branding/effective/room/{room}", headers=ctx["h"]).json()
    assert resolved["source"] == "custom" and resolved["brand_name"] == "Custom Co"
    assert resolved["accent"] == "#222222" and resolved["banner_url"].startswith("https://")

    link_default = client.get(base + f"/branding/effective/link/{link}", headers=ctx["h"]).json()
    assert link_default["source"] == "default"
    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/share-links/branding/effective/room/{room}",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 404, cross.text
