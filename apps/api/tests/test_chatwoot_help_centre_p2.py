"""Clean-room P2/P3 Chatwoot help-centre governance acceptance tests.

Named rows: CW-066, CW-067, CW-087, CW-088, CW-089, CW-090, CW-091, CW-092.
No upstream source copied. No external service contacted.
"""

from __future__ import annotations

import socket

import pytest

from novara_core.main import app
from novara_core.models import new_id

from .conftest import auth, bootstrap

MEMBER_EMAIL = "hcg-member@example.com"


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
def _attach_help_centre_router():
    prefix = "/api/v1/workspaces/{workspace_id}/help-centre"
    if _has_prefix(app.routes, prefix):
        yield
        return
    from novara_core.modules import help_centre_governance

    original = list(app.routes)
    app.include_router(help_centre_governance.router)
    try:
        yield
    finally:
        app.routes[:] = original
        app.router._mark_routes_changed()


def _invite_readonly(client, owner_token):
    reg = client.post("/api/v1/auth/register", json={
        "email": MEMBER_EMAIL,
        "password": "Password123!",
        "display_name": "HCG Reader",
    })
    assert reg.status_code in (200, 201), reg.text
    member_token = reg.json()["access_token"]
    invite = client.post(
        f"/api/v1/workspaces/{owner_token['workspace_id']}/invitations",
        headers=auth(owner_token["access_token"]),
        json={"email": MEMBER_EMAIL, "role": "read_only"},
    )
    assert invite.status_code in (200, 201), invite.text
    accept = client.post(
        "/api/v1/invitations/accept",
        headers=auth(member_token),
        json={"token": invite.json()["invite_token"]},
    )
    assert accept.status_code in (200, 201), accept.text
    return accept.json().get("access_token", member_token)


def _setup(client, db):
    owner = bootstrap(client, email="hcg-owner@example.com", workspace_name="HCG WS")
    reader_token = _invite_readonly(client, owner)
    ws = owner["workspace_id"]
    other = client.post("/api/v1/workspaces", headers=auth(owner["access_token"]),
                        json={"name": "Other HCG"})
    assert other.status_code == 200, other.text
    return {
        "ws": ws,
        "h_owner": auth(owner["access_token"]),
        "h_reader": auth(reader_token),
        "other_ws": other.json()["workspace_id"],
        "h_other": auth(other.json()["access_token"]),
    }


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/help-centre"


