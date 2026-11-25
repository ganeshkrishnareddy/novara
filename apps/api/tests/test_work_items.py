"""Named acceptance tests for the Plane work-item P0 cluster.

PL-004 (work items in a dedicated user-facing view), PL-006 (validated
assignment), PL-008 (configurable grouped states), PL-017 (due dates) and
PL-038 (typed workspace-scoped search). Route-order regression is covered too.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from novara_core.main import app
from novara_core.models import Event
from novara_core.modules import projects, search

from .conftest import auth, bootstrap

PROJECTS_PREFIX = "/api/v1/workspaces/{workspace_id}/projects"
SEARCH_PREFIX = "/api/v1/workspaces/{workspace_id}/search"


def _has_prefix(routes, prefix: str) -> bool:
    for route in routes:
        if getattr(route, "path", "").startswith(prefix):
            return True
        nested = getattr(route, "original_router", None)
        if nested is not None and _has_prefix(nested.routes, prefix):
            return True
    return False


@pytest.fixture(autouse=True)
def _work_item_routers():
    added = []
    if not _has_prefix(app.routes, PROJECTS_PREFIX):
        app.include_router(projects.router)
        added.append(projects.router)
    if not _has_prefix(app.routes, SEARCH_PREFIX):
        app.include_router(search.router)
        added.append(search.router)
    yield
    if added:
        # conftest's global guard restores app.routes after each test.
        app.routes[:] = [
            route for route in app.routes
            if getattr(route, "original_router", None) not in added
        ]


def _new_project(client, headers, workspace_id, name="Delivery"):
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        headers=headers,
        json={"name": name, "status": "active"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _new_item(client, headers, base, title, **extra):
    response = client.post(
        f"{base}/items", headers=headers, json={"title": title, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_work_item_lifecycle_is_user_facing_and_workspace_isolated(client, db_session):
    """PL-004: create/read/update/complete an item in a real view; no tenant leak."""
    first = bootstrap(client, "Work", "work@example.com")
    wid, headers = first["workspace_id"], auth(first["access_token"])
    base = f"/api/v1/workspaces/{wid}/projects"
    project = _new_project(client, headers, wid)

    item = _new_item(client, headers, base=f"{base}/{project['id']}", title="Draft brief")
    item_id = item["id"]
    assert item["status"] == "todo"
    assert item["completed_at"] is None
    assert item["state_group"] == "todo"

    listed = client.get(f"{base}/{project['id']}/items", headers=headers)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [item_id]

    done = client.patch(
        f"{base}/{project['id']}/items/{item_id}", headers=headers, json={"status": "done"}
    )
    assert done.status_code == 200, done.text
    assert done.json()["completed_at"] is not None
    assert done.json()["state_group"] == "done"

    progress = client.get(f"{base}/{project['id']}/progress", headers=headers)
    assert progress.json()["done_items"] == 1
    assert progress.json()["completion_percent"] == 100.0

    event_types = db_session.execute(
        select(Event.event_type).where(Event.workspace_id == wid)
    ).scalars().all()
    assert projects.PROJECT_ITEM_CREATED in event_types
    assert projects.PROJECT_ITEM_UPDATED in event_types

    second = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Other work"}
    )
    assert second.status_code == 200, second.text
    other_wid = second.json()["workspace_id"]
    other_headers = auth(second.json()["access_token"])
    other_project = _new_project(client, other_headers, other_wid, name="Private")
    other_item = _new_item(
        client, other_headers, f"/api/v1/workspaces/{other_wid}/projects/{other_project['id']}",
        "Secret brief",
    )
    local_base = f"/api/v1/workspaces/{wid}/projects"
    assert client.get(local_base + f"/{other_project['id']}/items", headers=headers).status_code == 404
    assert client.patch(
        f"{local_base}/{project['id']}/items/{other_item['id']}",
        headers=headers, json={"status": "done"},
    ).status_code == 404


def test_assignee_set_changed_and_invalid_values_rejected(client):
    """PL-006: assignee is validated as an active member and can be changed."""
    tokens = bootstrap(client, "Assign", "assign@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    me = client.get("/api/v1/auth/me", headers=headers).json()["user"]["id"]
    base = f"/api/v1/workspaces/{wid}/projects/{_new_project(client, headers, wid)['id']}"

    assignees = client.get(f"/api/v1/workspaces/{wid}/projects/assignees", headers=headers)
    assert assignees.status_code == 200, assignees.text
    assert any(row["id"] == me for row in assignees.json())

    item = _new_item(client, headers, base, "Assigned work", assignee_id=me)
    assert item["assignee_id"] == me

    changed = client.patch(
        f"{base}/items/{item['id']}", headers=headers, json={"assignee_id": None}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["assignee_id"] is None

    for invalid in ("not-a-user",):
        response = client.patch(
            f"{base}/items/{item['id']}", headers=headers, json={"assignee_id": invalid}
        )
        assert response.status_code == 422, (invalid, response.text)
    assert client.post(
        f"{base}/items", headers=headers, json={"title": "Bad assignee", "assignee_id": "ghost"}
    ).status_code == 422


def test_configurable_states_are_validated_grouped_and_drive_progress(client):
    """PL-008: custom states are grouped, ordered, validated and roll up progress."""
    tokens = bootstrap(client, "States", "states@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/projects"
    project = _new_project(client, headers, wid)
    item_base = f"{base}/{project['id']}"

    assert client.post(
        f"{base}/states", headers=headers, json={"name": "Wrong", "group": "invalid"}
    ).status_code == 422
    for name, group, position in (
        ("Backlog", "todo", 3),
        ("Review", "in_progress", 2),
        ("Shipped", "done", 1),
    ):
        created = client.post(
            f"{base}/states",
            headers=headers,
            json={"name": name, "group": group, "position": position},
        )
        assert created.status_code == 201, created.text
    assert client.post(
        f"{base}/states", headers=headers, json={"name": "Backlog"}
    ).status_code == 409

    states = client.get(f"{base}/states", headers=headers)
    assert states.status_code == 200, states.text
    assert [row["name"] for row in states.json()] == ["Shipped", "Review", "Backlog"]

    renamed = client.patch(
        f"{base}/states/{states.json()[1]['id']}", headers=headers, json={"name": "QA"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "QA"

    _new_item(client, headers, item_base, "Queued", status="Backlog")
    _new_item(client, headers, item_base, "Checking", status="QA")
    shipped = _new_item(client, headers, item_base, "Released", status="Shipped")
    assert shipped["state_group"] == "done"
    assert shipped["completed_at"] is not None

    listed = client.get(f"{item_base}/items", headers=headers).json()
    assert {row["title"]: row["state_group"] for row in listed} == {
        "Queued": "todo", "Checking": "in_progress", "Released": "done",
    }

    progress = client.get(f"{item_base}/progress", headers=headers).json()
    assert progress == {
        "project_id": project["id"], "total_items": 3, "todo_items": 1,
        "in_progress_items": 1, "done_items": 1, "completion_percent": round(100 / 3, 2),
    }

    assert client.post(
        f"{item_base}/items", headers=headers, json={"title": "Old", "status": "todo"}
    ).status_code == 422
    state_id = states.json()[0]["id"]
    deactivated = client.patch(
        f"{base}/states/{state_id}", headers=headers, json={"is_active": False}
    )
    assert deactivated.status_code == 200, deactivated.text
    assert client.post(
        f"{item_base}/items", headers=headers, json={"title": "Blocked", "status": "Shipped"}
    ).status_code == 422
    # Existing items keep their group after the state is deactivated.
    assert client.get(f"{item_base}/items", headers=headers).json()[2]["state_group"] == "done"


def test_due_dates_are_stored_validated_and_visible(client):
    """PL-017: project and item due dates persist, reject bad input and filter."""
    tokens = bootstrap(client, "Due", "due@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    project = client.post(
        f"/api/v1/workspaces/{wid}/projects",
        headers=headers,
        json={"name": "Dated", "due_at": "2027-03-01T10:00:00Z"},
    )
    assert project.status_code == 201, project.text
    assert project.json()["due_at"]

    assert client.post(
        f"/api/v1/workspaces/{wid}/projects",
        headers=headers, json={"name": "Bad date", "due_at": "not-a-date"},
    ).status_code == 422

    base = f"/api/v1/workspaces/{wid}/projects/{project.json()['id']}"
    late = _new_item(client, headers, base, "Overdue", due_at="2020-01-01T00:00:00Z")
    future = _new_item(client, headers, base, "Planned", due_at="2027-06-01T00:00:00Z")
    assert late["due_at"] and future["due_at"]

    rows = client.get(f"{base}/items", headers=headers).json()
    assert {row["title"] for row in rows} == {"Overdue", "Planned"}
    overdue = client.get(f"{base}/items?overdue=true", headers=headers)
    assert overdue.status_code == 200, overdue.text
    assert [row["id"] for row in overdue.json()] == [late["id"]]
    assert client.patch(
        f"{base}/items/{late['id']}", headers=headers, json={"due_at": "still-not-a-date"}
    ).status_code == 422


def test_search_returns_typed_project_results_without_cross_workspace_leak(client):
    """PL-038: typed project/work-item results are scoped to the caller's workspace."""
    first = bootstrap(client, "Searchable", "searchable@example.com")
    wid, headers = first["workspace_id"], auth(first["access_token"])
    base = f"/api/v1/workspaces/{wid}/projects"
    project = _new_project(client, headers, wid, name="Searchable Rollout")
    item = _new_item(client, headers, f"{base}/{project['id']}", "Findable work item")

    second = client.post("/api/v1/workspaces", headers=headers, json={"name": "Sealed"})
    other_wid, other_headers = second.json()["workspace_id"], auth(second.json()["access_token"])
    other_project = _new_project(client, other_headers, other_wid, name="Searchable Secret")
    _new_item(
        client, other_headers,
        f"/api/v1/workspaces/{other_wid}/projects/{other_project['id']}",
        "Findable secret item",
    )

    response = client.get(
        f"/api/v1/workspaces/{wid}/search", headers=headers,
        params={"q": "Searchable"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload["counts"]) == set(search.SEARCH_TYPES)
    typed = {row["type"]: row for row in payload["results"]}
    assert "project" in typed
    assert typed["project"]["id"] == project["id"]
    assert typed["project"]["url_hint"] == f"/projects/{project['id']}"
    ids = {row["id"] for row in payload["results"]}
    assert other_project["id"] not in ids

    item_search = client.get(
        f"/api/v1/workspaces/{wid}/search", headers=headers, params={"q": "Findable"}
    )
    assert item_search.status_code == 200, item_search.text
    item_typed = {row["type"]: row for row in item_search.json()["results"]}
    assert item_typed["project_item"]["id"] == item["id"]
    assert item_typed["project_item"]["url_hint"] == f"/projects/{project['id']}/items/{item['id']}"
    assert {row["id"] for row in item_search.json()["results"]} == {item["id"]}
    facets = client.get(f"/api/v1/workspaces/{wid}/search/facets", headers=headers)
    assert facets.status_code == 200, facets.text
    assert facets.json()["counts"]["project_item"] == 1

    assert client.get(
        f"/api/v1/workspaces/{wid}/search", headers=other_headers, params={"q": "Searchable"}
    ).status_code == 403


def test_static_project_routes_resolve_before_dynamic_project_id(client):
    """Static sub-resources must not be captured by GET /{project_id}."""
    tokens = bootstrap(client, "Routes", "project-routes@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/projects"
    for suffix in ("states", "assignees"):
        response = client.get(f"{base}/{suffix}", headers=headers)
        assert response.status_code == 200, (suffix, response.text)
