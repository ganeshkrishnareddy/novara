"""Clean-room P2/P3 Papermark data-room governance acceptance tests.

Named rows: PM-050, PM-057, PM-058, PM-059, PM-060, PM-061, PM-062, PM-064,
PM-065, PM-066. No upstream source copied. No external service contacted.
"""

from __future__ import annotations

import hashlib
import socket

import pytest

from novara_core.main import app
from novara_core.models import new_id

from .conftest import auth, bootstrap

MEMBER_EMAIL = "drg-member@example.com"


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
def _attach_dataroom_router():
    prefix = "/api/v1/workspaces/{workspace_id}/data-rooms"
    if _has_prefix(app.routes, prefix):
        yield
        return
    from novara_core.modules import dataroom_governance

    original = list(app.routes)
    app.include_router(dataroom_governance.router)
    try:
        yield
    finally:
        app.routes[:] = original
        app.router._mark_routes_changed()


def _invite_member(client, owner_token):
    reg = client.post("/api/v1/auth/register", json={
        "email": MEMBER_EMAIL,
        "password": "Password123!",
        "display_name": "DRG Member",
    })
    assert reg.status_code in (200, 201), reg.text
    member_token = reg.json()["access_token"]
    invite = client.post(
        f"/api/v1/workspaces/{owner_token['workspace_id']}/invitations",
        headers=auth(owner_token["access_token"]),
        json={"email": MEMBER_EMAIL, "role": "sales_rep"},
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
    from novara_core.models import User

    owner = bootstrap(client, email="drg-owner@example.com", workspace_name="DRG WS")
    member_token = _invite_member(client, owner)
    ws = owner["workspace_id"]
    owner_user = db.query(User).filter(User.email == "drg-owner@example.com").one()
    member_user = db.query(User).filter(User.email == MEMBER_EMAIL).one()
    return {
        "ws": ws,
        "h_owner": auth(owner["access_token"]),
        "h_member": auth(member_token),
        "owner_id": owner_user.id,
        "member_id": member_user.id,
        "member_email": MEMBER_EMAIL,
    }


def _room(client, ctx, name):
    response = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms",
        headers=ctx["h_owner"],
        json={"name": name, "description": "clean-room data room"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _document(db, ctx, title):
    from novara_core.modules.documents import Document

    row = Document(
        id=new_id(), workspace_id=ctx["ws"], title=title, doc_type="pdf",
        size_bytes=1024, storage_path=f"local://opaque/{new_id()}",
        uploaded_by=ctx["owner_id"],
    )
    db.add(row)
    db.commit()
    return row.id


def _attach(client, ctx, room_id, document_id, headers=None):
    response = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/documents",
        headers=headers or ctx["h_owner"],
        json={"document_id": document_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _link(db, ctx, document_id):
    from novara_core.modules.document_links import DocumentLink

    token = "drg-" + new_id()
    row = DocumentLink(
        id=new_id(), workspace_id=ctx["ws"], document_id=document_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        view_only=True, download_allowed=False, created_by=ctx["owner_id"],
    )
    db.add(row)
    db.commit()
    return row.id


def _visit(db, ctx, link_id):
    from novara_core.modules.document_links import LinkVisit

    row = LinkVisit(
        id=new_id(), workspace_id=ctx["ws"], link_id=link_id,
        visitor_email="visitor@example.com",
    )
    db.add(row)
    db.commit()
    return row.id


def _room_invite(client, ctx, room_id):
    response = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/invitations",
        headers=ctx["h_owner"],
        json={"email": ctx["member_email"], "role": "viewer"},
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


def _accept_room_invite(client, ctx, room_id, token):
    response = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/invitations/accept",
        headers=ctx["h_member"],
        json={"token": token},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_pm050_room_has_documents_visitors_links_and_audit(client, db_session):
    ctx = _setup(client, db_session)
    room_id = _room(client, ctx, "Deal room")
    doc_id = _document(db_session, ctx, "Deck.pdf")
    _attach(client, ctx, room_id, doc_id)
    link_id = _link(db_session, ctx, doc_id)
    _visit(db_session, ctx, link_id)

    room = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}",
        headers=ctx["h_owner"],
    )
    assert room.status_code == 200, room.text
    assert room.json()["documents"] == [doc_id]
    assert room.json()["link_count"] == 1
    assert room.json()["visitor_count"] == 1

    events = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/events",
        headers=ctx["h_owner"],
    )
    assert events.status_code == 200, events.text
    types = [e["event_type"] for e in events.json()]
    assert "room.created" in types
    assert "document.attached" in types


