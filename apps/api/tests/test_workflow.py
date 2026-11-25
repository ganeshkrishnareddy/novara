from __future__ import annotations

import pytest
from sqlalchemy import select

from novara_core.events import (
    CONTACT_IDENTIFIED,
    CONTACT_UPDATED,
    LEAD_CREATED,
    NOTIFICATION_CREATED,
    OUTREACH_APPROVED,
    OUTREACH_DRAFT_CREATED,
    TASK_CREATED,
)
from novara_core.models import (
    Contact,
    Event,
    Lead,
    Notification,
    OutreachDraft,
    Task,
    User,
    Workspace,
    WorkspaceMember,
    new_id,
    now,
)
from novara_core.schemas import WebsiteSubmission
from novara_core.security import hash_password
from novara_core.workflow import approve_outreach_draft, handle_website_form

from .conftest import auth, bootstrap


def make_owner(db, name="Acme", email="owner@example.com"):
    user = User(
        id=new_id(), email=email, display_name="Owner",
        password_hash=hash_password("Password123!"), created_at=now(),
    )
    workspace = Workspace(id=new_id(), name=name, created_at=now())
    db.add_all([user, workspace])
    db.flush()
    member = WorkspaceMember(
        id=new_id(), workspace_id=workspace.id, user_id=user.id,
        role="owner", status="active", created_at=now(),
    )
    db.add(member)
    db.flush()
    db.commit()
    return workspace, user, member


def make_member(db, workspace_id, role="member", email="member@example.com"):
    user = User(
        id=new_id(), email=email, display_name="Member",
        password_hash=hash_password("Password123!"), created_at=now(),
    )
    db.add(user)
    db.flush()
    member = WorkspaceMember(
        id=new_id(), workspace_id=workspace_id, user_id=user.id,
        role=role, status="active", created_at=now(),
    )
    db.add(member)
    db.flush()
    db.commit()
    return user, member


def submission(**overrides):
    data = {
        "submission_id": "form-001",
        "email": "jane@example.com",
        "full_name": "Jane Doe",
        "company": "Example Ltd",
        "message": "Please get in touch",
        "source": "website_form",
    }
    data.update(overrides)
    return WebsiteSubmission(**data)


def events_for(db, workspace_id):
    return db.execute(
        select(Event).where(Event.workspace_id == workspace_id).order_by(Event.seq)
    ).scalars().all()


# --------------------------------------------------------------------------
# Service-level workflow tests (original scenarios preserved)
# --------------------------------------------------------------------------


def test_intake_creates_one_identity_and_linked_records(db_session):
    workspace, user, _ = make_owner(db_session)

    result = handle_website_form(
        db_session, workspace_id=workspace.id, submission=submission()
    )

    assert result.created_contact is True
    assert db_session.get(Contact, result.contact_id) is not None
    assert db_session.get(Lead, result.lead_id).contact_id == result.contact_id
    assert db_session.get(Task, result.task_id).contact_id == result.contact_id
    assert db_session.get(Notification, result.notification_id).contact_id == result.contact_id
    assert db_session.get(OutreachDraft, result.draft_id).status == "draft"

    events = events_for(db_session, workspace.id)
    assert [event.event_type for event in events] == [
        CONTACT_IDENTIFIED, LEAD_CREATED, TASK_CREATED, NOTIFICATION_CREATED, OUTREACH_DRAFT_CREATED,
    ]
    assert {event.correlation_id for event in events} == {result.correlation_id}
    assert all(event.workspace_id == workspace.id for event in events)


def test_intake_is_idempotent_for_the_same_submission(db_session):
    workspace, _, _ = make_owner(db_session)

    first = handle_website_form(db_session, workspace_id=workspace.id, submission=submission())
    second = handle_website_form(db_session, workspace_id=workspace.id, submission=submission())

    assert first.model_dump() == second.model_dump()
    assert len(db_session.execute(select(Contact)).scalars().all()) == 1
    assert len(db_session.execute(select(Task)).scalars().all()) == 1
    assert len(events_for(db_session, workspace.id)) == 5


def test_same_email_updates_one_contact_instead_of_duplicating(db_session):
    workspace, _, _ = make_owner(db_session)

    handle_website_form(db_session, workspace_id=workspace.id, submission=submission(submission_id="form-001"))
    second = handle_website_form(
        db_session,
        workspace_id=workspace.id,
        submission=submission(submission_id="form-002", full_name="Jane Q. Doe"),
    )

    assert second.created_contact is False
    assert db_session.execute(select(Contact)).scalars().one().full_name == "Jane Doe"
    types = [event.event_type for event in events_for(db_session, workspace.id)]
    assert CONTACT_UPDATED in types
    assert types.count(CONTACT_IDENTIFIED) == 1


