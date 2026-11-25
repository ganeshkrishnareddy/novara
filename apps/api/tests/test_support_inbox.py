"""Customer Inbox P0 deep completion.

Feature IDs: CW-001, CW-002, CW-003, CW-004, CW-009, CW-011, CW-018.
Every assertion reads persisted rows or the public HTTP API. No reply triggers
an external send and no response body containing a token is logged.
"""

from __future__ import annotations

from sqlalchemy import func, select

from novara_core.database import Base
from novara_core.main import app
from novara_core.models import Contact, Event, User, WorkspaceMember, new_id, now
from novara_core.modules import support
from novara_core.security import hash_password

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/tickets"


def _second_member(db, workspace_id, *, email="teammate@example.com", status="active"):
    user = User(
        id=new_id(),
        email=email,
        display_name="Teammate",
        password_hash=hash_password("Password123!"),
    )
    db.add(user)
    db.add(WorkspaceMember(
        id=new_id(), workspace_id=workspace_id, user_id=user.id,
        role="member", status=status,
    ))
    db.commit()
    db.refresh(user)
    return user


def _second_workspace(client, headers, name="Second"):
    """First-run bootstrap is single use; additional workspaces come from the API."""
    response = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": name}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["workspace_id"], auth(body["access_token"])


def _events(db, workspace_id):
    return db.execute(
        select(Event).where(Event.workspace_id == workspace_id).order_by(Event.seq)
    ).scalars().all()


def _event_types(db, workspace_id):
    return [event.event_type for event in _events(db, workspace_id)]


