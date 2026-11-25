"""Named acceptance tests for the Papermark P1 document cluster.

Every test drives the real FastAPI application through the ``client`` fixture
(in-memory SQLite) and asserts persisted rows, returned API data and shared
audit events. No mock endpoints, no external calls and no copied AGPL source.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from novara_core.main import app
from novara_core.models import Contact, Event, Notification, new_id, now
from novara_core.modules import document_links, documents, storage

from .conftest import auth, bootstrap


def _member(client, wid, owner_headers, email, role, name):
    """Invite and accept a second workspace member with an explicit role."""
    invited = client.post(
        f"/api/v1/workspaces/{wid}/invitations",
        headers=owner_headers,
        json={"email": email, "role": role},
    )
    assert invited.status_code == 200, invited.text
    raw = invited.json()["invite_token"]
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": name},
    )
    assert registered.status_code == 200, registered.text
    joined = client.post(
        "/api/v1/invitations/accept",
        headers=auth(registered.json()["access_token"]),
        json={"token": raw},
    )
    assert joined.status_code == 200, joined.text
    return auth(joined.json()["access_token"])


def _doc(client, wid, headers, title="P1 doc", room_id=None, storage_path="metadata://p1/doc.pdf"):
    response = client.post(
        f"/api/v1/workspaces/{wid}/documents",
        headers=headers,
        json={
            "title": title, "doc_type": "pdf",
            "storage_path": storage_path, "room_id": room_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _link(client, wid, headers, document_id, **kwargs):
    response = client.post(
        f"/api/v1/workspaces/{wid}/documents/{document_id}/links",
        headers=headers, json=kwargs,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _visit(client, wid, headers, token, **kwargs):
    response = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/visits",
        headers=headers, json=kwargs,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _events(db, wid) -> list[Event]:
    return db.execute(
        select(Event).where(Event.workspace_id == wid)
    ).scalars().all()


# ---------------------------------------------------------------------------
# PM-009, PM-011, PM-041 — versions, immutable pages, links follow primary
# ---------------------------------------------------------------------------


def test_pm009_pm011_pm041_versions_pages_and_link_serves_primary(client, db_session):
    """A new primary version is atomic and an existing link immediately serves it."""
    tokens = bootstrap(client, "Versions", "versions@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"
    doc = _doc(client, wid, headers, storage_path="metadata://v1.pdf")
    did = doc["id"]
    link = _link(client, wid, headers, did)
    token = link["token"]

    before = client.get(f"{base}/links/resolve/{token}", headers=headers)
    assert before.status_code == 200, before.text
    assert before.json()["primary_version_id"] is None

    v1 = client.post(f"{base}/{did}/versions", headers=headers,
                     json={"storage_path": "metadata://v1.pdf", "size_bytes": 100})
    assert v1.status_code == 201, v1.text
    cover = client.post(
        f"{base}/{did}/versions/{v1.json()['id']}/pages", headers=headers,
        json={"page_number": 1, "label": "Old cover"},
    )
    assert cover.status_code == 201, cover.text

    v2 = client.post(f"{base}/{did}/versions", headers=headers,
                     json={"storage_path": "metadata://v2.pdf", "size_bytes": 200})
    assert v2.status_code == 201, v2.text
    new_page = client.post(
        f"{base}/{did}/versions/{v2.json()['id']}/pages", headers=headers,
        json={"page_number": 1, "label": "New cover"},
    )
    assert new_page.status_code == 201, new_page.text

    versions = client.get(f"{base}/{did}/versions", headers=headers).json()
    assert [(v["version_number"], v["is_primary"]) for v in versions] == [(1, False), (2, True)]
    assert len([v for v in versions if v["is_primary"]]) == 1
    assert documents.primary_version(db_session, wid, did).id == v2.json()["id"]

    # PM-041: the token was created before either version existed and still
    # resolves to the current primary bytes and its page list.
    resolved = client.get(f"{base}/links/resolve/{token}", headers=headers)
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["primary_version_id"] == v2.json()["id"]
    assert body["primary_version_number"] == 2
    assert body["storage_path"] == "metadata://v2.pdf"
    assert body["size_bytes"] == 200
    assert [p["id"] for p in body["pages"]] == [new_page.json()["id"]]
    assert db_session.get(documents.Document, did).storage_path == "metadata://v2.pdf"

    version_events = [e for e in _events(db_session, wid)
                      if e.event_type == documents.DOCUMENT_VERSION_CREATED]
    assert len(version_events) == 2
    assert version_events[-1].payload["demoted_versions"] == 1

    # PM-011: per-page view rows point at the immutable page id.
    visit = _visit(client, wid, headers, token)
    page_view = client.post(
        f"{base}/links/resolve/{token}/visits/{visit['id']}/page-views",
        headers=headers,
        json={"page_number": 1, "page_id": new_page.json()["id"]},
    )
    assert page_view.status_code == 201, page_view.text
    pv_row = db_session.get(document_links.PageView, page_view.json()["page_view_id"])
    assert pv_row.page_id == new_page.json()["id"]
    time_on_page = client.get(f"{base}/{did}/analytics/time-on-page", headers=headers).json()
    assert any(row["page_id"] == new_page.json()["id"] for row in time_on_page)
    # Pages have no mutation surface: the id stays stable.
    rejected = client.patch(
        f"{base}/{did}/versions/{v2.json()['id']}/pages/{new_page.json()['id']}",
        headers=headers, json={"page_number": 9},
    )
    assert rejected.status_code in (404, 405)
    assert db_session.get(documents.DocumentPage, new_page.json()["id"]).page_number == 1

    other = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other versions"})
    assert other.status_code == 200, other.text
    other_wid, other_headers = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(f"{base}/{did}/versions", headers=other_headers).status_code == 403
    assert client.get(
        f"/api/v1/workspaces/{other_wid}/documents/{did}/versions", headers=headers
    ).status_code == 403


# ---------------------------------------------------------------------------
# PM-019, PM-022 — folder paths, placement and collections
# ---------------------------------------------------------------------------


def test_pm019_pm022_folder_paths_and_collection_grouping(client, db_session):
    """Folder CRUD persists derived paths with collisions; collections group docs."""
    tokens = bootstrap(client, "Library", "library@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"

    parent = client.post(base + "/folders", headers=headers, json={"name": "Research"})
    assert parent.status_code == 201, parent.text
    child = client.post(base + "/folders", headers=headers,
                        json={"name": "2026", "parent_id": parent.json()["id"]})
    assert child.status_code == 201, child.text
    assert child.json()["path"] == "/Research/2026"
    assert client.post(base + "/folders", headers=headers,
                       json={"name": "2026", "parent_id": parent.json()["id"]}).status_code == 409
    assert client.post(base + "/folders", headers=headers,
                       json={"name": "research"}).status_code == 409
    renamed = client.patch(f"{base}/folders/{parent.json()['id']}",
                           headers=headers, json={"name": "Archive"})
    assert renamed.status_code == 200, renamed.text
    assert client.get(f"{base}/folders/{child.json()['id']}",
                      headers=headers).json()["path"] == "/Archive/2026"

    doc = _doc(client, wid, headers, storage_path="metadata://folder/doc.pdf")
    placed = client.post(f"{base}/{doc['id']}/folder", headers=headers,
                         json={"folder_id": child.json()["id"]})
    assert placed.status_code == 200 and placed.json()["folder_id"] == child.json()["id"]
    assert db_session.get(documents.Document, doc["id"]).folder_id == child.json()["id"]
    assert client.delete(f"{base}/folders/{child.json()['id']}",
                         headers=headers).status_code == 409
    assert client.post(f"{base}/{doc['id']}/folder", headers=headers,
                       json={"folder_id": None}).status_code == 200
    assert client.delete(f"{base}/folders/{child.json()['id']}",
                         headers=headers).status_code == 200
    assert client.delete(f"{base}/folders/{parent.json()['id']}",
                         headers=headers).status_code == 200

    library = client.post(base + "/collections", headers=headers,
                          json={"name": "Proposals", "scope": "library"})
    assert library.status_code == 201, library.text
    room = client.post(base + "/rooms", headers=headers, json={"name": "Board"})
    room_collection = client.post(base + "/collections", headers=headers, json={
        "name": "Board pack", "scope": "room", "room_id": room.json()["id"],
    })
    assert room_collection.status_code == 201, room_collection.text
    assert client.post(base + "/collections", headers=headers, json={
        "name": "Proposals", "scope": "library",
    }).status_code == 409

    cid = library.json()["id"]
    assert client.post(f"{base}/collections/{cid}/documents", headers=headers,
                       json={"document_id": doc["id"]}).status_code == 201
    members = client.get(f"{base}/collections/{cid}/documents", headers=headers).json()
    assert [row["id"] for row in members] == [doc["id"]]
    assert client.delete(f"{base}/collections/{cid}/documents/{doc['id']}",
                         headers=headers).status_code == 200
    assert client.get(f"{base}/collections/{cid}/documents", headers=headers).json() == []
    collection_row = db_session.get(documents.DocumentCollection, cid)
    assert collection_row.workspace_id == wid

    other = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other library"})
    other_headers = auth(other.json()["access_token"])
    assert client.get(base + "/collections", headers=other_headers).status_code == 403
    assert client.get(f"{base}/collections/{cid}", headers=other_headers).status_code == 403


# ---------------------------------------------------------------------------
# PM-026, PM-047 — agreement immutability and real NDA content gate
# ---------------------------------------------------------------------------


def test_pm026_pm047_agreement_immutability_and_nda_content_gate(client, db_session):
    """Content metadata is withheld until an NDA acceptance row exists."""
    tokens = bootstrap(client, "NDA", "nda@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"
    doc = _doc(client, wid, headers, storage_path="metadata://nda/deal.pdf")
    link = _link(client, wid, headers, doc["id"], require_nda=True)
    token = link["token"]

    blocked = client.get(f"{base}/links/resolve/{token}", headers=headers)
    assert blocked.status_code == 403, blocked.text
    assert "title" not in blocked.json() and "storage_path" not in blocked.json()
    assert client.post(f"{base}/links/resolve/{token}/visits", headers=headers,
                       json={"visitor_email": "buyer@example.com"}).status_code == 403

    agreement = client.post(f"{base}/{doc['id']}/agreements", headers=headers,
                            json={"title": "Mutual NDA", "body": "Keep it secret."})
    assert agreement.status_code == 201, agreement.text
    aid = agreement.json()["id"]
    accepted = client.post(f"{base}/agreements/{aid}/accept", headers=headers,
                           json={"visitor_email": "buyer@example.com"})
    assert accepted.status_code == 200, accepted.text
    row = db_session.get(document_links.Agreement, aid)
    assert row.accepted_at is not None
    assert row.visitor_email == "buyer@example.com"
    assert row.visitor_contact_id is not None
    assert any(e.event_type == document_links.DOCUMENT_AGREEMENT_ACCEPTED
               for e in _events(db_session, wid))

    assert client.patch(f"{base}/agreements/{aid}", headers=headers,
                        json={"body": "Changed"}).status_code == 409
    assert db_session.get(document_links.Agreement, aid).body == "Keep it secret."

    opened = client.get(f"{base}/links/resolve/{token}", headers=headers,
                        params={"visitor_email": "buyer@example.com"})
    assert opened.status_code == 200, opened.text
    assert opened.json()["document_id"] == doc["id"]
    visit = _visit(client, wid, headers, token, visitor_email="buyer@example.com")
    assert visit["contact_id"] == row.visitor_contact_id


# ---------------------------------------------------------------------------
# PM-031 — email verification gate
# ---------------------------------------------------------------------------


def test_pm031_email_verification_gate_blocks_then_admits_verified_viewer(client):
    """An unverified viewer is blocked; a verified one gets real view rows."""
    tokens = bootstrap(client, "Verify", "verify@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"
    doc = _doc(client, wid, headers, storage_path="metadata://verify/doc.pdf")
    link = _link(client, wid, headers, doc["id"], require_email_verification=True)
    token = link["token"]
    email = "viewer@example.com"

    assert client.get(f"{base}/links/resolve/{token}", headers=headers).status_code == 403
    assert client.get(f"{base}/links/resolve/{token}", headers=headers,
                      params={"visitor_email": email}).status_code == 403
    assert client.post(f"{base}/links/resolve/{token}/visits", headers=headers,
                       json={"visitor_email": email}).status_code == 403

    issued = client.post(f"{base}/links/resolve/{token}/request-verification",
                         headers=headers, json={"email": email})
    assert issued.status_code == 200, issued.text
    code = issued.json()["code"]
    assert client.post(f"{base}/links/resolve/{token}/confirm-verification",
                       headers=headers,
                       json={"email": email, "code": "wrong"}).status_code == 403
    confirmed = client.post(f"{base}/links/resolve/{token}/confirm-verification",
                            headers=headers, json={"email": email, "code": code})
    assert confirmed.status_code == 200, confirmed.text
    assert client.get(f"{base}/links/resolve/{token}", headers=headers,
                      params={"visitor_email": email}).status_code == 200
    visit = _visit(client, wid, headers, token, visitor_email=email)
    assert visit["visitor_email"] == email


# ---------------------------------------------------------------------------
# PM-034 — allow/block rules with deliberate subdomain matching
# ---------------------------------------------------------------------------


def test_pm034_email_allowlist_domain_subdomains_and_block(client):
    """Allow rules gate view creation and domain rules match subdomains by choice."""
    tokens = bootstrap(client, "Allowlist", "allow@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"
    doc = _doc(client, wid, headers, storage_path="metadata://allow/doc.pdf")
    link = _link(client, wid, headers, doc["id"])
    lid, token = link["id"], link["token"]

    allow = client.post(f"{base}/links/{lid}/access-rules", headers=headers, json={
        "effect": "allow", "kind": "domain", "value": "Example.com",
        "include_subdomains": True,
    })
    assert allow.status_code == 201, allow.text
    block = client.post(f"{base}/links/{lid}/access-rules", headers=headers, json={
        "effect": "block", "kind": "email", "value": "Blocked@Sub.Example.com",
    })
    assert block.status_code == 201, block.text
    rules = client.get(f"{base}/links/{lid}/access-rules", headers=headers).json()
    assert {r["value"] for r in rules} == {"example.com", "blocked@sub.example.com"}

    assert _visit(client, wid, headers, token,
                  visitor_email="friend@deep.sub.example.com")["id"]
    assert client.post(f"{base}/links/resolve/{token}/visits", headers=headers,
                       json={"visitor_email": "outsider@elsewhere.com"}).status_code == 403
    assert client.post(f"{base}/links/resolve/{token}/visits", headers=headers,
                       json={"visitor_email": "blocked@sub.example.com"}).status_code == 403

    # A rule that opts out of subdomains intentionally excludes them.
    second = _link(client, wid, headers, doc["id"])
    strict = client.post(f"{base}/links/{second['id']}/access-rules", headers=headers, json={
        "effect": "allow", "kind": "domain", "value": "foo.com",
        "include_subdomains": False,
    })
    assert strict.status_code == 201, strict.text
    assert client.post(f"{base}/links/resolve/{second['token']}/visits", headers=headers,
                       json={"visitor_email": "a@sub.foo.com"}).status_code == 403
    assert _visit(client, wid, headers, second["token"],
                  visitor_email="a@foo.com")["id"]


# ---------------------------------------------------------------------------
# PM-055, PM-063 — room membership and enforced ACL groups
# ---------------------------------------------------------------------------


def test_pm055_pm063_room_membership_and_permission_groups(client, db_session):
    """Documents join rooms without duplication; ACL rows are scoped and enforced."""
    tokens = bootstrap(client, "Rooms", "rooms@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"
    room_a = client.post(base + "/rooms", headers=headers, json={"name": "A"})
    room_b = client.post(base + "/rooms", headers=headers, json={"name": "B"})
    doc = _doc(client, wid, headers, storage_path="metadata://rooms/doc.pdf")

    for room in (room_a, room_b):
        attached = client.post(f"{base}/{doc['id']}/rooms/{room.json()['id']}",
                               headers=headers)
        assert attached.status_code == 201, attached.text
    assert set(client.get(f"{base}/{doc['id']}/rooms", headers=headers).json()) == {
        room_a.json()["id"], room_b.json()["id"],
    }
    assert client.delete(f"{base}/{doc['id']}/rooms/{room_a.json()['id']}",
                         headers=headers).status_code == 200
    assert client.get(f"{base}/{doc['id']}", headers=headers).status_code == 200
    assert client.get(f"{base}/{doc['id']}/rooms", headers=headers).json() == [
        room_b.json()["id"]
    ]

    group = client.post(base + "/permission-groups", headers=headers,
                        json={"name": "Approved viewers"})
    assert group.status_code == 201, group.text
    gid = group.json()["id"]
    member = client.post(f"{base}/permission-groups/{gid}/members", headers=headers,
                         json={"email": "member@example.com"})
    assert member.status_code == 201, member.text
    assert db_session.get(document_links.PermissionGroup, gid).workspace_id == wid

    link = _link(client, wid, headers, doc["id"], required_group_id=gid)
    token = link["token"]
    assert link["required_group_id"] == gid
    denied = client.get(f"{base}/links/resolve/{token}", headers=headers,
                        params={"visitor_email": "outsider@example.com"})
    assert denied.status_code == 403, denied.text
    assert client.post(f"{base}/links/resolve/{token}/visits", headers=headers,
                       json={"visitor_email": "outsider@example.com"}).status_code == 403
    allowed = client.get(f"{base}/links/resolve/{token}", headers=headers,
                         params={"visitor_email": "member@example.com"})
    assert allowed.status_code == 200, allowed.text
    assert _visit(client, wid, headers, token,
                  visitor_email="member@example.com")["id"]

    other = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other ACL"})
    other_headers = auth(other.json()["access_token"])
    assert client.get(base + "/permission-groups", headers=other_headers).status_code == 403
    assert client.get(f"{base}/permission-groups/{gid}", headers=other_headers).status_code == 404
    assert client.post(f"{base}/{doc['id']}/links", headers=headers,
                       json={"required_group_id": "not-in-this-workspace"}).status_code == 404


# ---------------------------------------------------------------------------
# PM-075, PM-078, PM-079, PM-082, PM-090 — real engagement analytics
# ---------------------------------------------------------------------------


def test_pm075_pm078_pm079_pm082_pm090_analytics_from_real_views(client, db_session):
    """Every figure is derived from persisted visits, page views and events."""
    tokens = bootstrap(client, "Analytics", "analytics@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"
    doc = _doc(client, wid, headers, storage_path="metadata://analytics/doc.pdf")
    link = _link(client, wid, headers, doc["id"], download_allowed=True)
    token = link["token"]

    contact = Contact(
        id=new_id(), workspace_id=wid, email="repeat@example.com",
        full_name="Repeat", source="document_view", created_at=now(), updated_at=now(),
    )
    db_session.add(contact)
    db_session.commit()
    v1 = _visit(client, wid, headers, token, contact_id=contact.id)
    _visit(client, wid, headers, token, contact_id=contact.id)
    _visit(client, wid, headers, token)  # anonymous

    summary = client.get(f"{base}/{doc['id']}/analytics/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["total_views"] == 3
    assert summary.json()["unique_visitors"] == 2
    assert summary.json()["total_downloads"] == 0

    page_view = client.post(
        f"{base}/links/resolve/{token}/visits/{v1['id']}/page-views",
        headers=headers, json={"page_number": 1},
    )
    assert page_view.status_code == 201, page_view.text
    left = client.post(
        f"{base}/links/resolve/{token}/visits/{v1['id']}/page-views/"
        f"{page_view.json()['page_view_id']}/leave", headers=headers,
    )
    assert left.status_code == 200, left.text
    pv_row = db_session.get(document_links.PageView, page_view.json()["page_view_id"])
    pv_row.entered_at = now() - timedelta(seconds=60)
    pv_row.left_at = now() - timedelta(seconds=18)
    pv_row.duration_seconds = None
    db_session.commit()
    timed = client.get(f"{base}/{doc['id']}/analytics/time-on-page", headers=headers).json()
    assert timed[0]["page_number"] == 1
    assert timed[0]["views"] == 1
    assert 40 <= timed[0]["total_duration_seconds"] <= 43

    visit_row = db_session.get(document_links.LinkVisit, v1["id"])
    visit_row.started_at = now() - timedelta(seconds=120)
    visit_row.ended_at = now() - timedelta(seconds=30)
    visit_row.duration_seconds = None
    db_session.commit()
    timing = client.get(f"{base}/{doc['id']}/analytics/timing", headers=headers).json()
    row = next(item for item in timing if item["visit_id"] == v1["id"])
    assert 88 <= row["duration_seconds"] <= 91

    anonymous_visit = client.get(f"{base}/links/{link['id']}/views", headers=headers).json()[0]
    downloaded = client.post(
        f"{base}/links/resolve/{token}/visits/{anonymous_visit['id']}/download",
        headers=headers, json={},
    )
    assert downloaded.status_code == 201, downloaded.text
    assert db_session.get(document_links.LinkVisit, anonymous_visit["id"]).downloaded_at is not None
    assert client.get(f"{base}/{doc['id']}/analytics/summary",
                      headers=headers).json()["total_downloads"] == 1

    document_events = [e for e in _events(db_session, wid)
                       if (e.payload or {}).get("document_id") == doc["id"]]
    assert documents.DOCUMENT_DOWNLOADED in [e.event_type for e in document_events]
    assert document_links.DOCUMENT_PAGE_TIMED in [e.event_type for e in document_events]
    aggregated = client.get(f"{base}/analytics/events", headers=headers,
                            params={"document_id": doc["id"]}).json()
    expected = {}
    for event in document_events:
        if event.event_type in (documents.DOCUMENT_VIEWED, documents.DOCUMENT_DOWNLOADED,
                                document_links.DOCUMENT_PAGE_VIEWED):
            expected[event.event_type] = expected.get(event.event_type, 0) + 1
    assert {row["event_type"]: row["count"] for row in aggregated} == expected


# ---------------------------------------------------------------------------
# PM-081 — real-time notification to the assigned owner
# ---------------------------------------------------------------------------


def test_pm081_view_notifies_assigned_owner(client, db_session):
    """A real view creates an in-app notification for the contact's owner."""
    tokens = bootstrap(client, "Notify", "notify@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    rep_headers = _member(client, wid, headers,
                          "assigned-rep@example.com", "sales_rep", "Rep")
    rep_id = client.get("/api/v1/auth/me", headers=rep_headers).json()["user"]["id"]
    base = f"/api/v1/workspaces/{wid}/documents"
    doc = _doc(client, wid, headers, storage_path="metadata://notify/doc.pdf")
    link = _link(client, wid, headers, doc["id"])

    contact = Contact(
        id=new_id(), workspace_id=wid, email="owned@example.com", full_name="Owned",
        source="document_view", owner_id=rep_id, created_at=now(), updated_at=now(),
    )
    db_session.add(contact)
    db_session.commit()
    visit = _visit(client, wid, headers, link["token"], contact_id=contact.id)
    assert visit["contact_id"] == contact.id

    notifications = db_session.execute(
        select(Notification).where(
            Notification.workspace_id == wid,
            Notification.contact_id == contact.id,
            Notification.category == "document_view",
        )
    ).scalars().all()
    assert len(notifications) == 1
    assert notifications[0].user_id == rep_id
    notification_events = [e for e in _events(db_session, wid)
                           if e.event_type == "notification.created"]
    assert any(e.payload.get("user_id") == rep_id for e in notification_events)


