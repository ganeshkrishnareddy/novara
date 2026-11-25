"""Phase 2 P2-2: multi-workspace isolation across the core API.

Two independently registered workspace owners are used. Every assertion checks
that a session can only see its own workspace's rows, and that naming another
workspace in the path is rejected even with a valid token.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from novara_core.models import Contact, Event, WorkspaceMember
from novara_core.security import create_session, hash_password

from .conftest import auth, bootstrap


@pytest.fixture()
def two_workspaces(client):
    first = bootstrap(client, workspace_name="First workspace")
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "second.workspace@example.test",
            "display_name": "Second owner",
            "password": "Password123!",
        },
    )
    assert registered.status_code == 200, registered.text
    second = registered.json()
    return first, second


def _create_contact(client, wid, headers, email):
    response = client.post(
        f"/api/v1/workspaces/{wid}/contacts",
        headers=headers,
        json={"email": email, "full_name": "Isolation Test", "company_name": "First Co"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_contact_lists_and_details_are_isolated(client, two_workspaces):
    first, second = two_workspaces
    w1, h1 = first["workspace_id"], auth(first["access_token"])
    w2, h2 = second["workspace_id"], auth(second["access_token"])

    contact = _create_contact(client, w1, h1, "isolation.first@example.test")
    assert client.get(f"/api/v1/workspaces/{w2}/contacts", headers=h2).json() == []
    detail = client.get(f"/api/v1/workspaces/{w2}/contacts/{contact['id']}", headers=h2)
    assert detail.status_code == 404
    assert client.get(f"/api/v1/workspaces/{w1}/contacts", headers=h2).status_code == 403
    assert client.get(f"/api/v1/workspaces/{w2}/contacts", headers=h1).status_code == 403


def test_cross_workspace_membership_is_not_trusted(client, two_workspaces, db_session):
    first, second = two_workspaces
    w2 = second["workspace_id"]
    foreign_user_id = db_session.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == first["workspace_id"])
    ).scalar_one().user_id
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "second.workspace@example.test",
            "password": "Password123!",
            "workspace_id": w2,
        },
    )
    assert response.status_code == 200
    assert response.json()["workspace_id"] == w2
    # Even a validly-shaped session for a workspace the user does not belong to
    # is rejected by the principal dependency (fail closed).
    _, access, _ = create_session(db_session, user_id=foreign_user_id, workspace_id=w2)
    db_session.commit()
    forged = client.get(f"/api/v1/workspaces/{w2}/contacts", headers=auth(access))
    assert forged.status_code == 403
    assert "no active membership" in forged.text


def test_events_and_members_are_not_visible_across_workspaces(client, two_workspaces, db_session):
    first, second = two_workspaces
    w1, h1 = first["workspace_id"], auth(first["access_token"])
    w2, h2 = second["workspace_id"], auth(second["access_token"])
    _create_contact(client, w1, h1, "events.first@example.test")

    first_events = client.get(f"/api/v1/workspaces/{w1}/events", headers=h1).json()
    assert first_events
    assert client.get(f"/api/v1/workspaces/{w2}/events", headers=h2).json() == []
    assert client.get(f"/api/v1/workspaces/{w1}/events", headers=h2).status_code == 403
    assert client.get(f"/api/v1/workspaces/{w1}/members", headers=h2).status_code == 403

    second_events = db_session.execute(
        select(Event).where(Event.workspace_id == w2)
    ).scalars().all()
    assert second_events == []


def test_same_email_in_two_workspaces_creates_two_distinct_contacts(client, two_workspaces, db_session):
    first, second = two_workspaces
    w1, h1 = first["workspace_id"], auth(first["access_token"])
    w2, h2 = second["workspace_id"], auth(second["access_token"])
    email = "shared.email@example.test"

    a = _create_contact(client, w1, h1, email)
    b = _create_contact(client, w2, h2, email)
    assert a["id"] != b["id"]
    rows = db_session.execute(select(Contact).where(Contact.email == email)).scalars().all()
    assert {row.workspace_id for row in rows} == {w1, w2}
    assert len(rows) == 2


def test_password_hash_is_not_shared_between_workspaces(client, two_workspaces, db_session):
    """A workspace boundary does not weaken credential storage."""
    from novara_core.models import User

    first, second = two_workspaces
    users = db_session.execute(
        select(User).where(User.email.in_({"owner@example.com", "second.workspace@example.test"}))
    ).scalars().all()
    assert len(users) == 2
    assert all(user.password_hash.startswith("bcrypt-sha256$") for user in users)
    assert users[0].password_hash != users[1].password_hash
    assert hash_password("Password123!") != users[0].password_hash
