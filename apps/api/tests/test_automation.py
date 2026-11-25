from __future__ import annotations

import pytest
from sqlalchemy import func, select

from novara_core.main import app
from novara_core.models import Contact, Event, Task, User, new_id
from novara_core.modules import automation

from .conftest import auth, bootstrap

PREFIX = "/api/v1/workspaces/{workspace_id}/automations"
VALID_DEFINITION = [
    {"id": "check_contact", "type": "condition", "check": "contact"},
    {"id": "notify", "type": "action", "check": "task"},
]


def _ensure_routes() -> None:
    already = any(
        (getattr(route, "path", "") or "").startswith(PREFIX)
        or getattr(route, "original_router", None) is automation.router
        for route in app.routes
    )
    if not already:
        app.include_router(automation.router)
    for route in app.routes:
        if getattr(route, "original_router", None) is automation.router and not hasattr(route, "path"):
            route.path = PREFIX


@pytest.fixture(autouse=True)
def _module_router() -> None:
    _ensure_routes()


def _second_workspace(client, headers):
    response = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Other Workspace"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["workspace_id"], auth(data["access_token"])


def test_automation_crud_status_and_events(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/automations"

    created = client.post(
        base,
        headers=headers,
        json={
            "name": "Qualify and follow up",
            "description": "Defines the follow-up flow",
            "trigger_type": "lead_qualified",
            "definition": VALID_DEFINITION,
        },
    )
    assert created.status_code == 201, created.text
    automation_id = created.json()["id"]
    assert created.json()["status"] == "active"
    assert created.json()["definition"] == VALID_DEFINITION
    assert created.json()["created_by"]

    assert [row["id"] for row in client.get(base, headers=headers).json()] == [automation_id]
    fetched = client.get(f"{base}/{automation_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Qualify and follow up"

    patched = client.patch(
        f"{base}/{automation_id}",
        headers=headers,
        json={"description": "Updated", "definition": [{"id": "only", "type": "noop"}]},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["definition"] == [{"id": "only", "type": "noop"}]

    changed = client.post(
        f"{base}/{automation_id}/status", headers=headers, json={"status": "paused"}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["status"] == "paused"

    events = db_session.execute(
        select(Event).where(Event.workspace_id == wid).order_by(Event.seq)
    ).scalars().all()
    types = [event.event_type for event in events]
    assert "automation.created" in types
    assert "automation.status_changed" in types
    owner_id = db_session.execute(
        select(User).where(User.email == "owner@example.com")
    ).scalar_one().id
    module_events = [event for event in events if event.event_type.startswith("automation.")]
    assert module_events
    assert all(event.payload.get("actor_id") == owner_id for event in module_events)

    deleted = client.delete(f"{base}/{automation_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert client.get(f"{base}/{automation_id}", headers=headers).status_code == 404


@pytest.mark.parametrize(
    "definition",
    [
        [],
        "not-a-list",
        [{}],
        [{"id": "a"}],
        [{"type": "noop"}],
        [{"id": "", "type": "noop"}],
        [{"id": "a", "type": "condition", "check": "unknown_table"}],
    ],
)
def test_invalid_definitions_are_rejected(client, definition):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    response = client.post(
        f"/api/v1/workspaces/{wid}/automations",
        headers=headers,
        json={"name": "Invalid", "trigger_type": "manual", "definition": definition},
    )
    assert response.status_code == 422, response.text


def test_invalid_payloads(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    url = f"/api/v1/workspaces/{wid}/automations"
    assert client.post(
        url, headers=headers,
        json={"name": "   ", "trigger_type": "manual", "definition": VALID_DEFINITION},
    ).status_code == 422
    assert client.post(
        url, headers=headers,
        json={"name": "Bad trigger", "trigger_type": "other", "definition": VALID_DEFINITION},
    ).status_code == 422
    assert client.post(
        url, headers=headers,
        json={"name": "Extra", "trigger_type": "manual", "definition": VALID_DEFINITION, "workspace_id": "x"},
    ).status_code == 422
    assert client.post(
        url, headers=headers,
        json={"name": "Duplicate", "trigger_type": "manual", "definition": VALID_DEFINITION},
    ).status_code == 201
    assert client.post(
        url, headers=headers,
        json={"name": "Duplicate", "trigger_type": "manual", "definition": VALID_DEFINITION},
    ).status_code == 409


def test_dry_run_walks_records_and_records_runs(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/automations"
    contact = Contact(id=new_id(), workspace_id=wid, email="dryrun@example.com")
    db_session.add(contact)
    db_session.commit()
    task_count_before = db_session.execute(
        select(func.count()).select_from(Task).where(Task.workspace_id == wid)
    ).scalar()

    created = client.post(
        base,
        headers=headers,
        json={
            "name": "Dry run flow",
            "trigger_type": "manual",
            "definition": [
                {"id": "found", "type": "condition", "check": "contact", "target_id": contact.id},
                {"id": "missing", "type": "action", "check": "task", "target_id": "does-not-exist"},
                {"id": "noop", "type": "action"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    automation_id = created.json()["id"]

    run = client.post(
        f"{base}/{automation_id}/dry_run",
        headers=headers,
        json={"trigger_event": "manual.test", "context": {}},
    )
    assert run.status_code == 201, run.text
    data = run.json()
    assert data["trigger_event"] == "manual.test"
    assert data["status"] == "skipped"
    assert "missing" in data["error"]
    assert [step["id"] for step in data["steps"]] == ["found", "missing", "noop"]
    assert data["steps"][0]["matched"] == 1
    assert data["steps"][1]["matched"] == 0
    assert data["steps"][2]["result"] == "noop"

    runs = client.get(f"{base}/{automation_id}/runs", headers=headers)
    assert runs.status_code == 200, runs.text
    assert [row["id"] for row in runs.json()] == [data["id"]]

    # A dry run never creates CRM records.
    task_count_after = db_session.execute(
        select(func.count()).select_from(Task).where(Task.workspace_id == wid)
    ).scalar()
    assert task_count_after == task_count_before

    run_events = db_session.execute(
        select(Event).where(
            Event.workspace_id == wid, Event.event_type == "automation.run_recorded"
        )
    ).scalars().all()
    assert len(run_events) == 1
    assert run_events[0].entity_id == data["id"]

    success = client.post(
        f"{base}/{automation_id}/dry_run",
        headers=headers,
        json={
            "trigger_event": "manual.test",
            "context": {"contact_id": contact.id},
        },
    )
    assert success.status_code == 201, success.text
    assert success.json()["status"] == "skipped"  # the missing task step is still absent

    simple = client.post(
        base,
        headers=headers,
        json={
            "name": "Simple flow",
            "trigger_type": "manual",
            "definition": [
                {"id": "find_contact", "type": "condition", "check": "contact", "target_id": contact.id},
                {"id": "act", "type": "action"},
            ],
        },
    ).json()
    good = client.post(
        f"{base}/{simple['id']}/dry_run", headers=headers, json={"trigger_event": "manual"}
    )
    assert good.status_code == 201, good.text
    assert good.json()["status"] == "success"
    assert good.json()["error"] is None

    paused = client.post(
        f"{base}/{simple['id']}/status", headers=headers, json={"status": "paused"}
    )
    assert paused.status_code == 200
    paused_run = client.post(
        f"{base}/{simple['id']}/dry_run", headers=headers, json={"trigger_event": "manual"}
    )
    assert paused_run.json()["status"] == "skipped"
    assert "paused" in paused_run.json()["error"]


def test_automation_workspace_isolation(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    other_wid, other_headers = _second_workspace(client, headers)

    foreign = client.post(
        f"/api/v1/workspaces/{other_wid}/automations",
        headers=other_headers,
        json={
            "name": "Foreign flow",
            "trigger_type": "manual",
            "definition": [{"id": "a", "type": "noop"}],
        },
    )
    assert foreign.status_code == 201, foreign.text
    foreign_id = foreign.json()["id"]

    assert client.get(
        f"/api/v1/workspaces/{wid}/automations/{foreign_id}", headers=headers
    ).status_code == 404
    assert client.post(
        f"{base_url(wid)}/{foreign_id}/dry_run", headers=headers, json={}
    ).status_code == 404
    assert client.get(
        f"/api/v1/workspaces/{other_wid}/automations", headers=headers
    ).status_code == 403
    assert client.post(
        f"/api/v1/workspaces/{other_wid}/automations",
        headers=headers,
        json={"name": "Intruder", "trigger_type": "manual", "definition": [{"id": "a", "type": "noop"}]},
    ).status_code == 403


def base_url(workspace_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/automations"