# ---------------------------------------------------------------------------
# PM-087, PM-089, PM-142 — scoped history, room rollup, documented API
# ---------------------------------------------------------------------------


def test_pm087_pm089_pm142_history_room_rollup_and_documented_api(client, db_session):
    """Bearer-token API creates, shares and reads real views; history stays scoped."""
    tokens = bootstrap(client, "History", "history@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"
    room = client.post(base + "/rooms", headers=headers, json={"name": "Deal room"})
    assert room.status_code == 201, room.text
    doc = _doc(client, wid, headers, room_id=room.json()["id"],
               storage_path="metadata://history/doc.pdf")
    link = _link(client, wid, headers, doc["id"])
    visit = _visit(client, wid, headers, link["token"], visitor_email="reader@example.com")
    contact_id = visit["contact_id"]
    assert contact_id is not None

    views = client.get(f"{base}/links/{link['id']}/views", headers=headers,
                       params={"skip": 0, "limit": 1})
    assert views.status_code == 200, views.text
    assert [row["id"] for row in views.json()] == [visit["id"]]
    history = client.get(f"{base}/visitors/{contact_id}/views", headers=headers)
    assert history.status_code == 200, history.text
    assert [row["id"] for row in history.json()] == [visit["id"]]

    rollup = client.get(f"{base}/rooms/{room.json()['id']}/analytics", headers=headers)
    assert rollup.status_code == 200, rollup.text
    assert rollup.json()["total_views"] == 1
    assert rollup.json()["unique_viewers"] == 1
    assert rollup.json()["documents"][0]["views"] == 1

    second_doc = _doc(client, wid, headers, title="Attached",
                      storage_path="metadata://history/attached.pdf")
    attached = client.post(f"{base}/{second_doc['id']}/rooms/{room.json()['id']}",
                           headers=headers)
    assert attached.status_code == 201, attached.text
    second_link = _link(client, wid, headers, second_doc["id"])
    _visit(client, wid, headers, second_link["token"], visitor_email="other@example.com")
    assert client.get(f"{base}/rooms/{room.json()['id']}/analytics",
                      headers=headers).json()["total_views"] == 2

    other = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other history"})
    other_headers = auth(other.json()["access_token"])
    assert client.get(f"{base}/links/{link['id']}/views", headers=other_headers).status_code == 403
    assert client.get(f"{base}/visitors/{contact_id}/views", headers=other_headers).status_code == 403
    assert client.get(f"{base}/rooms/{room.json()['id']}/analytics",
                      headers=other_headers).status_code == 403
    stored_views = db_session.execute(
        select(document_links.LinkVisit).where(document_links.LinkVisit.link_id == link["id"])
    ).scalars().all()
    assert len(stored_views) == 1 and stored_views[0].workspace_id == wid

    # PM-142: the published OpenAPI document lists the exact bearer-token
    # routes used above, so the API is documented as well as executable.
    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/workspaces/{workspace_id}/documents",
        "/api/v1/workspaces/{workspace_id}/documents/{document_id}/links",
        "/api/v1/workspaces/{workspace_id}/documents/links/resolve/{token}/visits",
        "/api/v1/workspaces/{workspace_id}/documents/links/{link_id}/views",
        "/api/v1/workspaces/{workspace_id}/documents/visitors/{visitor_id}/views",
    ):
        assert path in paths, f"missing documented route: {path}"