def _portal(client, ctx, name, slug):
    response = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/tickets/help-portals",
        headers=ctx["h_owner"], json={"name": name, "slug": slug},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _article(client, ctx, portal_id, slug, *, status="published", audience="public", title=None):
    response = client.post(
        _base(ctx) + "/articles", headers=ctx["h_owner"], json={
            "portal_id": portal_id, "title": title or slug.replace("-", " ").title(),
            "slug": slug, "body": f"Body for {slug}", "audience": audience, "status": status,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _document(db, ctx, title):
    from novara_core.modules.documents import Document

    row = Document(
        id=new_id(), workspace_id=ctx["ws"], title=title, doc_type="pdf",
        size_bytes=1024, storage_path=f"local://opaque/{new_id()}",
        uploaded_by="hcg-owner",
    )
    db.add(row)
    db.commit()
    return row.id


def test_cw087_article_metadata_embeds_and_immutable_revisions(client, db_session):
    """CW-087: create/publish/revise persists rich metadata and every prior revision survives."""
    ctx = _setup(client, db_session)
    pid = _portal(client, ctx, "Docs", "docs")
    article = _article(client, ctx, pid, "getting-started", status="draft")

    meta = client.put(_base(ctx) + f"/articles/{article['id']}/metadata", headers=ctx["h_owner"], json={
        "summary": "A short guide", "tags": ["setup", "basics"],
        "embeds": [{"kind": "video", "url": "https://www.youtube.com/watch?v=abc123"}],
    })
    assert meta.status_code == 200, meta.text
    assert meta.json()["tags"] == ["setup", "basics"]
    assert meta.json()["embeds"][0]["url"].startswith("https://www.youtube.com/")

    bad = client.put(_base(ctx) + f"/articles/{article['id']}/metadata", headers=ctx["h_owner"], json={
        "embeds": [{"kind": "video", "url": "http://attacker.example/steal"}],
    })
    assert bad.status_code == 422, bad.text

    publish = client.patch(_base(ctx) + f"/articles/{article['id']}", headers=ctx["h_owner"],
                           json={"status": "published"})
    assert publish.status_code == 200, publish.text
    assert publish.json()["published_at"] is not None

    revised = client.post(_base(ctx) + f"/articles/{article['id']}/revisions", headers=ctx["h_owner"],
                          json={"note": "clarified steps"})
    assert revised.status_code == 201, revised.text

    revisions = client.get(_base(ctx) + f"/articles/{article['id']}/revisions",
                           headers=ctx["h_owner"]).json()
    versions = [r["version"] for r in revisions]
    assert versions == sorted(versions) and len(versions) >= 3
    original = next(r for r in revisions if r["version"] == 1)
    assert original["status"] == "draft" and original["summary"] == ""
    newest = revisions[-1]
    assert newest["status"] == "published" and newest["summary"] == "A short guide"
    assert newest["note"] == "clarified steps"

    persisted = client.get(_base(ctx) + f"/articles/{article['id']}", headers=ctx["h_owner"]).json()
    assert persisted["status"] == "published"
    assert client.get(_base(ctx) + f"/articles/{article['id']}/metadata",
                      headers=ctx["h_owner"]).json()["summary"] == "A short guide"


def test_cw088_two_portals_hold_independent_branded_content(client, db_session):
    """CW-088: two portals keep separate branding/categories/articles and reject cross-workspace reads."""
    ctx = _setup(client, db_session)
    p1 = _portal(client, ctx, "Alpha Docs", "alpha")
    p2 = _portal(client, ctx, "Beta Docs", "beta")

    b1 = client.put(_base(ctx) + f"/portals/{p1}/branding", headers=ctx["h_owner"],
                    json={"brand_name": "Alpha", "accent": "#112233"})
    b2 = client.put(_base(ctx) + f"/portals/{p2}/branding", headers=ctx["h_owner"],
                    json={"brand_name": "Beta", "accent": "#445566"})
    assert b1.status_code == 200 and b2.status_code == 200
    assert client.get(_base(ctx) + f"/portals/{p1}/branding",
                      headers=ctx["h_owner"]).json()["brand_name"] == "Alpha"
    assert client.get(_base(ctx) + f"/portals/{p2}/branding",
                      headers=ctx["h_owner"]).json()["brand_name"] == "Beta"
    assert client.put(_base(ctx) + f"/portals/{p1}/branding", headers=ctx["h_owner"],
                      json={"brand_name": "Bad", "accent": "red"}).status_code == 422

    cat = client.post(_base(ctx) + f"/portals/{p1}/categories", headers=ctx["h_owner"],
                      json={"name": "Guides", "slug": "guides"})
    assert cat.status_code == 201, cat.text
    assert len(client.get(_base(ctx) + f"/portals/{p1}/categories",
                          headers=ctx["h_owner"]).json()) == 1
    assert client.get(_base(ctx) + f"/portals/{p2}/categories",
                      headers=ctx["h_owner"]).json() == []

    _article(client, ctx, p1, "alpha-only")
    assert len(client.get(_base(ctx) + f"/portals/{p1}/articles",
                          headers=ctx["h_owner"]).json()) == 1
    assert client.get(_base(ctx) + f"/portals/{p2}/articles",
                      headers=ctx["h_owner"]).json() == []

    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/help-centre/portals/{p1}/branding",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 404, cross.text


def test_cw089_view_and_search_counts_come_from_real_local_events(client, db_session):
    """CW-089: article views and visitor searches are persisted, workspace-scoped and aggregated."""
    from novara_core.models import Event

    ctx = _setup(client, db_session)
    p1 = _portal(client, ctx, "Docs", "docs")
    article = _article(client, ctx, p1, "billing-help")
    other = _portal(client, ctx, "Other", "other")

    for key in ("visitor-a", "visitor-b"):
        assert client.post(_base(ctx) + f"/articles/{article['id']}/views", json={
            "visitor_key": key,
        }).status_code == 201
    assert client.post(_base(ctx) + f"/articles/{article['id']}/views", json={
        "visitor_key": "bad key!",
    }).status_code == 422

    report = client.get(_base(ctx) + "/reports/article-views", headers=ctx["h_owner"]).json()
    assert report["views"][article["id"]] == 2

    for _ in range(3):
        assert client.post(_base(ctx) + "/public/docs/searches", json={
            "query": "refund", "results_count": 0, "visitor_key": "visitor-a",
        }).status_code == 201
    assert client.post(_base(ctx) + "/public/docs/searches", json={
        "query": "refund", "results_count": 2, "visitor_key": "visitor-b",
    }).status_code == 201
    assert client.post(_base(ctx) + "/public/other/searches", json={
        "query": "shipping", "results_count": 0, "visitor_key": "visitor-a",
    }).status_code == 201

    searches = {s["query"]: s for s in client.get(
        _base(ctx) + "/reports/searches", headers=ctx["h_owner"]).json()["searches"]}
    assert searches["refund"]["count"] == 4 and searches["refund"]["results"] == 2
    assert searches["shipping"]["count"] == 1

    events = db_session.query(Event).filter(
        Event.workspace_id == ctx["ws"], Event.event_type == "help_centre_governance.changed"
    ).count()
    assert events >= 7
    other_events = db_session.query(Event).filter(
        Event.workspace_id == ctx["other_ws"],
        Event.event_type == "help_centre_governance.changed",
    ).count()
    assert other_events == 0


def test_cw090_widget_surfaces_published_articles_without_creating_a_ticket(client, db_session):
    """CW-090: the widget opens published articles but never creates a support ticket."""
    from novara_core.modules.support import Ticket

    ctx = _setup(client, db_session)
    p1 = _portal(client, ctx, "Docs", "docs")
    article = _article(client, ctx, p1, "password-reset")
    draft = _article(client, ctx, p1, "secret-draft", status="draft")

    widget = client.put(_base(ctx) + f"/portals/{p1}/widget", headers=ctx["h_owner"], json={
        "enabled": True, "title": "Need help?", "intro": "Start here.",
    })
    assert widget.status_code == 200, widget.text

    listed = client.get(_base(ctx) + "/public/docs/widget/articles").json()
    slugs = [item["slug"] for item in listed["articles"]]
    assert listed["title"] == "Need help?" and "password-reset" in slugs
    assert "secret-draft" not in slugs

    before = db_session.query(Ticket).filter(Ticket.workspace_id == ctx["ws"]).count()
    opened = client.get(_base(ctx) + "/public/docs/widget/articles/password-reset")
    assert opened.status_code == 200, opened.text
    assert opened.json()["body"] == "Body for password-reset"
    after = db_session.query(Ticket).filter(Ticket.workspace_id == ctx["ws"]).count()
    assert after == before

    assert client.get(_base(ctx) + "/public/docs/widget/articles/secret-draft").status_code == 404
    assert client.put(_base(ctx) + f"/portals/{p1}/widget", headers=ctx["h_reader"],
                      json={"enabled": False}).status_code == 403
    assert client.get(_base(ctx) + "/public/docs/widget/articles").status_code == 200


def test_cw091_private_pages_invisible_on_every_unauthenticated_surface(client, db_session):
    """CW-091: an internal page cannot be read through any public route."""
    ctx = _setup(client, db_session)
    p1 = _portal(client, ctx, "Docs", "docs")
    article = _article(client, ctx, p1, "private-notes")
    visible = _article(client, ctx, p1, "public-notes")

    set_private = client.put(_base(ctx) + f"/articles/{article['id']}/visibility",
                             headers=ctx["h_owner"],
                             json={"visibility": "internal", "allowed_group": "staff"})
    assert set_private.status_code == 200, set_private.text
    assert client.put(_base(ctx) + f"/articles/{article['id']}/visibility",
                      headers=ctx["h_owner"], json={"visibility": "secret"}).status_code == 422

    legacy = f"/api/v1/workspaces/{ctx['ws']}/tickets/public/help/docs/articles"
    public_slugs = [a["slug"] for a in client.get(legacy).json()]
    assert "public-notes" in public_slugs and "private-notes" not in public_slugs
    assert client.get(legacy + "/private-notes").status_code == 404

    assert client.put(_base(ctx) + f"/portals/{p1}/widget", headers=ctx["h_owner"],
                      json={"enabled": True}).status_code == 200
    widget_slugs = [a["slug"] for a in client.get(
        _base(ctx) + "/public/docs/widget/articles").json()["articles"]]
    assert "private-notes" not in widget_slugs and "public-notes" in widget_slugs
    assert client.get(_base(ctx) + "/public/docs/widget/articles/private-notes").status_code == 404
    assert client.post(_base(ctx) + f"/articles/{article['id']}/views", json={
        "visitor_key": "visitor-a",
    }).status_code == 404

    staff_view = client.get(_base(ctx) + f"/articles/{article['id']}/visibility",
                            headers=ctx["h_owner"]).json()
    assert staff_view["visibility"] == "internal" and staff_view["allowed_group"] == "staff"


def test_cw092_api_article_crud_honours_ui_permissions(client, db_session):
    """CW-092: API article CRUD uses the same permission gate as the staff UI."""
    ctx = _setup(client, db_session)
    p1 = _portal(client, ctx, "Docs", "docs")
    article = _article(client, ctx, p1, "api-article")

    assert client.get(_base(ctx) + "/articles", params={"portal_id": p1},
                      headers=ctx["h_reader"]).status_code == 200
    assert client.get(_base(ctx) + f"/articles/{article['id']}",
                      headers=ctx["h_reader"]).status_code == 200

    denied_create = client.post(_base(ctx) + "/articles", headers=ctx["h_reader"], json={
        "portal_id": p1, "title": "Denied", "slug": "denied", "body": "nope",
    })
    assert denied_create.status_code == 403, denied_create.text
    assert client.patch(_base(ctx) + f"/articles/{article['id']}", headers=ctx["h_reader"],
                        json={"title": "Denied"}).status_code == 403
    assert client.delete(_base(ctx) + f"/articles/{article['id']}",
                         headers=ctx["h_reader"]).status_code == 403

    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/help-centre/articles/{article['id']}",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 404, cross.text
    cross_write = client.post(
        f"/api/v1/workspaces/{ctx['other_ws']}/help-centre/articles",
        headers=ctx["h_owner"], json={
            "portal_id": p1, "title": "Cross", "slug": "cross", "body": "nope",
        },
    )
    assert cross_write.status_code == 403, cross_write.text

    patched = client.patch(_base(ctx) + f"/articles/{article['id']}", headers=ctx["h_owner"],
                           json={"title": "Renamed", "status": "published"})
    assert patched.status_code == 200 and patched.json()["title"] == "Renamed"
    assert client.delete(_base(ctx) + f"/articles/{article['id']}",
                         headers=ctx["h_owner"]).status_code == 204
    assert client.get(_base(ctx) + f"/articles/{article['id']}",
                      headers=ctx["h_owner"]).status_code == 404


def test_cw066_content_gaps_are_advisory_and_derived_from_local_searches(client, db_session):
    """CW-066: gaps come only from stored local search events and stay advisory."""
    ctx = _setup(client, db_session)
    p1 = _portal(client, ctx, "Docs", "docs")
    assert client.get(_base(ctx) + "/content-gaps", headers=ctx["h_owner"]).json() == []

    for _ in range(3):
        assert client.post(_base(ctx) + "/public/docs/searches", json={
            "query": "refund-policy", "results_count": 0, "visitor_key": "visitor-a",
        }).status_code == 201

    refresh = client.post(_base(ctx) + "/content-gaps/refresh", headers=ctx["h_owner"])
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["source"] == "local_search_events"
    gaps = client.get(_base(ctx) + "/content-gaps", headers=ctx["h_owner"]).json()
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap["portal_id"] == p1 and gap["query"] == "refund-policy"
    assert gap["searches"] == 3 and gap["zero_result_searches"] == 3
    assert gap["advisory_only"] is True and "advisor" in gap["advisory"]

    assert client.post(_base(ctx) + "/content-gaps/refresh",
                       headers=ctx["h_reader"]).status_code == 403
    other_gaps = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/help-centre/content-gaps",
        headers=ctx["h_other"],
    ).json()
    assert other_gaps == []


def test_cw067_faq_index_accepts_only_authorized_documents_and_retains_citations(client, db_session):
    """CW-067: indexing is workspace-authorized and every entry keeps a citation."""
    ctx = _setup(client, db_session)
    p1 = _portal(client, ctx, "Docs", "docs")
    article = _article(client, ctx, p1, "billing")
    doc_id = _document(db_session, ctx, "Billing handbook")

    indexed = client.post(_base(ctx) + "/faq-index", headers=ctx["h_owner"], json={
        "document_id": doc_id, "article_id": article["id"], "excerpt": "How refunds work",
    })
    assert indexed.status_code == 201, indexed.text
    citation = indexed.json()["citation"]
    assert citation["document_id"] == doc_id and citation["title"] == "Billing handbook"
    assert citation["excerpt"] == "How refunds work" and citation["workspace_id"] == ctx["ws"]
    assert indexed.json()["authorized"] is True

    duplicate = client.post(_base(ctx) + "/faq-index", headers=ctx["h_owner"], json={
        "document_id": doc_id, "excerpt": "again",
    })
    assert duplicate.status_code == 409, duplicate.text

    foreign_doc = _document(db_session, {"ws": ctx["other_ws"]}, "Foreign manual")
    foreign = client.post(_base(ctx) + "/faq-index", headers=ctx["h_owner"], json={
        "document_id": foreign_doc, "excerpt": "not yours",
    })
    assert foreign.status_code == 404, foreign.text

    denied = client.post(_base(ctx) + "/faq-index", headers=ctx["h_reader"], json={
        "document_id": foreign_doc, "excerpt": "read only",
    })
    assert denied.status_code == 403, denied.text

    listed = client.get(_base(ctx) + "/faq-index", headers=ctx["h_owner"]).json()
    assert len(listed) == 1 and listed[0]["document_id"] == doc_id
    assert listed[0]["citation"]["article_id"] == article["id"]
