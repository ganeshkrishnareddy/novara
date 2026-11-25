from __future__ import annotations

import pytest
from sqlalchemy import select

from novara_core.main import app
from novara_core.models import Event
from novara_core.modules import support

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
def _attach_support_router():
    """Attach our router only when the core app has not already wired it, and
    restore the app afterwards so other test files see the original routes."""
    prefix = "/api/v1/workspaces/{workspace_id}/tickets"
    if _has_prefix(app.routes, prefix):
        yield
        return
    original = list(app.routes)
    app.include_router(support.router)
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


def test_ticket_lifecycle_messages_and_events(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    actor_id = me.json()["user"]["id"]

    created = client.post(
        f"/api/v1/workspaces/{wid}/tickets",
        headers=headers,
        json={"subject": "  Login broken  ", "body": "  Cannot sign in  ", "priority": "high"},
    )
    assert created.status_code == 201, created.text
    ticket = created.json()
    assert ticket["subject"] == "Login broken"
    assert ticket["body"] == "Cannot sign in"
    assert ticket["status"] == "open"
    assert ticket["priority"] == "high"
    ticket_id = ticket["id"]

    patched = client.patch(
        f"/api/v1/workspaces/{wid}/tickets/{ticket_id}",
        headers=headers,
        json={"status": "pending", "priority": "urgent"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "pending"
    assert patched.json()["priority"] == "urgent"

    message = client.post(
        f"/api/v1/workspaces/{wid}/tickets/{ticket_id}/messages",
        headers=headers,
        json={"body": "Investigating now"},
    )
    assert message.status_code == 201, message.text
    assert message.json()["author_id"] == actor_id
    assert message.json()["body"] == "Investigating now"
    assert message.json()["ticket_id"] == ticket_id

    detail = client.get(f"/api/v1/workspaces/{wid}/tickets/{ticket_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["ticket"]["status"] == "pending"
    assert len(detail.json()["messages"]) == 1

    listed = client.get(f"/api/v1/workspaces/{wid}/tickets", headers=headers)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [ticket_id]
    messages = client.get(
        f"/api/v1/workspaces/{wid}/tickets/{ticket_id}/messages", headers=headers
    )
    assert len(messages.json()) == 1

    types = _event_types(db_session, wid)
    for expected in (
        support.TICKET_CREATED,
        support.TICKET_UPDATED,
        support.TICKET_STATUS_CHANGED,
        support.TICKET_MESSAGE_ADDED,
    ):
        assert expected in types
    assert all(event.payload["actor_id"] == actor_id for event in _events(db_session, wid))
    assert all(event.workspace_id == wid for event in _events(db_session, wid))


def test_ticket_status_and_priority_filters(client):
    tokens = bootstrap(client, "Filters", "filters@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/tickets"

    for subject, status_value, priority in (
        ("Open one", "open", "normal"),
        ("Pending one", "pending", "high"),
        ("Closed one", "closed", "low"),
    ):
        created = client.post(
            base,
            headers=headers,
            json={"subject": subject, "body": "body", "priority": priority},
        )
        assert created.status_code == 201, created.text
        if status_value != "open":
            patched = client.patch(
                f"{base}/{created.json()['id']}",
                headers=headers,
                json={"status": status_value},
            )
            assert patched.status_code == 200, patched.text

    assert len(client.get(base + "?status=open", headers=headers).json()) == 1
    assert len(client.get(base + "?status=pending", headers=headers).json()) == 1
    assert len(client.get(base + "?priority=high", headers=headers).json()) == 1
    assert client.get(base + "?status=open&priority=high", headers=headers).json() == []
    assert client.get(base + "?status=bogus", headers=headers).status_code == 422
    assert client.get(base + "?priority=bogus", headers=headers).status_code == 422


def test_ticket_workspace_isolation(client, db_session):
    first = bootstrap(client, "First", "first@example.com")
    first_headers = auth(first["access_token"])
    first_wid = first["workspace_id"]

    second_response = client.post(
        "/api/v1/workspaces", headers=first_headers, json={"name": "Second"}
    )
    assert second_response.status_code == 200, second_response.text
    second = second_response.json()
    second_wid, second_headers = second["workspace_id"], auth(second["access_token"])

    other_ticket = client.post(
        f"/api/v1/workspaces/{second_wid}/tickets",
        headers=second_headers,
        json={"subject": "Other tenant", "body": "secret details"},
    )
    assert other_ticket.status_code == 201, other_ticket.text
    other_id = other_ticket.json()["id"]

    # The session's workspace must match the path.
    assert client.get(f"/api/v1/workspaces/{second_wid}/tickets", headers=first_headers).status_code == 403

    # Rows from the other workspace are invisible through this workspace's paths.
    assert client.get(f"/api/v1/workspaces/{first_wid}/tickets", headers=first_headers).json() == []
    for path in (
        f"/api/v1/workspaces/{first_wid}/tickets/{other_id}",
        f"/api/v1/workspaces/{first_wid}/tickets/{other_id}/messages",
    ):
        assert client.get(path, headers=first_headers).status_code == 404
    assert client.patch(
        f"/api/v1/workspaces/{first_wid}/tickets/{other_id}",
        headers=first_headers,
        json={"status": "closed"},
    ).status_code == 404
    assert client.post(
        f"/api/v1/workspaces/{first_wid}/tickets/{other_id}/messages",
        headers=first_headers,
        json={"body": "should not land"},
    ).status_code == 404

    assert all(event.workspace_id == second_wid for event in _events(db_session, second_wid))
    assert _events(db_session, first_wid) == []


def test_static_support_routes_are_not_shadowed_by_ticket_id(client):
    """Static sub-resources must resolve to their own handlers, not /{ticket_id}."""
    tokens = bootstrap(client, "Routes", "routes@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/tickets"
    for suffix in (
        "search?q=anything", "counts", "assignees", "saved-replies", "macros",
        "sla-policies", "business-hours", "escalation-rules", "csat",
    ):
        response = client.get(f"{base}/{suffix}", headers=headers)
        assert response.status_code == 200, (suffix, response.status_code, response.text)


def test_ticket_bad_payloads_and_missing_rows(client):
    tokens = bootstrap(client, "BadInput", "bad@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/tickets"

    bad_creates = (
        {"subject": "", "body": "body"},
        {"subject": "subject", "body": "   "},
        {"subject": "subject", "body": "body", "priority": "critical"},
        {"subject": "subject", "body": "body", "workspace_id": "other"},
        {"subject": "subject", "body": "body", "author_id": "someone-else"},
        {"subject": "subject", "body": "body", "contact_id": "missing-contact"},
        {"subject": "subject", "body": "body", "assignee_id": "missing-user"},
    )
    for payload in bad_creates:
        response = client.post(base, headers=headers, json=payload)
        assert response.status_code == 422, (payload, response.text)

    valid = client.post(base, headers=headers, json={"subject": "Valid", "body": "body"})
    assert valid.status_code == 201, valid.text
    ticket_id = valid.json()["id"]

    bad_patches = (
        {"status": "bogus"},
        {"priority": "critical"},
        {"assignee_id": "missing-user"},
        {"contact_id": "missing-contact"},
    )
    for payload in bad_patches:
        response = client.patch(f"{base}/{ticket_id}", headers=headers, json=payload)
        assert response.status_code == 422, (payload, response.text)

    assert client.post(
        f"{base}/{ticket_id}/messages", headers=headers, json={"body": ""}
    ).status_code == 422
    assert client.post(
        f"{base}/{ticket_id}/messages",
        headers=headers,
        json={"body": "ok", "author_id": "spoofed"},
    ).status_code == 422

    assert client.get(f"{base}/does-not-exist", headers=headers).status_code == 404
    assert client.patch(
        f"{base}/does-not-exist", headers=headers, json={"status": "closed"}
    ).status_code == 404
    assert client.post(
        f"{base}/does-not-exist/messages", headers=headers, json={"body": "hello"}
    ).status_code == 404
    assert client.get(base, headers=auth("garbage")).status_code == 401
