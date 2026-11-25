from __future__ import annotations

import pytest
from sqlalchemy import select

from novara_core.main import app
from novara_core.models import Event
from novara_core.modules import projects

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
def _attach_projects_router():
    prefix = "/api/v1/workspaces/{workspace_id}/projects"
    if _has_prefix(app.routes, prefix):
        yield
        return
    original = list(app.routes)
    app.include_router(projects.router)
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


def test_project_crud_items_completion_and_events(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    actor_id = me.json()["user"]["id"]
    base = f"/api/v1/workspaces/{wid}/projects"

    created = client.post(
        base,
        headers=headers,
        json={"name": "  Launch  ", "description": "Q4 rollout", "status": "planning"},
    )
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["name"] == "Launch"
    assert project["status"] == "planning"
    assert project["owner_id"] == actor_id
    project_id = project["id"]

    assert client.get(f"{base}/{project_id}", headers=headers).json()["id"] == project_id
    patched = client.patch(
        f"{base}/{project_id}",
        headers=headers,
        json={"status": "active", "description": "In flight"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "active"
    assert patched.json()["description"] == "In flight"

    first_item = client.post(
        f"{base}/{project_id}/items",
        headers=headers,
        json={"title": "Design", "status": "todo"},
    )
    assert first_item.status_code == 201, first_item.text
    assert first_item.json()["completed_at"] is None
    first_item_id = first_item.json()["id"]

    second_item = client.post(
        f"{base}/{project_id}/items",
        headers=headers,
        json={"title": "Build", "status": "in_progress", "assignee_id": actor_id},
    )
    assert second_item.status_code == 201, second_item.text

    third_item = client.post(
        f"{base}/{project_id}/items",
        headers=headers,
        json={"title": "Ship", "status": "done"},
    )
    assert third_item.status_code == 201, third_item.text
    assert third_item.json()["completed_at"] is not None

    completed = client.patch(
        f"{base}/{project_id}/items/{first_item_id}",
        headers=headers,
        json={"status": "done"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "done"
    assert completed.json()["completed_at"] is not None

    items = client.get(f"{base}/{project_id}/items", headers=headers)
    assert items.status_code == 200
    assert len(items.json()) == 3

    types = _event_types(db_session, wid)
    for expected in (
        projects.PROJECT_CREATED,
        projects.PROJECT_UPDATED,
        projects.PROJECT_ITEM_CREATED,
        projects.PROJECT_ITEM_UPDATED,
    ):
        assert expected in types
    assert all(event.payload["actor_id"] == actor_id for event in _events(db_session, wid))

    deleted = client.delete(f"{base}/{project_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert client.get(base, headers=headers).json() == []
    assert client.get(f"{base}/{project_id}", headers=headers).status_code == 404
    assert projects.PROJECT_DELETED in _event_types(db_session, wid)


def test_project_progress_summary_is_computed_in_sql(client):
    tokens = bootstrap(client, "Progress", "progress@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/projects"

    empty = client.post(base, headers=headers, json={"name": "Empty"})
    assert empty.status_code == 201, empty.text
    empty_progress = client.get(
        f"{base}/{empty.json()['id']}/progress", headers=headers
    )
    assert empty_progress.status_code == 200, empty_progress.text
    assert empty_progress.json() == {
        "project_id": empty.json()["id"],
        "total_items": 0,
        "todo_items": 0,
        "in_progress_items": 0,
        "done_items": 0,
        "completion_percent": 0.0,
    }

    project = client.post(base, headers=headers, json={"name": "Measured"})
    project_id = project.json()["id"]
    for title, item_status in (
        ("A", "todo"),
        ("B", "in_progress"),
        ("C", "done"),
        ("D", "done"),
    ):
        response = client.post(
            f"{base}/{project_id}/items",
            headers=headers,
            json={"title": title, "status": item_status},
        )
        assert response.status_code == 201, response.text

    progress = client.get(f"{base}/{project_id}/progress", headers=headers)
    assert progress.status_code == 200, progress.text
    assert progress.json() == {
        "project_id": project_id,
        "total_items": 4,
        "todo_items": 1,
        "in_progress_items": 1,
        "done_items": 2,
        "completion_percent": 50.0,
    }
    assert client.get(f"{base}/missing/progress", headers=headers).status_code == 404


def test_project_workspace_isolation(client, db_session):
    first = bootstrap(client, "First", "first@example.com")
    first_headers = auth(first["access_token"])
    first_wid = first["workspace_id"]

    second_response = client.post(
        "/api/v1/workspaces", headers=first_headers, json={"name": "Second"}
    )
    assert second_response.status_code == 200, second_response.text
    second = second_response.json()
    second_wid, second_headers = second["workspace_id"], auth(second["access_token"])

    own_project = client.post(
        f"/api/v1/workspaces/{first_wid}/projects",
        headers=first_headers,
        json={"name": "Own"},
    )
    assert own_project.status_code == 201, own_project.text
    own_project_id = own_project.json()["id"]

    other_project = client.post(
        f"/api/v1/workspaces/{second_wid}/projects",
        headers=second_headers,
        json={"name": "Other"},
    )
    assert other_project.status_code == 201, other_project.text
    other_project_id = other_project.json()["id"]
    other_item = client.post(
        f"/api/v1/workspaces/{second_wid}/projects/{other_project_id}/items",
        headers=second_headers,
        json={"title": "Secret item"},
    )
    assert other_item.status_code == 201, other_item.text
    other_item_id = other_item.json()["id"]

    assert client.get(
        f"/api/v1/workspaces/{second_wid}/projects", headers=first_headers
    ).status_code == 403

    first_base = f"/api/v1/workspaces/{first_wid}/projects"
    assert client.get(first_base, headers=first_headers).json()[0]["id"] == own_project_id
    for path in (
        f"{first_base}/{other_project_id}",
        f"{first_base}/{other_project_id}/items",
        f"{first_base}/{other_project_id}/progress",
    ):
        assert client.get(path, headers=first_headers).status_code == 404
    assert client.patch(
        f"{first_base}/{other_project_id}",
        headers=first_headers,
        json={"name": "hijacked"},
    ).status_code == 404
    assert client.delete(
        f"{first_base}/{other_project_id}", headers=first_headers
    ).status_code == 404

    # An item from the other workspace cannot be patched under a local project.
    assert client.patch(
        f"{first_base}/{own_project_id}/items/{other_item_id}",
        headers=first_headers,
        json={"status": "done"},
    ).status_code == 404

    assert _events(db_session, first_wid)
    assert all(event.workspace_id == first_wid for event in _events(db_session, first_wid))
    assert all(event.workspace_id == second_wid for event in _events(db_session, second_wid))


def test_project_bad_payloads_and_missing_rows(client):
    tokens = bootstrap(client, "BadInput", "bad@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/projects"

    bad_projects = (
        {"name": ""},
        {"name": "   "},
        {"name": "Valid", "status": "unknown"},
        {"name": "Valid", "owner_id": "not-a-member"},
        {"name": "Valid", "workspace_id": "another-workspace"},
    )
    for payload in bad_projects:
        response = client.post(base, headers=headers, json=payload)
        assert response.status_code == 422, (payload, response.text)

    assert client.get(base + "?status=unknown", headers=headers).status_code == 422

    project = client.post(base, headers=headers, json={"name": "Valid"})
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    assert client.patch(
        f"{base}/{project_id}", headers=headers, json={"name": ""}
    ).status_code == 422
    assert client.patch(
        f"{base}/{project_id}", headers=headers, json={"owner_id": None}
    ).status_code == 422
    assert client.patch(
        f"{base}/{project_id}", headers=headers, json={"status": "unknown"}
    ).status_code == 422

    bad_items = (
        {"title": ""},
        {"title": "Valid", "status": "unknown"},
        {"title": "Valid", "assignee_id": "not-a-member"},
        {"title": "Valid", "item_id": "spoofed"},
    )
    for payload in bad_items:
        response = client.post(
            f"{base}/{project_id}/items", headers=headers, json=payload
        )
        assert response.status_code == 422, (payload, response.text)

    item = client.post(
        f"{base}/{project_id}/items", headers=headers, json={"title": "Valid item"}
    )
    assert item.status_code == 201, item.text
    assert client.patch(
        f"{base}/{project_id}/items/{item.json()['id']}",
        headers=headers,
        json={"status": "unknown"},
    ).status_code == 422
    assert client.patch(
        f"{base}/{project_id}/items/{item.json()['id']}",
        headers=headers,
        json={"title": ""},
    ).status_code == 422

    assert client.get(f"{base}/missing", headers=headers).status_code == 404
    assert client.post(
        f"{base}/missing/items", headers=headers, json={"title": "x"}
    ).status_code == 404
    assert client.patch(
        f"{base}/{project_id}/items/missing", headers=headers, json={"status": "done"}
    ).status_code == 404
    assert client.get(base, headers=auth("garbage")).status_code == 401