def test_pm057_nested_room_folders_can_be_created_listed_and_deleted(client, db_session):
    ctx = _setup(client, db_session)
    room_id = _room(client, ctx, "Folders")
    base = f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/folders"

    parent = client.post(base, headers=ctx["h_owner"], json={"name": "Legal"})
    assert parent.status_code == 201, parent.text
    parent_id = parent.json()["id"]
    child = client.post(base, headers=ctx["h_owner"], json={
        "name": "2026", "parent_id": parent_id,
    })
    assert child.status_code == 201, child.text
    assert child.json()["path"] == "Legal/2026"

    listed = client.get(base, headers=ctx["h_owner"])
    assert listed.status_code == 200, listed.text
    paths = {f["path"] for f in listed.json()}
    assert paths == {"Legal", "Legal/2026"}

    assert client.delete(f"{base}/{child.json()['id']}", headers=ctx["h_owner"]).status_code == 200
    assert client.delete(f"{base}/{parent_id}", headers=ctx["h_owner"]).status_code == 200
    assert client.get(base, headers=ctx["h_owner"]).json() == []


def test_pm058_room_item_ordering_persists_across_reads(client, db_session):
    ctx = _setup(client, db_session)
    room_id = _room(client, ctx, "Ordering")
    first = _document(db_session, ctx, "First.pdf")
    second = _document(db_session, ctx, "Second.pdf")
    _attach(client, ctx, room_id, first)
    _attach(client, ctx, room_id, second)

    update = client.put(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/order",
        headers=ctx["h_owner"],
        json={"entries": [
            {"item_type": "document", "item_id": second, "position": 0},
            {"item_type": "document", "item_id": first, "position": 1},
        ]},
    )
    assert update.status_code == 200, update.text

    url = f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/items"
    for _ in range(2):
        response = client.get(url, headers=ctx["h_owner"])
        assert response.status_code == 200, response.text
        assert [(x["item_type"], x["item_id"]) for x in response.json()] == [
            ("document", second), ("document", first),
        ]


def test_pm059_viewer_group_is_room_scoped_and_bindable_to_link(client, db_session):
    ctx = _setup(client, db_session)
    room_id = _room(client, ctx, "Group room")
    other_room = _room(client, ctx, "Other group room")
    doc_id = _document(db_session, ctx, "Scoped.pdf")
    _attach(client, ctx, room_id, doc_id)
    link_id = _link(db_session, ctx, doc_id)

    group = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/groups",
        headers=ctx["h_owner"], json={"name": "Investors"},
    )
    assert group.status_code == 201, group.text
    group_id = group.json()["id"]
    other_group = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{other_room}/groups",
        headers=ctx["h_owner"], json={"name": "Other investors"},
    )
    assert other_group.status_code == 201, other_group.text

    bound = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/groups/{group_id}/bind-link",
        headers=ctx["h_owner"], json={"link_id": link_id},
    )
    assert bound.status_code == 201, bound.text
    lookup = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/links/{link_id}/group",
        headers=ctx["h_owner"],
    )
    assert lookup.json() == {"link_id": link_id, "group_id": group_id, "room_id": room_id}

    denied = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{other_room}"
        f"/groups/{other_group.json()['id']}/bind-link",
        headers=ctx["h_owner"], json={"link_id": link_id},
    )
    assert denied.status_code == 404, denied.text