# ---------------------------------------------------------------------------
# PM-121 — document preferences and room member settings
# ---------------------------------------------------------------------------


def test_pm121_document_preferences_and_room_member_settings(client):
    """Preferences persist in one workspace and really change new link defaults."""
    tokens = bootstrap(client, "Prefs", "prefs@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"
    member_headers = _member(client, wid, headers,
                             "room-member@example.com", "sales_rep", "Member")
    member_id = client.get("/api/v1/auth/me", headers=member_headers).json()["user"]["id"]

    patched = client.patch(base + "/preferences", headers=headers,
                           json={"default_view_only": False, "default_link_expiry_hours": 24})
    assert patched.status_code == 200, patched.text
    fetched = client.get(base + "/preferences", headers=headers).json()
    assert fetched["default_view_only"] is False
    assert fetched["default_link_expiry_hours"] == 24
    assert fetched["workspace_id"] == wid and fetched["user_id"]

    doc = _doc(client, wid, headers, storage_path="metadata://prefs/doc.pdf")
    link = _link(client, wid, headers, doc["id"])
    assert link["view_only"] is False
    assert link["expires_at"] is not None

    room = client.post(base + "/rooms", headers=headers, json={"name": "Settings room"})
    setting = client.put(
        f"{base}/rooms/{room.json()['id']}/members/{member_id}/settings",
        headers=headers, json={"can_manage": True, "can_download": True},
    )
    assert setting.status_code == 200, setting.text
    listed = client.get(f"{base}/rooms/{room.json()['id']}/members",
                        headers=headers).json()
    assert [(row["user_id"], row["can_manage"], row["can_download"]) for row in listed] == [
        (member_id, True, True)
    ]

    other = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other prefs"})
    other_headers = auth(other.json()["access_token"])
    assert client.get(base + "/preferences", headers=other_headers).status_code == 403
    assert client.get(f"/api/v1/workspaces/{other.json()['workspace_id']}/documents/preferences",
                      headers=headers).status_code == 403


# ---------------------------------------------------------------------------
# PM-150 — local, licence-compatible document conversion
# ---------------------------------------------------------------------------


def test_pm150_local_conversion_output_without_agpl_source(client, db_session):
    """Conversion output is produced locally, audited, and free of AGPL source."""
    tokens = bootstrap(client, "Convert", "convert@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/storage"
    uploaded = client.post(
        base + "/files", headers=headers,
        files={"file": ("notes.txt", b"NOVARA local conversion", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    source_id = uploaded.json()["id"]

    job = client.post(base + "/conversions", headers=headers,
                      json={"source_file_id": source_id, "target_format": "text"})
    assert job.status_code == 201, job.text
    result = job.json()
    assert result["status"] == "completed", result
    assert result["result_file_id"] is not None
    assert result["finished_at"] is not None
    converted = client.get(
        f"{base}/files/{result['result_file_id']}/download", headers=headers
    )
    assert converted.status_code == 200, converted.text
    assert converted.content == b"NOVARA local conversion"

    job_row = db_session.get(storage.ConversionJob, result["id"])
    assert job_row.workspace_id == wid
    assert job_row.status == "completed" and job_row.finished_at is not None
    assert any(e.event_type == storage.FILE_CONVERTED
               and e.payload.get("result_file_id") == result["result_file_id"]
               for e in _events(db_session, wid))

    root = Path(__file__).resolve().parents[3]
    assert (root / "apps/api/novara_core/modules/storage.py").is_file()
    assert not (root / "apps/api/novara_core/lib/trigger").exists(), "AGPL conversion source found"