def test_outreach_requires_an_authorised_approver_and_is_never_sent(db_session):
    workspace, _, _ = make_owner(db_session)
    member, _ = make_member(db_session, workspace.id, role="read_only", email="member@example.com")
    result = handle_website_form(db_session, workspace_id=workspace.id, submission=submission())

    with pytest.raises(PermissionError):
        approve_outreach_draft(
            db_session, workspace_id=workspace.id, draft_id=result.draft_id, actor_user_id=member.id
        )
    approved = approve_outreach_draft(
        db_session, workspace_id=workspace.id, draft_id=result.draft_id,
        actor_user_id=db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one().id,
    )
    assert approved.status == "approved"
    assert approved.approved_at is not None
    assert OUTREACH_APPROVED in [e.event_type for e in events_for(db_session, workspace.id)]
    assert "sent" not in approved.status


def test_workspace_isolation(db_session):
    first, _, _ = make_owner(db_session, "First")
    second, _, _ = make_owner(db_session, "Second", email="second@example.com")

    handle_website_form(db_session, workspace_id=first.id, submission=submission())

    assert db_session.execute(select(Contact).where(Contact.workspace_id == first.id)).scalars().one()
    assert db_session.execute(select(Contact).where(Contact.workspace_id == second.id)).scalars().all() == []
    assert events_for(db_session, second.id) == []


# --------------------------------------------------------------------------
# API end-to-end and security scenarios
# --------------------------------------------------------------------------


def test_api_end_to_end(client):
    tokens = bootstrap(client)
    token = tokens["access_token"]
    wid = tokens["workspace_id"]
    headers = auth(token)

    intake = client.post(
        f"/api/v1/workspaces/{wid}/intake/website-form",
        headers=headers,
        json={"submission_id": "web-1", "email": "lead@example.com", "full_name": "Lead"},
    )
    assert intake.status_code == 201, intake.text
    result = intake.json()

    contacts = client.get(f"/api/v1/workspaces/{wid}/contacts", headers=headers).json()
    assert len(contacts) == 1
    assert contacts[0]["email"] == "lead@example.com"

    timeline = client.get(
        f"/api/v1/workspaces/{wid}/contacts/{result['contact_id']}/timeline", headers=headers
    ).json()
    assert len(timeline) == 5

    approved = client.post(
        f"/api/v1/workspaces/{wid}/outreach-drafts/{result['draft_id']}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    audit = client.get(f"/api/v1/workspaces/{wid}/events", headers=headers).json()
    assert len(audit) == 6
    assert client.get("/health").json()["product"] == "NOVARA"


def test_no_route_sends_external_messages():
    from novara_core.main import app

    # OpenAPI lists every route including lazily included module routers;
    # app.routes may contain wrapper objects with no .path attribute.
    paths = set(app.openapi()["paths"])
    paths.update(getattr(route, "path", "") for route in app.routes)
    joined = " ".join(paths).lower()
    assert "/send" not in joined
    assert "publish" not in joined
    assert "email/send" not in joined


def test_unauthenticated_request_is_rejected(client):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    response = client.get(f"/api/v1/workspaces/{wid}/contacts")
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid or expired access token"
    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=auth("garbage")).status_code == 401


def test_logout_revokes_token_and_refresh_rotates(client):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    headers = auth(tokens["access_token"])

    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["access_token"] != tokens["access_token"]
    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=headers).status_code == 401

    new_headers = auth(new_tokens["access_token"])
    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=new_headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=new_headers).json()["revoked"] is True
    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=new_headers).status_code == 401


def test_cross_workspace_access_is_denied(client, db_session):
    first = bootstrap(client, "First", "first@example.com")
    first_headers = auth(first["access_token"])
    second = client.post("/api/v1/workspaces", headers=first_headers, json={"name": "Second"})
    assert second.status_code == 200
    second_wid = second.json()["workspace_id"]

    response = client.get(f"/api/v1/workspaces/{second_wid}/contacts", headers=first_headers)
    assert response.status_code == 403
    assert "cross-workspace" in response.json()["detail"]
    blocked = client.post(
        f"/api/v1/workspaces/{second_wid}/intake/website-form",
        headers=first_headers,
        json={"email": "x@example.com"},
    )
    assert blocked.status_code == 403