def test_pm060_email_and_domain_rules_admit_exactly_intended_viewers(client, db_session):
    ctx = _setup(client, db_session)
    room_id = _room(client, ctx, "Rules")
    group = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/groups",
        headers=ctx["h_owner"], json={"name": "Domain viewers"},
    )
    group_id = group.json()["id"]
    rules = f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/groups/{group_id}/rules"
    assert client.post(rules, headers=ctx["h_owner"], json={
        "effect": "allow", "kind": "domain", "value": "example.com",
    }).status_code == 201
    assert client.post(rules, headers=ctx["h_owner"], json={
        "effect": "block", "kind": "email", "value": "blocked@example.com",
    }).status_code == 201

    check = f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/groups/{group_id}/membership-check"
    admitted = client.post(check, headers=ctx["h_owner"], json={"email": "ann@example.com"})
    assert admitted.json()["admitted"] is True
    subdomain = client.post(check, headers=ctx["h_owner"], json={"email": "bob@sub.example.com"})
    assert subdomain.json()["admitted"] is True
    blocked = client.post(check, headers=ctx["h_owner"], json={"email": "blocked@example.com"})
    assert blocked.json()["admitted"] is False
    assert blocked.json()["reason"] == "blocked_by_rule"
    outsider = client.post(check, headers=ctx["h_owner"], json={"email": "eve@other.org"})
    assert outsider.json()["admitted"] is False


def test_pm061_group_item_permissions_control_view_and_download(client, db_session):
    ctx = _setup(client, db_session)
    room_id = _room(client, ctx, "Per item")
    visible = _document(db_session, ctx, "Visible.pdf")
    hidden = _document(db_session, ctx, "Hidden.pdf")
    _attach(client, ctx, room_id, visible)
    _attach(client, ctx, room_id, hidden)
    group = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/groups",
        headers=ctx["h_owner"], json={"name": "_item viewers"},
    )
    group_id = group.json()["id"]
    base = f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/groups/{group_id}/items"

    first = client.put(f"{base}/{visible}", headers=ctx["h_owner"], json={
        "document_id": visible, "can_view": True, "can_download": False,
    })
    assert first.status_code == 200, first.text
    second = client.put(f"{base}/{hidden}", headers=ctx["h_owner"], json={
        "document_id": hidden, "can_view": False, "can_download": True,
    })
    assert second.status_code == 200, second.text

    listed = client.get(base, headers=ctx["h_owner"])
    assert listed.status_code == 200, listed.text
    assert [(x["document_id"], x["can_download"]) for x in listed.json()] == [(visible, False)]
    assert hidden not in {x["document_id"] for x in listed.json()}

    mismatch = client.put(f"{base}/{visible}", headers=ctx["h_owner"], json={
        "document_id": hidden, "can_view": True,
    })
    assert mismatch.status_code == 422


def test_pm062_updating_link_permissions_immediately_changes_visibility(client, db_session):
    ctx = _setup(client, db_session)
    room_id = _room(client, ctx, "Link permissions")
    doc_id = _document(db_session, ctx, "Linked.pdf")
    _attach(client, ctx, room_id, doc_id)
    link_id = _link(db_session, ctx, doc_id)
    set_url = (
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/links/{link_id}/items/{doc_id}"
    )
    visibility_url = (
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/links/{link_id}/visibility/{doc_id}"
    )

    initial = client.put(set_url, headers=ctx["h_owner"], json={
        "document_id": doc_id, "can_view": True, "can_download": False,
    })
    assert initial.status_code == 200, initial.text
    assert client.get(visibility_url, headers=ctx["h_owner"]).json() == {
        "visible": True, "can_download": False,
    }

    hidden = client.put(set_url, headers=ctx["h_owner"], json={
        "document_id": doc_id, "can_view": False, "can_download": False,
    })
    assert hidden.status_code == 200, hidden.text
    assert client.get(visibility_url, headers=ctx["h_owner"]).json() == {
        "visible": False, "can_download": False,
    }

    restored = client.put(set_url, headers=ctx["h_owner"], json={
        "document_id": doc_id, "can_view": True, "can_download": True,
    })
    assert restored.status_code == 200, restored.text
    assert client.get(visibility_url, headers=ctx["h_owner"]).json() == {
        "visible": True, "can_download": True,
    }


