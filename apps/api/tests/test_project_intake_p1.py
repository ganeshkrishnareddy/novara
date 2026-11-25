"""Named acceptance tests for PL-088 (guest project intake).

Requests are real persisted rows. Acceptance calls the project module's own
work-item creation path, so the created item carries normal activity and audit
records. No email, external form host or provider is contacted.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from novara_core.main import API
from novara_core.models import Event, now
from novara_core.modules.project_intake import (
    INTAKE_ACCEPTED,
    INTAKE_DECLINED,
    INTAKE_LINK_CREATED,
    INTAKE_LINK_REVOKED,
    INTAKE_SNOOZED,
    INTAKE_SUBMITTED,
    ProjectIntakeLink,
    ProjectIntakeRequest,
)
from novara_core.modules.projects import ProjectItem
from novara_core.security import hash_token

from .conftest import auth, bootstrap

PROJECTS = "/api/v1/workspaces/{wid}/projects"


def _project(client, wid, headers, name="Intake project"):
    response = client.post(PROJECTS.format(wid=wid), headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _link(client, wid, headers, project_id, name="Public form", expires_at=None):
    body = {"name": name}
    if expires_at is not None:
        body["expires_at"] = expires_at
    response = client.post(
        PROJECTS.format(wid=wid) + f"/{project_id}/intake/links", headers=headers, json=body
    )
    assert response.status_code == 201, response.text
    return response.json()


INTAKE = "/api/v1/public/project-intake"


def _submit(client, token, title, email="guest@example.com"):
    response = client.post(
        f"{INTAKE}/{token}/requests",
        json={
            "title": title,
            "description": "Please review this request.",
            "requester_name": "Guest Person",
            "requester_email": email,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_pl088_guest_submission_and_acceptance_creates_real_work_item(client, db_session):
    tokens = bootstrap(client, "IntakeAccept", "intake-accept@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    project = _project(client, wid, headers, "Accepted requests")
    issued = _link(client, wid, headers, project["id"])
    assert issued["token"].startswith("pil_")
    row = db_session.execute(
        select(ProjectIntakeLink).where(ProjectIntakeLink.id == issued["id"])
    ).scalar_one()
    assert row.token_hash == hash_token(issued["token"])
    assert issued["token"] not in row.token_hash
    listed = client.get(
        PROJECTS.format(wid=wid) + f"/{project['id']}/intake/links", headers=headers
    )
    assert listed.status_code == 200, listed.text
    assert all("token" not in item for item in listed.json())

    submitted = _submit(client, issued["token"], "Need a new landing page")
    assert submitted["state"] == "submitted"
    assert submitted["workspace_id"] == wid and submitted["project_id"] == project["id"]

    queue = client.get(
        PROJECTS.format(wid=wid) + f"/{project['id']}/intake/requests", headers=headers
    )
    assert [r["id"] for r in queue.json()] == [submitted["id"]]

    decided = client.post(
        PROJECTS.format(wid=wid)
        + f"/{project['id']}/intake/requests/{submitted['id']}/decision",
        headers=headers,
        json={"decision": "accept"},
    )
    assert decided.status_code == 200, decided.text
    accepted = decided.json()
    assert accepted["state"] == "accepted" and accepted["item_id"]

    items = client.get(PROJECTS.format(wid=wid) + f"/{project['id']}/items", headers=headers)
    assert items.status_code == 200, items.text
    item = next(item for item in items.json() if item["id"] == accepted["item_id"])
    assert item["title"] == "Need a new landing page"
    assert "guest@example.com" in item["description"]

    stored = db_session.execute(
        select(ProjectIntakeRequest).where(ProjectIntakeRequest.id == submitted["id"])
    ).scalar_one()
    assert stored.item_id == item["id"]
    assert db_session.get(ProjectItem, item["id"]) is not None
    event_types = set(
        db_session.execute(
            select(Event.event_type).where(Event.workspace_id == wid)
        ).scalars().all()
    )
    assert {INTAKE_LINK_CREATED, INTAKE_SUBMITTED, INTAKE_ACCEPTED} <= event_types


def test_pl088_decline_snooze_revoke_and_tenant_isolation(client, db_session):
    tokens = bootstrap(client, "IntakeStates", "intake-states@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    project = _project(client, wid, headers, "Triage")
    base = PROJECTS.format(wid=wid) + f"/{project['id']}/intake"
    issued = _link(client, wid, headers, project["id"], "Triage form")

    first = _submit(client, issued["token"], "First request", "first@example.com")
    declined = client.post(
        base + f"/requests/{first['id']}/decision", headers=headers,
        json={"decision": "decline"},
    )
    assert declined.status_code == 200, declined.text
    assert declined.json()["state"] == "declined"
    repeat = client.post(
        base + f"/requests/{first['id']}/decision", headers=headers,
        json={"decision": "accept"},
    )
    assert repeat.status_code == 409

    second = _submit(client, issued["token"], "Second request", "second@example.com")
    future = (now() + timedelta(days=1)).isoformat()
    snoozed = client.post(
        base + f"/requests/{second['id']}/decision", headers=headers,
        json={"decision": "snooze", "snooze_until": future},
    )
    assert snoozed.status_code == 200, snoozed.text
    assert snoozed.json()["state"] == "snoozed" and snoozed.json()["snooze_until"]

    third = _submit(client, issued["token"], "Third request", "third@example.com")
    past = (now() - timedelta(hours=1)).isoformat()
    assert client.post(
        base + f"/requests/{third['id']}/decision", headers=headers,
        json={"decision": "snooze", "snooze_until": past},
    ).status_code == 422

    removed = client.delete(base + f"/links/{issued['id']}", headers=headers)
    assert removed.status_code == 200, removed.text
    after_revoke = client.post(
        f"{INTAKE}/{issued['token']}/requests",
        json={"title": "After revocation", "requester_name": "Guest",
              "requester_email": "guest@example.com"},
    )
    assert after_revoke.status_code == 401

    expired = _link(
        client, wid, headers, project["id"], "Expired form",
        expires_at=(now() - timedelta(hours=1)).isoformat(),
    )
    after_expiry = client.post(
        f"{INTAKE}/{expired['token']}/requests",
        json={"title": "After expiry", "requester_name": "Guest",
              "requester_email": "guest@example.com"},
    )
    assert after_expiry.status_code == 401

    other = client.post("/api/v1/auth/register", json={
        "email": "intake-other@example.com", "display_name": "Other",
        "password": "Password123!",
    })
    assert other.status_code == 200
    other_wid, other_headers = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(base + "/requests", headers=other_headers).status_code == 403
    assert client.post(
        base + f"/requests/{first['id']}/decision", headers=other_headers,
        json={"decision": "accept"},
    ).status_code == 403

    event_types = set(
        db_session.execute(
            select(Event.event_type).where(Event.workspace_id == wid)
        ).scalars().all()
    )
    assert {INTAKE_DECLINED, INTAKE_SNOOZED, INTAKE_LINK_REVOKED} <= event_types
