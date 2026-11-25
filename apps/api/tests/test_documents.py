from __future__ import annotations

import pytest
from sqlalchemy import select

from novara_core.main import app
from novara_core.models import Event
from novara_core.modules import documents

from .conftest import auth, bootstrap


def _has_prefix(routes, prefix: str) -> bool:
    for route in routes:
        if getattr(route, "path", "").startswith(prefix):
            return True
        nested = getattr(route, "original_router", None)
        if nested is not None and _has_prefix(nested.routes, prefix):
            return True
    return False


@pytest.fixture(scope="module", autouse=True)
def _attach_documents_router():
    prefix = "/api/v1/workspaces/{workspace_id}/documents"
    if _has_prefix(app.routes, prefix):
        yield
        return
    original = list(app.routes)
    app.include_router(documents.router)
    try:
        yield
    finally:
        app.routes[:] = original
        app.router._mark_routes_changed()


def _events(db, workspace_id: str) -> list[Event]:
    return db.execute(
        select(Event).where(Event.workspace_id == workspace_id).order_by(Event.seq)
    ).scalars().all()


def _event_types(db, workspace_id: str) -> list[str]:
    return [event.event_type for event in _events(db, workspace_id)]


def test_dataroom_and_document_metadata_lifecycle(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    actor_id = me.json()["user"]["id"]
    base = f"/api/v1/workspaces/{wid}/documents"

    room = client.post(
        base + "/rooms",
        headers=headers,
        json={"name": " Board Pack ", "description": "Board materials"},
    )
    assert room.status_code == 201, room.text
    assert room.json()["name"] == "Board Pack"
    assert room.json()["created_by"] == actor_id
    room_id = room.json()["id"]

    assert client.get(f"{base}/rooms/{room_id}", headers=headers).json()["id"] == room_id
    assert len(client.get(base + "/rooms", headers=headers).json()) == 1

    created = client.post(
        base,
        headers=headers,
        json={
            "title": " Strategy ",
            "doc_type": "pdf",
            "size_bytes": 2048,
            "storage_path": "metadata://board/strategy.pdf",
            "room_id": room_id,
        },
    )
    assert created.status_code == 201, created.text
    document = created.json()
    assert document["title"] == "Strategy"
    assert document["doc_type"] == "pdf"
    assert document["size_bytes"] == 2048
    assert document["storage_path"] == "metadata://board/strategy.pdf"
    assert document["room_id"] == room_id
    assert document["uploaded_by"] == actor_id
    document_id = document["id"]

    fetched = client.get(f"{base}/{document_id}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == document_id
    assert len(client.get(base, headers=headers).json()) == 1
    assert len(client.get(base + f"?room_id={room_id}", headers=headers).json()) == 1

    patched_room = client.patch(
        f"{base}/rooms/{room_id}", headers=headers, json={"description": "Updated"}
    )
    assert patched_room.status_code == 200, patched_room.text
    assert patched_room.json()["description"] == "Updated"

    deleted = client.delete(f"{base}/{document_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted": True, "document_id": document_id}
    assert client.get(f"{base}/{document_id}", headers=headers).status_code == 404
    assert client.get(base, headers=headers).json() == []

    types = _event_types(db_session, wid)
    for expected in (
        documents.DATAROOM_CREATED,
        documents.DATAROOM_UPDATED,
        documents.DOCUMENT_CREATED,
        documents.DOCUMENT_DELETED,
    ):
        assert expected in types
    assert all(event.payload["actor_id"] == actor_id for event in _events(db_session, wid))
    assert all(event.workspace_id == wid for event in _events(db_session, wid))


def test_dataroom_name_must_be_unique_per_workspace(client):
    tokens = bootstrap(client, "Duplicate", "duplicate@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents/rooms"

    first = client.post(base, headers=headers, json={"name": "Board"})
    assert first.status_code == 201, first.text
    duplicate = client.post(base, headers=headers, json={"name": "Board"})
    assert duplicate.status_code == 409, duplicate.text
    assert "already exists" in duplicate.json()["detail"]

    other = client.post(base, headers=headers, json={"name": "Legal"})
    assert other.status_code == 201, other.text
    conflict = client.patch(
        f"{base}/{other.json()['id']}", headers=headers, json={"name": "Board"}
    )
    assert conflict.status_code == 409, conflict.text

    harmless = client.patch(
        f"{base}/{other.json()['id']}", headers=headers, json={"description": "Contracts"}
    )
    assert harmless.status_code == 200, harmless.text
    assert len(client.get(base, headers=headers).json()) == 2


def test_document_filters_and_bad_payloads(client):
    tokens = bootstrap(client, "BadInput", "bad@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"

    bad_rooms = (
        {"name": ""},
        {"name": "   "},
        {"name": "Valid", "workspace_id": "other"},
        {"name": "Valid", "created_by": "spoofed"},
    )
    for payload in bad_rooms:
        response = client.post(base + "/rooms", headers=headers, json=payload)
        assert response.status_code == 422, (payload, response.text)

    room = client.post(base + "/rooms", headers=headers, json={"name": "Good"})
    assert room.status_code == 201, room.text
    room_id = room.json()["id"]

    bad_documents = (
        {"title": "", "storage_path": "metadata://x"},
        {"title": "Valid", "storage_path": "metadata://x", "size_bytes": -1},
        {"title": "Valid", "storage_path": "metadata://x", "uploaded_by": "spoofed"},
        {"title": "Valid", "storage_path": "metadata://x", "workspace_id": "other"},
        {"title": "Valid"},
        {"title": "Valid", "storage_path": "metadata://x", "room_id": "missing-room"},
    )
    for payload in bad_documents:
        response = client.post(base, headers=headers, json=payload)
        assert response.status_code in (404, 422), (payload, response.text)
    # Only the unknown room case is a 404; the rest are validation failures.
    assert client.post(
        base,
        headers=headers,
        json={"title": "Valid", "storage_path": "metadata://x", "room_id": "missing-room"},
    ).status_code == 404

    assert client.get(base + "?room_id=missing-room", headers=headers).status_code == 404
    assert client.get(base + "/missing", headers=headers).status_code == 404
    assert client.delete(base + "/missing", headers=headers).status_code == 404
    assert client.patch(base + "/rooms/missing", headers=headers, json={"name": "x"}).status_code == 404
    assert client.get(base, headers=auth("garbage")).status_code == 401


def test_documents_and_rooms_are_workspace_isolated(client, db_session):
    first = bootstrap(client, "First", "first@example.com")
    first_headers = auth(first["access_token"])
    first_wid = first["workspace_id"]

    second_response = client.post(
        "/api/v1/workspaces", headers=first_headers, json={"name": "Second"}
    )
    assert second_response.status_code == 200, second_response.text
    second = second_response.json()
    second_wid, second_headers = second["workspace_id"], auth(second["access_token"])

    room2 = client.post(
        f"/api/v1/workspaces/{second_wid}/documents/rooms",
        headers=second_headers,
        json={"name": "Private"},
    )
    assert room2.status_code == 201, room2.text
    room2_id = room2.json()["id"]
    document2 = client.post(
        f"/api/v1/workspaces/{second_wid}/documents",
        headers=second_headers,
        json={
            "title": "Private doc",
            "storage_path": "metadata://private/doc.txt",
            "room_id": room2_id,
        },
    )
    assert document2.status_code == 201, document2.text
    document2_id = document2.json()["id"]

    assert client.get(
        f"/api/v1/workspaces/{second_wid}/documents", headers=first_headers
    ).status_code == 403

    first_base = f"/api/v1/workspaces/{first_wid}/documents"
    assert client.get(first_base, headers=first_headers).json() == []
    assert client.get(first_base + "/rooms", headers=first_headers).json() == []
    assert client.get(f"{first_base}/{document2_id}", headers=first_headers).status_code == 404
    assert client.get(f"{first_base}/rooms/{room2_id}", headers=first_headers).status_code == 404
    assert client.delete(f"{first_base}/{document2_id}", headers=first_headers).status_code == 404
    assert client.patch(
        f"{first_base}/rooms/{room2_id}", headers=first_headers, json={"name": "hijacked"}
    ).status_code == 404
    assert client.post(
        first_base,
        headers=first_headers,
        json={"title": "Cross room", "storage_path": "metadata://x", "room_id": room2_id},
    ).status_code == 404

    assert _events(db_session, first_wid) == []
    assert all(event.workspace_id == second_wid for event in _events(db_session, second_wid))


def test_room_delete_guarded_by_existing_document_metadata(client, db_session):
    tokens = bootstrap(client, "Guard", "guard@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/documents"

    room = client.post(base + "/rooms", headers=headers, json={"name": "Guarded"})
    room_id = room.json()["id"]
    document = client.post(
        base,
        headers=headers,
        json={
            "title": "In room",
            "storage_path": "metadata://guarded/file.txt",
            "room_id": room_id,
        },
    )
    assert document.status_code == 201, document.text

    guarded = client.delete(f"{base}/rooms/{room_id}", headers=headers)
    assert guarded.status_code == 409, guarded.text

    assert client.delete(f"{base}/{document.json()['id']}", headers=headers).status_code == 200
    assert client.delete(f"{base}/rooms/{room_id}", headers=headers).status_code == 200
    assert client.get(f"{base}/rooms/{room_id}", headers=headers).status_code == 404
    assert documents.DATAROOM_DELETED in _event_types(db_session, wid)