def test_pm064_room_entitlements_deny_another_rooms_document(client, db_session):
    ctx = _setup(client, db_session)
    room_a = _room(client, ctx, "Entitlement A")
    room_b = _room(client, ctx, "Entitlement B")
    doc_a = _document(db_session, ctx, "A.pdf")
    doc_b = _document(db_session, ctx, "B.pdf")
    _attach(client, ctx, room_a, doc_a)
    _attach(client, ctx, room_b, doc_b)
    _accept_room_invite(client, ctx, room_a, _room_invite(client, ctx, room_a))

    base = f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms"
    allowed = client.get(f"{base}/{room_a}/access/{doc_a}", headers=ctx["h_member"])
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["allowed"] is True

    denied = client.get(f"{base}/{room_b}/access/{doc_a}", headers=ctx["h_member"])
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "document_not_in_room"

    decisions = client.get(f"{base}/{room_a}/access-decisions", headers=ctx["h_owner"])
    assert decisions.status_code == 200, decisions.text
    assert any(d["actor_id"] == ctx["member_id"] and d["allowed"] for d in decisions.json())


def test_pm065_invitation_acceptance_grants_only_the_invited_room(client, db_session):
    ctx = _setup(client, db_session)
    invited_room = _room(client, ctx, "Invited only")
    other_room = _room(client, ctx, "Not invited")
    doc = _document(db_session, ctx, "OnlyA.pdf")
    _attach(client, ctx, other_room, doc)
    token = _room_invite(client, ctx, invited_room)

    accepted = _accept_room_invite(client, ctx, invited_room, token)
    assert accepted["granted"] is True
    assert accepted["room_id"] == invited_room

    mine = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/my-rooms",
        headers=ctx["h_member"],
    )
    assert mine.status_code == 200, mine.text
    assert [r["room_id"] for r in mine.json()] == [invited_room]

    denied = client.get(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{other_room}/access/{doc}",
        headers=ctx["h_member"],
    )
    assert denied.status_code == 403, denied.text

    repeat = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{invited_room}/invitations/accept",
        headers=ctx["h_member"], json={"token": token},
    )
    assert repeat.json()["already_accepted"] is True


def test_pm066_frozen_room_rejects_attach_detach_and_move(client, db_session):
    ctx = _setup(client, db_session)
    room_id = _room(client, ctx, "Frozen")
    attached = _document(db_session, ctx, "Attached.pdf")
    replacement = _document(db_session, ctx, "Replacement.pdf")
    _attach(client, ctx, room_id, attached)

    freeze = client.post(
        f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}/freeze",
        headers=ctx["h_owner"],
    )
    assert freeze.status_code == 200, freeze.text
    assert freeze.json()["frozen"] is True

    base = f"/api/v1/workspaces/{ctx['ws']}/data-rooms/rooms/{room_id}"
    attach = client.post(f"{base}/documents", headers=ctx["h_owner"],
                         json={"document_id": replacement})
    assert attach.status_code == 409, attach.text
    detach = client.delete(f"{base}/documents/{attached}", headers=ctx["h_owner"])
    assert detach.status_code == 409, detach.text
    move = client.put(f"{base}/order", headers=ctx["h_owner"], json={"entries": [
        {"item_type": "document", "item_id": attached, "position": 5},
    ]})
    assert move.status_code == 409, move.text

    unfreeze = client.post(f"{base}/unfreeze", headers=ctx["h_owner"])
    assert unfreeze.status_code == 200, unfreeze.text
    assert client.delete(f"{base}/documents/{attached}", headers=ctx["h_owner"]).status_code == 200
