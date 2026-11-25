"""AI agent control center: API, governance and workspace-scope tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from novara_core.database import get_db
from novara_core.models import Event, User, WorkspaceMember, new_id, now
from novara_core.modules.agents import (
    AGENT_CREATED,
    AGENT_RUN_APPROVED,
    AGENT_RUN_REQUESTED,
    AGENT_STATUS_CHANGED,
    AgentConfig,
    AgentRun,
    router,
)
from novara_core.security import create_session, hash_password

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/agents"


@pytest.fixture()
def agent_api(db_session):
    """Exercise the module router through a real FastAPI app on the test DB."""
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _owner_id(db_session) -> str:
    return db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one().id


def _role_headers(db_session, workspace_id: str, role: str, email: str):
    user = User(
        id=new_id(),
        email=email,
        display_name="Test Member",
        password_hash=hash_password("Password123!"),
        created_at=now(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        WorkspaceMember(
            id=new_id(),
            workspace_id=workspace_id,
            user_id=user.id,
            role=role,
            status="active",
            created_at=now(),
        )
    )
    db_session.flush()
    _, access, _ = create_session(db_session, user_id=user.id, workspace_id=workspace_id)
    db_session.commit()
    return auth(access)


def _create_agent(agent_api, workspace_id, headers, name="Research agent", **overrides):
    payload = {
        "name": name,
        "purpose": "Summarise internal notes",
        "model_provider": "local",
        "model_name": "llama-3",
        "boundary": "Read internal notes only; never contact customers",
        "max_steps": 4,
        "status": "active",
        "requires_approval": False,
    }
    payload.update(overrides)
    response = agent_api.post(BASE.format(wid=workspace_id), headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_agent_config_and_run_lifecycle(client, db_session, agent_api):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    url = BASE.format(wid=wid)

    assert agent_api.get(url, headers=headers).json() == []

    agent = _create_agent(agent_api, wid, headers)
    agent_id = agent["id"]
    assert "No external AI provider" in agent["notes"]
    assert agent["created_by"] == _owner_id(db_session)
    assert agent["max_steps"] == 4

    listed = agent_api.get(url, headers=headers).json()
    assert [item["id"] for item in listed] == [agent_id]
    fetched = agent_api.get(f"{url}/{agent_id}", headers=headers).json()
    assert fetched["boundary"] == agent["boundary"]

    updated = agent_api.patch(
        f"{url}/{agent_id}", headers=headers, json={"boundary": "Read notes only", "max_steps": 5}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["max_steps"] == 5

    paused = agent_api.post(f"{url}/{agent_id}/status", headers=headers, json={"status": "paused"})
    assert paused.json()["status"] == "paused"
    blocked = agent_api.post(
        f"{url}/{agent_id}/runs", headers=headers, json={"task": "Summarise weekly notes"}
    )
    assert blocked.status_code == 409
    resumed = agent_api.post(f"{url}/{agent_id}/status", headers=headers, json={"status": "active"})
    assert resumed.json()["status"] == "active"

    run = agent_api.post(
        f"{url}/{agent_id}/runs",
        headers=headers,
        json={"task": "Summarise weekly notes", "steps_taken": 1},
    )
    assert run.status_code == 201, run.text
    run_data = run.json()
    assert run_data["status"] == "queued"
    assert run_data["actor_id"] == _owner_id(db_session)
    assert "does not fabricate AI output" in run_data["notes"]

    runs = agent_api.get(f"{url}/runs", headers=headers).json()
    assert [item["id"] for item in runs] == [run_data["id"]]
    run_detail = agent_api.get(f"{url}/runs/{run_data['id']}", headers=headers).json()
    assert run_detail["task"] == "Summarise weekly notes"

    progressing = agent_api.post(
        f"{url}/{agent_id}/runs/{run_data['id']}/progress",
        headers=headers,
        json={"steps_taken": 2, "status": "running"},
    )
    assert progressing.status_code == 200, progressing.text
    assert progressing.json()["status"] == "running"

    finished = agent_api.post(
        f"{url}/{agent_id}/runs/{run_data['id']}/progress",
        headers=headers,
        json={"steps_taken": 3, "status": "completed"},
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "completed"
    assert finished.json()["finished_at"] is not None
    assert db_session.get(AgentRun, run_data["id"]).steps_taken == 3

    # Runs are retained for audit, and deletion of a clean config works.
    assert agent_api.delete(f"{url}/{agent_id}", headers=headers).status_code == 409
    spare = _create_agent(agent_api, wid, headers, name="Spare agent")
    deleted = agent_api.delete(f"{url}/{spare['id']}", headers=headers)
    assert deleted.status_code == 200
    assert "No external AI provider" in deleted.json()["notes"]
    assert agent_api.get(f"{url}/{spare['id']}", headers=headers).status_code == 404


def test_approval_is_role_gated_and_publishes_events(client, db_session, agent_api):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    url = BASE.format(wid=wid)
    owner_id = _owner_id(db_session)

    agent = _create_agent(agent_api, wid, headers, name="Approval agent", requires_approval=True)
    run = agent_api.post(
        f"{url}/{agent['id']}/runs", headers=headers, json={"task": "Draft customer outreach"}
    ).json()

    # A governed run cannot complete itself when the config requires approval.
    waiting = agent_api.post(
        f"{url}/{agent['id']}/runs/{run['id']}/progress",
        headers=headers,
        json={"status": "completed"},
    )
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["status"] == "awaiting_approval"
    assert agent_api.post(
        f"{url}/{agent['id']}/runs/{run['id']}/progress",
        headers=headers,
        json={"steps_taken": 1},
    ).status_code == 409

    sales_rep_headers = _role_headers(db_session, wid, "sales_rep", "rep@example.com")
    denied = agent_api.post(
        f"{url}/{agent['id']}/runs/{run['id']}/approve", headers=sales_rep_headers
    )
    assert denied.status_code == 403
    assert "outreach:approve" in denied.json()["detail"]
    assert agent_api.get(f"{url}/runs/{run['id']}", headers=headers).json()["status"] == "awaiting_approval"

    approved = agent_api.post(f"{url}/{agent['id']}/runs/{run['id']}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "completed"
    assert approved.json()["finished_at"] is not None
    assert agent_api.post(
        f"{url}/{agent['id']}/runs/{run['id']}/approve", headers=headers
    ).status_code == 409

    events = db_session.execute(
        select(Event).where(Event.workspace_id == wid).order_by(Event.seq)
    ).scalars().all()
    types = [event.event_type for event in events]
    for expected in (AGENT_CREATED, AGENT_RUN_REQUESTED, AGENT_RUN_APPROVED, AGENT_STATUS_CHANGED):
        assert expected in types
    for event in events:
        assert event.payload["actor_id"] == owner_id
    approval_event = next(event for event in events if event.event_type == AGENT_RUN_APPROVED)
    assert approval_event.entity_id == run["id"]
    assert approval_event.payload["approved_by"] == owner_id


def test_execution_limit_is_enforced(client, db_session, agent_api):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    url = BASE.format(wid=wid)

    agent = _create_agent(agent_api, wid, headers, name="Limited agent", max_steps=2)
    agent_id = agent["id"]

    too_many = agent_api.post(
        f"{url}/{agent_id}/runs",
        headers=headers,
        json={"task": "Too many steps", "steps_taken": 3},
    )
    assert too_many.status_code == 422
    assert "max_steps" in too_many.json()["detail"]

    run = agent_api.post(
        f"{url}/{agent_id}/runs", headers=headers, json={"task": "Two steps", "steps_taken": 1}
    ).json()

    over_limit = agent_api.post(
        f"{url}/{agent_id}/runs/{run['id']}/progress",
        headers=headers,
        json={"steps_taken": 3, "status": "running"},
    )
    assert over_limit.status_code == 422
    assert db_session.get(AgentRun, run["id"]).steps_taken == 1

    within_limit = agent_api.post(
        f"{url}/{agent_id}/runs/{run['id']}/progress",
        headers=headers,
        json={"steps_taken": 2, "status": "completed"},
    )
    assert within_limit.status_code == 200, within_limit.text
    assert within_limit.json()["steps_taken"] == 2

    invalid_config = agent_api.post(
        url,
        headers=headers,
        json={
            "name": "Invalid steps",
            "purpose": "p",
            "model_provider": "local",
            "model_name": "m",
            "boundary": "b",
            "max_steps": 0,
        },
    )
    assert invalid_config.status_code == 422


def test_workspace_isolation(client, db_session, agent_api):
    first = bootstrap(client)
    first_wid, first_headers = first["workspace_id"], auth(first["access_token"])
    first_url = BASE.format(wid=first_wid)
    first_agent = _create_agent(agent_api, first_wid, first_headers, name="First agent")
    first_run = agent_api.post(
        f"{first_url}/{first_agent['id']}/runs", headers=first_headers, json={"task": "First run"}
    ).json()

    second = client.post(
        "/api/v1/workspaces", headers=first_headers, json={"name": "Second workspace"}
    )
    assert second.status_code == 200, second.text
    second_tokens = second.json()
    second_wid, second_headers = second_tokens["workspace_id"], auth(second_tokens["access_token"])
    second_url = BASE.format(wid=second_wid)
    second_agent = _create_agent(agent_api, second_wid, second_headers, name="Second agent")
    second_run = agent_api.post(
        f"{second_url}/{second_agent['id']}/runs", headers=second_headers, json={"task": "Second run"}
    ).json()

    assert agent_api.get(first_url, headers=second_headers).status_code == 403
    assert agent_api.get(first_url, headers=first_headers).json()[0]["id"] == first_agent["id"]
    assert [item["id"] for item in agent_api.get(second_url, headers=second_headers).json()] == [
        second_agent["id"]
    ]

    # An id from another workspace must not be readable under this workspace.
    assert agent_api.get(f"{first_url}/{second_agent['id']}", headers=first_headers).status_code == 404
    assert agent_api.get(f"{first_url}/runs/{second_run['id']}", headers=first_headers).status_code == 404
    assert agent_api.post(
        f"{first_url}/{second_agent['id']}/runs/{second_run['id']}/approve", headers=first_headers
    ).status_code == 404

    assert db_session.get(AgentConfig, first_agent["id"]).workspace_id == first_wid
    assert db_session.get(AgentRun, second_run["id"]).workspace_id == second_wid
    assert db_session.get(AgentRun, first_run["id"]).workspace_id == first_wid


def test_agent_endpoints_require_authentication(client, db_session, agent_api):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    url = BASE.format(wid=wid)
    assert agent_api.get(url).status_code == 401
    assert agent_api.post(url, json={"name": "x"}).status_code == 401
