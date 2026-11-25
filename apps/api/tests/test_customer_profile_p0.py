"""Named acceptance tests for the P0 customer-profile cluster.

CW-014: a support conversation belongs to exactly one existing workspace
contact and the contact profile can surface those conversations without a
second identity store. CW-129: one user may belong to several workspaces and
every support row is readable only through an active membership with the
right role. No route count, menu item or 200 response alone closes a feature.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.events import MEMBER_UPDATED
from novara_core.models import Event
from novara_core.modules import support

from .conftest import auth, bootstrap


def _member(client, wid, owner_headers, email, role, name):
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


def _ticket(client, wid, headers, contact_id=None, subject="Profile question"):
    response = client.post(
        f"/api/v1/workspaces/{wid}/tickets",
        headers=headers,
        json={
            "subject": subject, "body": "Question about the local install",
            "contact_id": contact_id, "origin_channel": "web_form",
            "conversation_type": "question",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# CW-014 — one contact identity behind the support profile
# ---------------------------------------------------------------------------


def test_ticket_belongs_to_exactly_one_existing_workspace_contact(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = client.post(
        f"/api/v1/workspaces/{wid}/contacts", headers=headers,
        json={"full_name": "Grace Hopper", "email": "grace@example.com"},
    ).json()
    cid = contact["id"]

    rejected = client.post(
        f"/api/v1/workspaces/{wid}/tickets", headers=headers,
        json={"subject": "Bad link", "body": "x", "contact_id": "missing-contact"},
    )
    assert rejected.status_code == 422, rejected.text

    ticket = _ticket(client, wid, headers, cid)
    assert ticket["contact_id"] == cid

    second = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Other account"}
    ).json()
    other_wid = second["workspace_id"]
    other_headers = auth(second["access_token"])
    assert client.get(
        f"/api/v1/workspaces/{other_wid}/tickets", headers=other_headers,
        params={"contact_id": cid},
    ).status_code == 422


def test_contact_profile_surfaces_only_its_linked_conversations(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}"
    one = client.post(base + "/contacts", headers=headers,
                      json={"full_name": "Ada One", "email": "one@example.com"}).json()
    two = client.post(base + "/contacts", headers=headers,
                      json={"full_name": "Ben Two", "email": "two@example.com"}).json()
    first = _ticket(client, wid, headers, one["id"], "Ada's issue")
    _ticket(client, wid, headers, two["id"], "Ben's issue")

    profile = client.get(base + "/tickets", headers=headers,
                         params={"contact_id": one["id"]})
    assert profile.status_code == 200, profile.text
    ids = [row["id"] for row in profile.json()]
    assert ids == [first["id"]]

    note = client.post(base + f"/contacts/{one['id']}/notes", headers=headers,
                       json={"contact_id": one["id"], "body": "Called back locally."})
    assert note.status_code == 201, note.text
    timeline = client.get(base + f"/contacts/{one['id']}/timeline", headers=headers)
    assert timeline.status_code == 200

    # Pre-chat identification reuses the same contact and surfaces its history.
    identified = client.post(base + "/tickets/identify", headers=headers,
                             json={"email": "one@example.com", "full_name": "Ada One"})
    assert identified.status_code == 201, identified.text
    assert identified.json()["contact_id"] == one["id"]
    assert identified.json()["created"] is False
    contacts = client.get(base + "/contacts", headers=headers).json()
    assert len([row for row in contacts if row["email"] == "one@example.com"]) == 1


# ---------------------------------------------------------------------------
# CW-129 — membership lifecycle and active-membership enforcement
# ---------------------------------------------------------------------------


def test_one_user_can_belong_to_multiple_workspaces(client):
    tokens = bootstrap(client)
    wid_a, headers_a = tokens["workspace_id"], auth(tokens["access_token"])
    second = client.post(
        "/api/v1/workspaces", headers=headers_a, json={"name": "Second account"}
    )
    assert second.status_code == 200, second.text
    wid_b = second.json()["workspace_id"]
    headers_b = auth(second.json()["access_token"])

    for wid, headers in ((wid_a, headers_a), (wid_b, headers_b)):
        invited = client.post(
            f"/api/v1/workspaces/{wid}/invitations", headers=headers,
            json={"email": "multi@example.com", "role": "sales_rep"},
        )
        assert invited.status_code == 200, invited.text
        if wid == wid_a:
            raw_a = invited.json()["invite_token"]
        else:
            raw_b = invited.json()["invite_token"]

    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "multi@example.com", "password": "Password123!",
              "display_name": "Multi Member"},
    )
    assert registered.status_code == 200, registered.text
    # A freshly registered identity can accept invitations for both accounts;
    # each acceptance returns a token scoped to that one workspace.
    registration_headers = auth(registered.json()["access_token"])
    accepted_a = client.post("/api/v1/invitations/accept", headers=registration_headers,
                             json={"token": raw_a})
    assert accepted_a.status_code == 200, accepted_a.text
    accepted_b = client.post("/api/v1/invitations/accept", headers=registration_headers,
                             json={"token": raw_b})
    assert accepted_b.status_code == 200, accepted_b.text
    rep_a = auth(accepted_a.json()["access_token"])
    rep_b = auth(accepted_b.json()["access_token"])

    for wid, headers in ((wid_a, rep_a), (wid_b, rep_b)):
        me = client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200 and me.json()["workspace_id"] == wid
        assert client.get(f"/api/v1/workspaces/{wid}/tickets", headers=headers).status_code == 200
    assert client.get(f"/api/v1/workspaces/{wid_b}/tickets", headers=rep_a).status_code == 403

    listed = client.get(f"/api/v1/workspaces/{wid_a}/members", headers=headers_a)
    assert any(row["email"] == "multi@example.com" for row in listed.json())
    listed_b = client.get(f"/api/v1/workspaces/{wid_b}/members", headers=headers_b)
    assert any(row["email"] == "multi@example.com" for row in listed_b.json())


def test_suspension_revokes_support_access_immediately_and_can_be_reversed(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    rep = _member(client, wid, headers, "rep@example.com", "sales_rep", "Rep")
    members = client.get(f"/api/v1/workspaces/{wid}/members", headers=headers).json()
    rep_row = next(row for row in members if row["email"] == "rep@example.com")
    path = f"/api/v1/workspaces/{wid}/members/{rep_row['user_id']}"

    assert client.get(f"/api/v1/workspaces/{wid}/tickets", headers=rep).status_code == 200
    suspended = client.patch(path, headers=headers, json={"status": "suspended"})
    assert suspended.status_code == 200 and suspended.json()["status"] == "suspended"
    assert client.get(f"/api/v1/workspaces/{wid}/tickets", headers=rep).status_code == 403
    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=rep).status_code == 403

    events = db_session.execute(
        select(Event).where(Event.workspace_id == wid, Event.event_type == MEMBER_UPDATED)
    ).scalars().all()
    assert len(events) == 1
    assert events[0].payload["changes"] == {"status": "suspended"}

    reactivated = client.patch(path, headers=headers, json={"status": "active"})
    assert reactivated.status_code == 200 and reactivated.json()["status"] == "active"
    assert client.get(f"/api/v1/workspaces/{wid}/tickets", headers=rep).status_code == 200


def test_membership_changes_validate_roles_status_and_last_owner(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    members = client.get(f"/api/v1/workspaces/{wid}/members", headers=headers).json()
    owner = next(row for row in members if row["role"] == "owner")
    rep = _member(client, wid, headers, "rep@example.com", "sales_rep", "Rep")
    rep_members = client.get(f"/api/v1/workspaces/{wid}/members", headers=headers).json()
    rep_row = next(row for row in rep_members if row["email"] == "rep@example.com")
    rep_path = f"/api/v1/workspaces/{wid}/members/{rep_row['user_id']}"
    owner_path = f"/api/v1/workspaces/{wid}/members/{owner['user_id']}"

    assert client.patch(rep_path, headers=headers, json={"status": "snoozed"}).status_code == 422
    assert client.patch(rep_path, headers=headers, json={"role": "owner"}).status_code == 422
    assert client.patch(rep_path, headers=headers, json={}).status_code == 422
    assert client.patch(rep_path, headers=rep, json={"status": "suspended"}).status_code == 403
    assert client.patch(f"/api/v1/workspaces/{wid}/members/missing", headers=headers,
                        json={"status": "suspended"}).status_code == 404

    promoted = client.patch(rep_path, headers=headers, json={"role": "sales_manager"})
    assert promoted.status_code == 200 and promoted.json()["role"] == "sales_manager"
    assert client.patch(owner_path, headers=headers,
                        json={"status": "suspended"}).status_code == 409
    assert client.patch(owner_path, headers=headers,
                        json={"role": "sales_rep"}).status_code == 409


def test_support_list_filters_reject_foreign_contact_ids(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    assert support.TICKET_CREATED
    foreign = client.get(f"/api/v1/workspaces/{wid}/tickets", headers=headers,
                         params={"contact_id": "not-a-real-contact"})
    assert foreign.status_code == 422, foreign.text