def _create(client, wid, headers, **overrides):
    payload = {"subject": "Invoice question", "body": "Please explain the charge"}
    payload.update(overrides)
    response = client.post(BASE.format(wid=wid), headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_shared_inbox_is_workspace_scoped_audited_and_local_only(client, db_session):
    """CW-001: contact:read sees only this workspace's tickets with context."""
    tokens = bootstrap(client, "Inbox", "inbox@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = Contact(
        id=new_id(), workspace_id=wid, email="customer@example.com",
        full_name="Customer One",
    )
    db_session.add(contact)
    db_session.commit()

    ticket = _create(
        client, wid, headers,
        contact_id=contact.id, priority="high",
        origin_channel="web_form", conversation_type="billing",
    )
    listed = client.get(BASE.format(wid=wid), headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["subject"] == "Invoice question"
    assert row["contact_id"] == contact.id
    assert row["priority"] == "high"
    assert row["status"] == "open"
    assert all(event.workspace_id == wid for event in _events(db_session, wid))
    assert support.TICKET_CREATED in _event_types(db_session, wid)

    # A reply is recorded locally: no campaign or broadcast is created.
    reply = client.post(
        BASE.format(wid=wid) + f"/{ticket['id']}/messages",
        headers=headers, json={"body": "Checking the invoice now"},
    )
    assert reply.status_code == 201, reply.text
    for table in ("campaigns", "broadcast_campaigns"):
        model = Base.metadata.tables[table]
        assert db_session.execute(select(func.count()).select_from(model)).scalar_one() == 0

    # Another workspace never appears in this queue.
    other_wid, other_headers = _second_workspace(client, headers, "Other Inbox")
    _create(client, other_wid, other_headers, subject="Other tenant")
    assert [row["subject"] for row in client.get(BASE.format(wid=wid), headers=headers).json()] == [
        "Invoice question"
    ]
    assert client.get(BASE.format(wid=other_wid), headers=headers).status_code == 403


def test_conversation_persists_origin_type_and_four_named_events(client, db_session):
    """CW-002: origin/type metadata and named lifecycle events persist."""
    tokens = bootstrap(client, "Lifecycle", "lifecycle@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = BASE.format(wid=wid)

    bad = client.post(
        base, headers=headers,
        json={"subject": "s", "body": "b", "origin_channel": "carrier_pigeon"},
    )
    assert bad.status_code == 422
    bad = client.post(
        base, headers=headers,
        json={"subject": "s", "body": "b", "conversation_type": "unknown"},
    )
    assert bad.status_code == 422

    ticket = _create(
        client, wid, headers,
        origin_channel="email", conversation_type="incident",
    )
    assert ticket["origin_channel"] == "email"
    assert ticket["conversation_type"] == "incident"
    ticket_id = ticket["id"]

    assert client.get(base + f"/{ticket_id}", headers=headers).json()["ticket"]["origin_channel"] == "email"
    patched = client.patch(base + f"/{ticket_id}", headers=headers, json={"status": "pending"})
    assert patched.status_code == 200, patched.text
    client.post(base + f"/{ticket_id}/messages", headers=headers, json={"body": "Working on it"})
    client.patch(base + f"/{ticket_id}", headers=headers, json={"status": "resolved"})

    types = _event_types(db_session, wid)
    for expected in (
        support.TICKET_CREATED, support.TICKET_UPDATED,
        support.TICKET_STATUS_CHANGED, support.TICKET_MESSAGE_ADDED,
    ):
        assert expected in types
    created_event = next(e for e in _events(db_session, wid) if e.event_type == support.TICKET_CREATED)
    assert created_event.payload["origin_channel"] == "email"
    assert created_event.payload["conversation_type"] == "incident"

    # Cross-workspace identifiers never resolve to a local row.
    other_wid, other_headers = _second_workspace(client, headers, "Lifecycle Other")
    assert client.get(
        BASE.format(wid=other_wid) + f"/{ticket_id}", headers=other_headers
    ).status_code == 404


def test_public_reply_has_direction_channel_order_and_verified_actor(client, db_session):
    """CW-003: replies carry direction/channel, thread order and the actor id."""
    tokens = bootstrap(client, "Replies", "replies@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    me = client.get("/api/v1/auth/me", headers=headers)
    actor_id = me.json()["user"]["id"]
    ticket = _create(client, wid, headers)
    base = BASE.format(wid=wid) + f"/{ticket['id']}/messages"

    for body, direction, channel in (
        ("How can we help?", "inbound", "web_form"),
        ("We can help", "outbound", "local"),
        ("Checking with the team", "outbound", "local"),
    ):
        response = client.post(
            base, headers=headers,
            json={"body": body, "direction": direction, "channel": channel},
        )
        assert response.status_code == 201, response.text
        assert response.json()["direction"] == direction
        assert response.json()["channel"] == channel

    assert client.post(
        base, headers=headers, json={"body": "x", "direction": "carrier_pigeon"}
    ).status_code == 422
    assert client.post(
        base, headers=headers, json={"body": "x", "channel": "carrier_pigeon"}
    ).status_code == 422

    thread = client.get(base, headers=headers).json()
    assert [row["body"] for row in thread] == [
        "How can we help?", "We can help", "Checking with the team"
    ]
    assert all(row["author_id"] == actor_id for row in thread)
    assert all(row["created_at"] for row in thread)
    assert all(row["ticket_id"] == ticket["id"] for row in thread)
    added = [e for e in _events(db_session, wid) if e.event_type == support.TICKET_MESSAGE_ADDED]
    assert len(added) == 3
    assert added[0].payload["direction"] == "inbound"
    assert added[0].payload["channel"] == "web_form"
    assert db_session.execute(
        select(func.count()).select_from(Base.metadata.tables["campaigns"])
    ).scalar_one() == 0


def test_assignment_requires_active_member_and_audits_reassignment(client, db_session):
    """CW-004: only active same-workspace members can own a conversation."""
    tokens = bootstrap(client, "Assign", "assign@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    me = client.get("/api/v1/auth/me", headers=headers).json()
    owner_id = me["user"]["id"]
    teammate = _second_member(db_session, wid)
    inactive = _second_member(
        db_session, wid, email="inactive@example.com", status="inactive"
    )
    other_wid, _ = _second_workspace(client, headers, "Assign Other")
    # A different user who belongs only to another workspace. A second workspace
    # created by the same owner is not an outsider: it is one identity in two scopes.
    outsider = _second_member(db_session, other_wid, email="outsider@example.com")

    assignees = client.get(BASE.format(wid=wid) + "/assignees", headers=headers)
    assert assignees.status_code == 200, assignees.text
    assignee_ids = {row["id"] for row in assignees.json()}
    assert owner_id in assignee_ids and teammate.id in assignee_ids
    assert inactive.id not in assignee_ids and outsider.id not in assignee_ids

    ticket = _create(client, wid, headers)
    base = BASE.format(wid=wid) + f"/{ticket['id']}"

    for invalid in ("missing-user", outsider.id, inactive.id):
        denied = client.patch(base, headers=headers, json={"assignee_id": invalid})
        assert denied.status_code == 422, (invalid, denied.text)

    assigned = client.patch(base, headers=headers, json={"assignee_id": teammate.id})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assignee_id"] == teammate.id
    assert client.get(BASE.format(wid=wid) + "?mine=true", headers=headers).json() == []
    assert [
        row["id"] for row in client.get(
            BASE.format(wid=wid) + f"?assignee_id={teammate.id}", headers=headers
        ).json()
    ] == [ticket["id"]]

    reassigned = client.patch(base, headers=headers, json={"assignee_id": owner_id})
    assert reassigned.status_code == 200, reassigned.text
    assert len(client.get(BASE.format(wid=wid) + "?mine=true", headers=headers).json()) == 1

    cleared = client.patch(base, headers=headers, json={"assignee_id": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["assignee_id"] is None

    assignment_events = [
        e for e in _events(db_session, wid) if e.event_type == support.TICKET_ASSIGNED
    ]
    assert len(assignment_events) == 3
    assert assignment_events[0].payload["to"] == teammate.id
    assert assignment_events[1].payload["from"] == teammate.id
    assert assignment_events[1].payload["to"] == owner_id
    assert all(e.payload["actor_id"] == owner_id for e in assignment_events)


def test_status_transitions_and_reasons_are_validated_and_audited(client, db_session):
    """CW-009: only four statuses persist and each change is an audit event."""
    tokens = bootstrap(client, "Status", "status@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    ticket = _create(client, wid, headers)
    base = BASE.format(wid=wid) + f"/{ticket['id']}"

    for invalid in ("snoozed", "bogus", ""):
        assert client.patch(base, headers=headers, json={"status": invalid}).status_code == 422

    for status_value, reason in (
        ("pending", "awaiting_customer"),
        ("resolved", "resolved"),
        ("closed", None),
        ("open", "reopened"),
    ):
        payload = {"status": status_value}
        if reason:
            payload["status_reason"] = reason
        response = client.patch(base, headers=headers, json=payload)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status_value

    assert client.patch(base, headers=headers, json={"status_reason": "bogus"}).status_code == 422
    changes = [
        e for e in _events(db_session, wid) if e.event_type == support.TICKET_STATUS_CHANGED
    ]
    assert [e.payload["to"] for e in changes] == ["pending", "resolved", "closed", "open"]
    assert changes[0].payload["reason"] == "awaiting_customer"
    assert changes[-1].payload["reason"] == "reopened"
    assert client.get(BASE.format(wid=wid) + "?status=open", headers=headers).json()


def test_priority_persists_filters_and_rejects_unknown_values(client):
    """CW-011: exactly four priorities persist, filter and validate."""
    tokens = bootstrap(client, "Priority", "priority@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = BASE.format(wid=wid)
    for value in ("low", "normal", "high", "urgent"):
        assert _create(client, wid, headers, subject=value, priority=value)["priority"] == value
    assert client.post(base, headers=headers, json={
        "subject": "bad", "body": "body", "priority": "critical"
    }).status_code == 422
    for value in ("low", "normal", "high", "urgent"):
        rows = client.get(base + f"?priority={value}", headers=headers).json()
        assert [row["subject"] for row in rows] == [value]
    assert client.get(base + "?priority=bogus", headers=headers).status_code == 422
    counts = client.get(base + "/counts", headers=headers).json()
    assert counts == {
        "total": 4, "open": 4, "pending": 0, "resolved": 0,
        "closed": 0, "unassigned": 4, "urgent": 1,
    }


def test_pre_chat_identity_reuses_single_crm_contact(client, db_session):
    """CW-018: identity capture upserts the existing CRM contact, never a duplicate."""
    tokens = bootstrap(client, "Identity", "identity@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    identify = BASE.format(wid=wid) + "/identify"

    assert client.post(
        identify, headers=headers, json={"email": "not-an-email"}
    ).status_code == 422
    first = client.post(
        identify, headers=headers,
        json={"email": "Visitor@Example.com", "full_name": "Visitor", "company_name": "Acme"},
    )
    assert first.status_code == 201, first.text
    assert first.json()["created"] is True
    assert first.json()["existing_conversations"] == 0
    contact_id = first.json()["contact_id"]

    second = client.post(
        identify, headers=headers,
        json={"email": "visitor@example.com", "full_name": "Changed name"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["created"] is False
    assert second.json()["contact_id"] == contact_id

    assert client.post(
        BASE.format(wid=wid), headers=headers,
        json={"subject": "s", "body": "b", "contact_id": "missing-contact"},
    ).status_code == 422
    ticket = _create(client, wid, headers, contact_id=contact_id)
    third = client.post(identify, headers=headers, json={"email": "visitor@example.com"})
    assert third.json()["existing_conversations"] == 1

    contacts = db_session.execute(
        select(Contact).where(Contact.workspace_id == wid, Contact.email == "visitor@example.com")
    ).scalars().all()
    assert len(contacts) == 1
    assert contacts[0].source == "pre_chat_identity"
    identified = [
        e for e in _events(db_session, wid)
        if e.event_type == support.TICKET_CONTACT_IDENTIFIED
    ]
    assert len(identified) == 1
    assert identified[0].entity_id == contact_id
    assert ticket["contact_id"] == contact_id


def test_queue_counts_and_realtime_stream_route_are_registered(client):
    """CW-001: live queue aggregates are available and the SSE route exists."""
    tokens = bootstrap(client, "Queue", "queue@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    assert client.get(BASE.format(wid=wid) + "/counts", headers=headers).json() == {
        "total": 0, "open": 0, "pending": 0, "resolved": 0,
        "closed": 0, "unassigned": 0, "urgent": 0,
    }
    _create(client, wid, headers, priority="urgent")
    ticket = _create(client, wid, headers)
    client.patch(
        BASE.format(wid=wid) + f"/{ticket['id']}", headers=headers, json={"status": "pending"}
    )
    counts = client.get(BASE.format(wid=wid) + "/counts", headers=headers).json()
    assert counts["total"] == 2
    assert counts["open"] == 1
    assert counts["pending"] == 1
    assert counts["unassigned"] == 2
    assert counts["urgent"] == 1

    paths = set(app.openapi()["paths"])
    assert BASE.format(wid="{workspace_id}") + "/stream" in paths
    # Read one frame only; the feed is intentionally long-lived.
    with client.stream("GET", BASE.format(wid=wid) + "/stream", headers=headers) as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        for line in stream.iter_lines():
            assert line.startswith("data: ") or line.startswith(": ")
            break
