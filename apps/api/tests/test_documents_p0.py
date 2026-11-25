"""Named acceptance tests for the P0 document cluster.

PM-001 (document + room + share + tracked view), PM-073 (view events on the
shared spine with salesperson notification and customer timeline), PM-095
(precise document permission verbs) and PM-137 (a beginner can follow the
installed-product walkthrough). Every assertion is against real persisted rows
returned by the API, never a route count or a menu item.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.main import app  # noqa: F401 - registers every module router
from novara_core.models import Contact, Event, Notification
from novara_core.modules import documents
from novara_core.permissions import (
    DOCUMENT_ADMIN,
    DOCUMENT_READ,
    DOCUMENT_WRITE,
    ROLE_PERMISSIONS,
    has_permission,
)

from .conftest import auth, bootstrap


def _member(client, wid, owner_headers, email, role, name):
    """Invite, register and accept a second member with an explicit role."""
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


def _seed(client, wid, headers, title="Proposal", room_id=None, **link_kwargs):
    """Create one document and one link, returning their ids and raw token."""
    doc = client.post(
        f"/api/v1/workspaces/{wid}/documents",
        headers=headers,
        json={
            "title": title, "doc_type": "pdf",
            "storage_path": "metadata://p/proposal.pdf", "room_id": room_id,
        },
    )
    assert doc.status_code == 201, doc.text
    document_id = doc.json()["id"]
    link = client.post(
        f"/api/v1/workspaces/{wid}/documents/{document_id}/links",
        headers=headers,
        json=link_kwargs,
    )
    assert link.status_code == 201, link.text
    return document_id, link.json()["id"], link.json()["token"]


def _events(db, wid) -> list[Event]:
    return db.execute(
        select(Event).where(Event.workspace_id == wid).order_by(Event.seq)
    ).scalars().all()


# ---------------------------------------------------------------------------
# PM-095 — precise document verbs
# ---------------------------------------------------------------------------


def test_document_verbs_are_precise_and_role_scoped():
    assert has_permission("owner", DOCUMENT_READ)
    assert has_permission("owner", DOCUMENT_WRITE)
    assert has_permission("owner", DOCUMENT_ADMIN)
    for verb in (DOCUMENT_READ, DOCUMENT_WRITE, DOCUMENT_ADMIN):
        assert verb in ROLE_PERMISSIONS["admin"]
        assert verb in ROLE_PERMISSIONS["sales_manager"]
        assert verb in ROLE_PERMISSIONS["marketing"]
    assert has_permission("sales_rep", DOCUMENT_READ)
    assert has_permission("sales_rep", DOCUMENT_WRITE)
    assert not has_permission("sales_rep", DOCUMENT_ADMIN)
    assert has_permission("support", DOCUMENT_READ)
    assert not has_permission("support", DOCUMENT_WRITE)
    assert has_permission("read_only", DOCUMENT_READ)
    assert not has_permission("read_only", DOCUMENT_WRITE)
    assert not has_permission("read_only", DOCUMENT_ADMIN)


def test_document_endpoints_enforce_read_write_and_admin_verbs(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    document_id, link_id, _ = _seed(client, wid, headers)
    reader = _member(client, wid, headers, "reader@example.com", "read_only", "Reader")
    rep = _member(client, wid, headers, "rep@example.com", "sales_rep", "Rep")
    base = f"/api/v1/workspaces/{wid}/documents"

    # read verb is enough to browse metadata and engagement history
    assert client.get(base, headers=reader).status_code == 200
    assert client.get(f"{base}/{document_id}", headers=reader).status_code == 200
    assert client.get(f"{base}/{document_id}/links", headers=reader).status_code == 200

    # write verb is required to create and modify metadata or links
    assert client.post(base + "/rooms", headers=reader, json={"name": "x"}).status_code == 403
    assert client.post(
        base, headers=reader, json={"title": "x", "storage_path": "metadata://x"}
    ).status_code == 403
    assert client.post(
        f"{base}/{document_id}/links", headers=reader, json={}
    ).status_code == 403
    assert client.post(
        f"{base}/{document_id}/links", headers=rep, json={}
    ).status_code == 201

    # admin verb alone permits destructive and link-revoking actions
    assert client.delete(f"{base}/{document_id}", headers=reader).status_code == 403
    assert client.delete(f"{base}/{document_id}", headers=rep).status_code == 403
    assert client.post(f"{base}/links/{link_id}/revoke", headers=reader).status_code == 403
    assert client.post(f"{base}/links/{link_id}/instant-revoke", headers=rep).status_code == 403
    assert client.delete(f"{base}/{document_id}", headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# PM-073 — view events, salesperson notification, customer timeline
# ---------------------------------------------------------------------------


def test_document_view_notifies_salesperson_and_reaches_customer_timeline(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    document_id, _, token = _seed(client, wid, headers, download_allowed=False)

    visit = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/visits",
        headers=headers,
        json={"visitor_name": "Dana Buyer", "visitor_email": "dana@example.com"},
    )
    assert visit.status_code == 201, visit.text

    contact = db_session.execute(
        select(Contact).where(Contact.workspace_id == wid, Contact.email == "dana@example.com")
    ).scalar_one_or_none()
    assert contact is not None
    assert visit.json()["contact_id"] == contact.id

    types = [event.event_type for event in _events(db_session, wid)]
    assert documents.DOCUMENT_VIEWED in types

    viewed = [
        event for event in _events(db_session, wid)
        if event.event_type == documents.DOCUMENT_VIEWED
    ]
    assert len(viewed) == 1
    assert viewed[0].entity_id == contact.id
    assert viewed[0].payload["document_id"] == document_id

    notifications = db_session.execute(
        select(Notification).where(
            Notification.workspace_id == wid, Notification.category == "document_view"
        )
    ).scalars().all()
    assert len(notifications) == 1
    assert notifications[0].contact_id == contact.id
    assert "Proposal" in notifications[0].message

    timeline = client.get(
        f"/api/v1/workspaces/{wid}/contacts/{contact.id}/timeline", headers=headers
    )
    assert timeline.status_code == 200, timeline.text
    assert any(row["event_type"] == documents.DOCUMENT_VIEWED for row in timeline.json())
    # The audit and notification events share the view's correlation id.
    assert len(timeline.json()) >= 3

    # Identifying the same visitor again reuses the one CRM identity.
    again = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/identify",
        headers=headers,
        json={"visitor_name": "Dana Buyer", "visitor_email": "dana@example.com"},
    )
    assert again.status_code == 200, again.text
    assert again.json()["created"] is False
    assert again.json()["contact_id"] == contact.id


def test_download_is_policy_controlled_and_publishes_a_shared_event(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    document_id, _, blocked_token = _seed(client, wid, headers, download_allowed=False)
    visit = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{blocked_token}/visits",
        headers=headers,
        json={"visitor_email": "downloader@example.com"},
    ).json()

    denied = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{blocked_token}"
        f"/visits/{visit['id']}/download",
        headers=headers,
        json={},
    )
    assert denied.status_code == 403, denied.text
    assert documents.DOCUMENT_DOWNLOADED not in [
        event.event_type for event in _events(db_session, wid)
    ]

    allowed = client.post(
        f"/api/v1/workspaces/{wid}/documents/{document_id}/links",
        headers=headers,
        json={"download_allowed": True},
    )
    assert allowed.status_code == 201, allowed.text
    allowed_token = allowed.json()["token"]
    visit2 = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{allowed_token}/visits",
        headers=headers,
        json={"visitor_email": "downloader@example.com"},
    ).json()
    downloaded = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{allowed_token}"
        f"/visits/{visit2['id']}/download",
        headers=headers,
        json={"page_number": 2},
    )
    assert downloaded.status_code == 201, downloaded.text
    assert downloaded.json()["document_id"] == document_id

    events = _events(db_session, wid)
    download_events = [
        event for event in events if event.event_type == documents.DOCUMENT_DOWNLOADED
    ]
    assert len(download_events) == 1
    assert download_events[0].payload["page_number"] == 2
    notification = db_session.execute(
        select(Notification).where(
            Notification.workspace_id == wid, Notification.category == "document_download"
        )
    ).scalar_one_or_none()
    assert notification is not None


# ---------------------------------------------------------------------------
# PM-001 — the complete room -> document -> share -> view journey
# ---------------------------------------------------------------------------


def test_document_journey_has_enforced_sharing_controls_and_isolation(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"

    room = client.post(base + "/rooms", headers=headers, json={"name": "Investor pack"})
    assert room.status_code == 201, room.text
    room_id = room.json()["id"]
    document_id, link_id, token = _seed(
        client, wid, headers, room_id=room_id,
        password="gate", expires_in_hours=24, max_views=1, download_allowed=False,
    )
    assert client.get(base + f"?room_id={room_id}", headers=headers).json()[0]["id"] == document_id

    resolve = client.get(f"{base}/links/resolve/{token}", headers=headers)
    assert resolve.status_code == 200 and resolve.json()["password_required"] is True
    assert client.post(
        f"{base}/links/resolve/{token}/unlock", headers=headers, json={"password": "wrong"}
    ).status_code == 403
    assert client.post(
        f"{base}/links/resolve/{token}/unlock", headers=headers, json={"password": "gate"}
    ).status_code == 200

    first = client.post(
        f"{base}/links/resolve/{token}/visits", headers=headers, json={"visitor_name": "A"}
    )
    assert first.status_code == 201, first.text
    limited = client.post(f"{base}/links/resolve/{token}/visits", headers=headers, json={})
    assert limited.status_code == 429, limited.text

    assert client.post(f"{base}/links/{link_id}/revoke", headers=headers).status_code == 200
    assert client.get(f"{base}/links/resolve/{token}", headers=headers).status_code == 200
    assert client.post(f"{base}/links/resolve/{token}/visits", headers=headers, json={}).status_code == 410

    second = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Other"}
    )
    assert second.status_code == 200, second.text
    other_headers = auth(second.json()["access_token"])
    other_wid = second.json()["workspace_id"]
    assert client.get(f"/api/v1/workspaces/{other_wid}/documents", headers=other_headers).json() == []
    assert client.get(
        f"/api/v1/workspaces/{other_wid}/documents", headers=headers
    ).status_code == 403
    other_base = f"/api/v1/workspaces/{other_wid}/documents"
    assert client.get(f"{other_base}/{document_id}", headers=other_headers).status_code == 404

    # Deleting a room with documents still in it stays guarded.
    assert client.delete(f"{base}/rooms/{room_id}", headers=headers).status_code == 409
    assert client.delete(f"{base}/{document_id}", headers=headers).status_code == 200
    assert client.delete(f"{base}/rooms/{room_id}", headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# PM-137 — the documented beginner walkthrough is itself tested
# ---------------------------------------------------------------------------


def test_install_guide_document_walkthrough_runs_end_to_end(client, db_session):
    """Mirrors docs/INSTALL.md 'Document metadata quickstart' step by step."""
    tokens = bootstrap(client, "Starter", "starter@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"

    # Step 1: create a data room.
    room = client.post(base + "/rooms", headers=headers, json={"name": "Sales collateral"})
    assert room.status_code == 201, room.text
    # Step 2: register a document record. No file is uploaded.
    doc = client.post(
        base, headers=headers,
        json={
            "title": "Overview.pdf", "doc_type": "pdf",
            "storage_path": "metadata://local/overview.pdf", "room_id": room.json()["id"],
        },
    )
    assert doc.status_code == 201, doc.text
    document_id = doc.json()["id"]
    # Step 3: create a share link with enforced controls.
    link = client.post(
        f"{base}/{document_id}/links", headers=headers,
        json={"max_views": 3, "view_only": True, "download_allowed": False},
    )
    assert link.status_code == 201, link.text
    token = link.json()["token"]
    # Step 4: resolve the link, then record a visit.
    assert client.get(f"{base}/links/resolve/{token}", headers=headers).status_code == 200
    visit = client.post(
        f"{base}/links/resolve/{token}/visits", headers=headers,
        json={"visitor_email": "prospect@example.com"},
    )
    assert visit.status_code == 201, visit.text
    client.post(
        f"{base}/links/resolve/{token}/visits/{visit.json()['id']}/page-views",
        headers=headers, json={"page_number": 1},
    )
    # Step 5: the sharing user sees the notification.
    feed = client.get(
        f"/api/v1/workspaces/{wid}/notifications?category=document_view", headers=headers
    )
    assert feed.status_code == 200 and len(feed.json()) == 1
    assert documents.DOCUMENT_VIEWED in [
        event.event_type for event in _events(db_session, wid)
    ]