def test_read_only_role_cannot_write(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    invited = client.post(
        f"/api/v1/workspaces/{wid}/invitations",
        headers=headers,
        json={"email": "reader@example.com", "role": "read_only"},
    )
    assert invited.status_code == 200
    raw = invited.json()["invite_token"]

    reader = client.post(
        "/api/v1/auth/register",
        json={"email": "reader@example.com", "password": "Password123!", "display_name": "Reader"},
    )
    # The reader already has a personal workspace from register; accept the invite.
    joined = client.post(
        "/api/v1/invitations/accept",
        headers=auth(reader.json()["access_token"]),
        json={"token": raw},
    )
    assert joined.status_code == 200
    reader_headers = auth(joined.json()["access_token"])

    blocked = client.post(
        f"/api/v1/workspaces/{wid}/contacts",
        headers=reader_headers,
        json={"email": "denied@example.com"},
    )
    assert blocked.status_code == 403
    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=reader_headers).status_code == 200


def test_password_reset_and_email_verification(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    reset = client.post("/api/v1/auth/password-reset/request", json={"email": "owner@example.com"})
    assert reset.status_code == 200
    assert "development_token" not in reset.json()  # dev mode off by default

    verify = client.post("/api/v1/auth/email/verify/request", headers=headers).json()
    assert verify["accepted"] is True
    assert "development_token" not in verify

    bad = client.post("/api/v1/auth/password-reset/confirm", json={"token": "nope", "new_password": "NewPassword123!"})
    assert bad.status_code == 400


def test_password_change_revokes_other_sessions(client):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=auth(tokens["access_token"]),
        json={"current_password": "Password123!", "new_password": "AnotherPassword123!"},
    )
    assert changed.status_code == 200
    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=auth(tokens["access_token"])).status_code == 200
    relogin = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "AnotherPassword123!", "workspace_id": wid},
    )
    assert relogin.status_code == 200


def test_crm_lifecycle_and_delete_safeguards(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    contact = client.post(
        f"/api/v1/workspaces/{wid}/contacts",
        headers=headers,
        json={"email": "crm@example.com", "full_name": "CRM Person", "tags": ["vip"]},
    )
    assert contact.status_code == 201, contact.text
    cid = contact.json()["id"]

    duplicate = client.post(
        f"/api/v1/workspaces/{wid}/contacts", headers=headers, json={"email": "crm@example.com"}
    )
    assert duplicate.status_code == 409

    note = client.post(
        f"/api/v1/workspaces/{wid}/contacts/{cid}/notes",
        headers=headers, json={"contact_id": cid, "body": "Called, interested"},
    )
    assert note.status_code == 201

    guarded = client.delete(f"/api/v1/workspaces/{wid}/contacts/{cid}", headers=headers)
    assert guarded.status_code == 409  # not archived yet

    archived = client.post(f"/api/v1/workspaces/{wid}/contacts/{cid}/archive", headers=headers)
    assert archived.status_code == 200

    guarded = client.delete(f"/api/v1/workspaces/{wid}/contacts/{cid}", headers=headers)
    assert guarded.status_code == 409  # dependent note blocks deletion

    restored = client.post(f"/api/v1/workspaces/{wid}/contacts/{cid}/restore", headers=headers)
    assert restored.json()["archived"] is False


def test_lead_qualification_conversion_and_tasks(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    intake = client.post(
        f"/api/v1/workspaces/{wid}/intake/website-form",
        headers=headers, json={"email": "convert@example.com"},
    )
    lead_id = intake.json()["lead_id"]

    qualify = client.post(f"/api/v1/workspaces/{wid}/leads/{lead_id}/qualify", headers=headers)
    assert qualify.status_code == 200
    convert = client.post(f"/api/v1/workspaces/{wid}/leads/{lead_id}/convert", headers=headers)
    assert convert.status_code == 200
    assert convert.json()["status"] == "converted"

    task = client.post(
        f"/api/v1/workspaces/{wid}/tasks",
        headers=headers,
        json={"title": "Follow up", "contact_id": intake.json()["contact_id"], "priority": "high"},
    )
    assert task.status_code == 201
    done = client.patch(
        f"/api/v1/workspaces/{wid}/tasks/{task.json()['id']}",
        headers=headers, json={"status": "done"},
    )
    assert done.json()["completed_at"] is not None

    notifications = client.get(f"/api/v1/workspaces/{wid}/notifications", headers=headers).json()
    assert any("New lead captured" in item["message"] for item in notifications)
