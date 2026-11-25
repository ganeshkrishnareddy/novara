"""Named acceptance tests for the P1 Plane backend cluster.

Every test here drives the real project router with the shared client/db/auth
fixtures. Rows whose acceptance criterion also requires a UI change are kept
out of the claimed set; their backend assertions are included for the
integration agent but the test names say "backend" explicitly.
"""

from __future__ import annotations

from sqlalchemy import func, select

from novara_core.models import Event
from novara_core.modules import projects as pj

from .conftest import auth, bootstrap


API = "/api/v1"


def _setup(client, name="Plane P1", email="plane-owner@example.com"):
    tokens = bootstrap(client, name, email)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    created = client.post(
        f"{API}/workspaces/{wid}/projects", headers=headers, json={"name": name}
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    return wid, headers, pid, f"{API}/workspaces/{wid}/projects/{pid}"


def _other_workspace(client, headers):
    response = client.post(f"{API}/workspaces", headers=headers, json={"name": "Other"})
    assert response.status_code == 200, response.text
    data = response.json()
    return data["workspace_id"], auth(data["access_token"])


def _member(client, wid, headers, email, role="sales_rep"):
    invite = client.post(
        f"{API}/workspaces/{wid}/invitations", headers=headers,
        json={"email": email, "role": role},
    )
    assert invite.status_code == 200, invite.text
    registered = client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Password123!", "display_name": email.split("@")[0]},
    )
    assert registered.status_code == 200, registered.text
    accepted = client.post(
        f"{API}/invitations/accept", headers=auth(registered.json()["access_token"]),
        json={"token": invite.json()["invite_token"]},
    )
    assert accepted.status_code == 200, accepted.text
    member_headers = auth(accepted.json()["access_token"])
    me = client.get(f"{API}/auth/me", headers=member_headers)
    assert me.status_code == 200, me.text
    return member_headers, me.json()["user"]["id"]


def _item(client, base, headers, title, **extra):
    response = client.post(base + "/items", headers=headers, json={"title": title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _types(db_session, wid):
    return [
        event.event_type
        for event in db_session.execute(
            select(Event).where(Event.workspace_id == wid).order_by(Event.seq)
        ).scalars().all()
    ]


# ---------------------------------------------------------------------------
# Claimed rows — acceptance criteria are entirely backend/persistence criteria
# ---------------------------------------------------------------------------


def test_pl010_cycles_schedule_assignment_dates_and_progress(client, db_session):
    """PL-010: a cycle can be scheduled, work items assigned, dates validated and progress reported."""
    wid, headers, pid, base = _setup(client)
    cycle = client.post(base + "/cycles", headers=headers, json={
        "name": "Sprint 1", "start_at": "2026-01-01T00:00:00Z",
        "end_at": "2026-01-14T00:00:00Z",
    })
    assert cycle.status_code == 201, cycle.text
    cid = cycle.json()["id"]
    assert client.post(base + "/cycles", headers=headers, json={
        "name": "Bad", "start_at": "2026-02-02T00:00:00Z",
        "end_at": "2026-02-01T00:00:00Z",
    }).status_code == 422
    assert client.patch(base + f"/cycles/{cid}", headers=headers,
                        json={"end_at": "2025-12-31T00:00:00Z"}).status_code == 422

    first = _item(client, base, headers, "A", status="done")
    second = _item(client, base, headers, "B", status="todo")
    assert client.post(base + f"/cycles/{cid}/items", headers=headers,
                       json={"item_id": first["id"]}).status_code == 201
    assert client.post(base + f"/cycles/{cid}/items", headers=headers,
                       json={"item_id": second["id"]}).status_code == 201
    outside = _item(client, base, headers, "Outside", due_at="2026-03-01T00:00:00Z")
    assert client.post(base + f"/cycles/{cid}/items", headers=headers,
                       json={"item_id": outside["id"]}).status_code == 422
    assert [row["id"] for row in client.get(
        base + f"/cycles/{cid}/items", headers=headers).json()] == [first["id"], second["id"]]

    progress = client.get(base + f"/cycles/{cid}/progress", headers=headers)
    assert progress.status_code == 200, progress.text
    assert progress.json() == {
        "cycle_id": cid, "total_items": 2, "todo_items": 1, "in_progress_items": 0,
        "done_items": 1, "completion_percent": 50.0, "dates_valid": True,
    }
    assert client.delete(base + f"/cycles/{cid}/items/{second['id']}",
                         headers=headers).status_code == 200
    assert client.get(base + f"/cycles/{cid}/progress", headers=headers).json()["total_items"] == 1

    other_wid, other_headers = _other_workspace(client, headers)
    assert client.patch(f"{API}/workspaces/{wid}/projects/missing/cycles/{cid}",
                        headers=headers, json={"name": "x"}).status_code == 404
    assert client.post(f"{API}/workspaces/{wid}/projects/{pid}/cycles/{cid}/items",
                       headers=other_headers, json={"item_id": first["id"]}).status_code == 403
    types = _types(db_session, wid)
    assert pj.PROJECT_CYCLE_UPDATED in types
    assert pj.PROJECT_ITEM_CYCLE_ASSIGNED in types
    assert all(e.workspace_id == wid for e in db_session.execute(
        select(Event).where(Event.workspace_id == wid)).scalars().all())


def test_pl011_modules_persist_lead_members_dates_state_and_progress(client, db_session):
    """PL-011: modules persist with lead, members, dates, state and work-item progress."""
    wid, headers, pid, base = _setup(client)
    teammate_headers, teammate_id = _member(client, wid, headers, "module-member@example.com")
    module = client.post(base + "/modules", headers=headers, json={
        "name": "Checkout", "description": "Checkout revamp", "lead_id": teammate_id,
        "start_at": "2026-03-01T00:00:00Z", "end_at": "2026-04-01T00:00:00Z",
        "state": "active",
    })
    assert module.status_code == 201, module.text
    mid = module.json()["id"]
    assert module.json()["lead_id"] == teammate_id
    assert module.json()["state"] == "active"
    assert client.post(base + "/modules", headers=headers, json={
        "name": "Bad", "state": "unknown"}).status_code == 422
    assert client.post(base + "/modules", headers=headers, json={
        "name": "Bad", "start_at": "2026-05-02T00:00:00Z",
        "end_at": "2026-05-01T00:00:00Z"}).status_code == 422

    members = client.get(base + f"/modules/{mid}/members", headers=headers)
    assert [m["user_id"] for m in members.json()] == [teammate_id]
    assert client.post(base + f"/modules/{mid}/members", headers=headers,
                       json={"user_id": teammate_id}).status_code == 409
    second = client.post(base + "/modules", headers=headers, json={"name": "Other module"})
    assert second.status_code == 201, second.text

    a = _item(client, base, headers, "A")
    b = _item(client, base, headers, "B")
    for item_id in (a["id"], b["id"]):
        response = client.post(base + f"/modules/{mid}/items", headers=headers,
                               json={"item_id": item_id})
        assert response.status_code == 201, response.text
    # Multi-module assignment: the same item also belongs to a second module.
    assert client.post(base + f"/modules/{second.json()['id']}/items", headers=headers,
                       json={"item_id": a["id"]}).status_code == 201
    assert client.post(base + f"/modules/{mid}/items", headers=headers,
                       json={"item_id": a["id"]}).status_code == 409
    assert client.patch(base + f"/items/{b['id']}", headers=headers,
                        json={"status": "done"}).status_code == 200
    progress = client.get(base + f"/modules/{mid}/progress", headers=headers)
    assert progress.status_code == 200, progress.text
    assert progress.json() == {
        "module_id": mid, "total_items": 2, "done_items": 1,
        "completion_percent": 50.0, "dates_valid": True,
    }
    assert len(client.get(base + f"/modules/{second.json()['id']}/items",
                          headers=headers).json()) == 1

    patched = client.patch(base + f"/modules/{mid}", headers=headers,
                           json={"state": "completed"})
    assert patched.status_code == 200 and patched.json()["state"] == "completed"
    assert client.delete(base + f"/modules/{mid}/members/{teammate_id}",
                         headers=headers).status_code == 409
    assert client.delete(base + f"/modules/{mid}", headers=headers).status_code == 200
    assert client.get(base + f"/modules/{mid}", headers=headers).status_code == 404
    types = _types(db_session, wid)
    assert {pj.PROJECT_MODULE_CREATED, pj.PROJECT_MODULE_UPDATED,
            pj.PROJECT_MODULE_DELETED} <= set(types)
    assert teammate_headers  # sharing/membership was a real active user


def test_pl012_sub_item_rollup_without_duplicate_rows(client, db_session):
    """PL-012: a child can be created from a parent and progress rolls up without duplicating rows."""
    wid, headers, pid, base = _setup(client)
    parent = _item(client, base, headers, "Parent")
    child = client.post(base + f"/items/{parent['id']}/sub-items", headers=headers,
                        json={"title": "Child"})
    assert child.status_code == 201, child.text
    grandchild = client.post(base + f"/items/{child.json()['id']}/sub-items", headers=headers,
                             json={"title": "Grandchild", "status": "done"})
    assert grandchild.status_code == 201, grandchild.text
    assert client.patch(base + f"/items/{grandchild.json()['id']}", headers=headers,
                        json={"status": "done"}).status_code == 200

    rollup = client.get(base + f"/items/{parent['id']}/rollup", headers=headers)
    assert rollup.status_code == 200, rollup.text
    assert rollup.json() == {
        "item_id": parent["id"], "total_items": 3, "todo_items": 2,
        "in_progress_items": 0, "done_items": 1, "completion_percent": 33.33,
    }
    rows = db_session.execute(
        select(func.count()).select_from(pj.ProjectItem).where(
            pj.ProjectItem.workspace_id == wid, pj.ProjectItem.project_id == pid
        )
    ).scalar_one()
    assert rows == 3
    child_ids = [row["id"] for row in client.get(
        base + f"/items/{parent['id']}/children", headers=headers).json()]
    assert child_ids == [child.json()["id"]]
    assert len(set(child_ids)) == len(child_ids)
    assert client.post(base + "/items/missing/sub-items", headers=headers,
                       json={"title": "orphan"}).status_code == 404


def test_pl015_parent_set_and_remove_updates_children(client, db_session):
    """PL-015: parent can be set or removed and child list updates accordingly."""
    wid, headers, pid, base = _setup(client)
    parent = _item(client, base, headers, "Parent")
    child = _item(client, base, headers, "Child")
    assert client.post(base + f"/items/{child['id']}/parent", headers=headers,
                       json={"parent_id": parent["id"]}).status_code == 200
    assert [row["id"] for row in client.get(
        base + f"/items/{parent['id']}/children", headers=headers).json()] == [child["id"]]
    assert client.post(base + f"/items/{parent['id']}/parent", headers=headers,
                       json={"parent_id": child["id"]}).status_code == 422
    assert client.post(base + f"/items/{child['id']}/parent", headers=headers,
                       json={"parent_id": child["id"]}).status_code == 422
    assert client.post(base + f"/items/{child['id']}/parent", headers=headers,
                       json={"parent_id": "missing"}).status_code == 404
    removed = client.delete(base + f"/items/{child['id']}/parent", headers=headers)
    assert removed.status_code == 200 and client.get(
        base + f"/items/{parent['id']}/children", headers=headers).json() == []
    activity = client.get(base + f"/items/{child['id']}/activity", headers=headers).json()
    parent_changes = [row for row in activity if row["field"] == "parent_item_id"]
    assert [row["new_value"] for row in parent_changes] == [parent["id"], None]
    assert parent_changes[0]["old_value"] is None
    assert pj.PROJECT_ITEM_PARENT_CHANGED in _types(db_session, wid)


def test_pl018_work_item_start_date_persists_and_is_validated(client):
    """PL-018: start date persists on work items and participates in date checks."""
    wid, headers, pid, base = _setup(client)
    item = client.post(base + "/items", headers=headers, json={
        "title": "Dated", "start_at": "2026-01-01T00:00:00Z",
        "due_at": "2026-01-10T00:00:00Z",
    })
    assert item.status_code == 201, item.text
    iid = item.json()["id"]
    assert item.json()["start_at"] is not None
    assert client.post(base + "/items", headers=headers, json={
        "title": "Bad", "start_at": "2026-02-10T00:00:00Z",
        "due_at": "2026-02-01T00:00:00Z",
    }).status_code == 422
    assert client.patch(base + f"/items/{iid}", headers=headers,
                        json={"start_at": "2026-02-01T00:00:00Z"}).status_code == 422
    assert client.patch(base + f"/items/{iid}", headers=headers,
                        json={"start_at": "2025-12-20T00:00:00Z"}).status_code == 200
    matching = client.get(base + "/items", headers=headers,
                          params={"start_from": "2025-12-01T00:00:00Z"}).json()
    assert [row["id"] for row in matching] == [iid]
    assert client.get(base + "/items", headers=headers,
                      params={"start_to": "2025-01-01T00:00:00Z"}).json() == []


def test_pl026_multiple_filters_combine_and_return_matching_items(client):
    """PL-026: multiple filters combine and return only matching items."""
    wid, headers, pid, base = _setup(client)
    label = client.post(base + "/labels", headers=headers, json={"name": "backend"})
    assert label.status_code == 201, label.text
    lid = label.json()["id"]
    cycle = client.post(base + "/cycles", headers=headers,
                        json={"name": "Filter cycle"}).json()
    a = _item(client, base, headers, "A", status="todo", priority="high", cycle_id=cycle["id"])
    b = _item(client, base, headers, "B", status="todo", priority="low")
    c = _item(client, base, headers, "C", status="done", priority="high")
    assert client.post(base + f"/items/{a['id']}/labels", headers=headers,
                       json={"label_id": lid}).status_code == 201
    assert client.post(base + f"/items/{b['id']}/labels", headers=headers,
                       json={"label_id": lid}).status_code == 201

    combined = client.get(base + "/items", headers=headers, params={
        "status": "todo", "priority": "high", "label": "backend", "cycle_id": cycle["id"],
    })
    assert combined.status_code == 200, combined.text
    assert [row["id"] for row in combined.json()] == [a["id"]]
    assert {row["id"] for row in client.get(
        base + "/items", headers=headers, params={"priority": "high"}).json()} == {
        a["id"], c["id"]
    }
    assert [row["id"] for row in client.get(
        base + "/items", headers=headers, params={"label": "backend", "priority": "low"}
    ).json()] == [b["id"]]
    assert client.get(base + "/items", headers=headers,
                      params={"priority": "urgentish"}).status_code == 422


def test_pl027_saved_view_restores_filters_layout_sort_and_sharing(client, db_session):
    """PL-027: a saved view restores filters, layout and sort for its owner and permitted sharers."""
    wid, headers, pid, base = _setup(client)
    shared_headers, shared_id = _member(client, wid, headers, "view-shared@example.com")
    other_headers, other_id = _member(client, wid, headers, "view-other@example.com")
    _item(client, base, headers, "Alpha", priority="high", status="todo")
    _item(client, base, headers, "Beta", priority="high", status="todo")
    _item(client, base, headers, "Gamma", priority="low", status="todo")

    assert client.post(base + "/views", headers=headers, json={
        "name": "Bad", "shared_with": ["not-a-member"]}).status_code == 422
    created = client.post(base + "/views", headers=headers, json={
        "name": "High priority", "filters": {"priority": "high", "status": "todo"},
        "layout": "board", "sort_by": "title", "sort_dir": "desc",
        "shared_with": [shared_id],
    })
    assert created.status_code == 201, created.text
    vid = created.json()["id"]

    restored = client.get(base + f"/views/{vid}", headers=headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["filters"] == {"priority": "high", "status": "todo"}
    assert restored.json()["layout"] == "board"
    assert restored.json()["sort_by"] == "title" and restored.json()["sort_dir"] == "desc"
    assert restored.json()["shared_with"] == [shared_id]
    assert client.get(base + f"/views/{vid}", headers=shared_headers).status_code == 200
    assert client.get(base + f"/views/{vid}", headers=other_headers).status_code == 404
    assert client.get(base + f"/views/{vid}", headers=headers).json()["shared_with"] == [shared_id]
    titles = [row["title"] for row in client.get(
        base + f"/views/{vid}/items", headers=headers).json()]
    assert titles == ["Beta", "Alpha"]
    assert [row["title"] for row in client.get(
        base + f"/views/{vid}/items", headers=shared_headers).json()] == ["Beta", "Alpha"]
    assert client.get(base + f"/views/{vid}/items", headers=other_headers).status_code == 404

    assert client.patch(base + f"/views/{vid}", headers=other_headers,
                        json={"layout": "list"}).status_code == 403
    patched = client.patch(base + f"/views/{vid}", headers=headers,
                           json={"filters": {"priority": "low"}})
    assert patched.status_code == 200 and patched.json()["filters"] == {"priority": "low"}
    assert [row["title"] for row in client.get(
        base + f"/views/{vid}/items", headers=headers).json()] == ["Gamma"]
    assert client.delete(base + f"/views/{vid}", headers=headers).status_code == 200
    assert client.get(base + f"/views/{vid}", headers=headers).status_code == 404
    types = set(_types(db_session, wid))
    assert {pj.PROJECT_VIEW_CREATED, pj.PROJECT_VIEW_UPDATED, pj.PROJECT_VIEW_DELETED} <= types
    assert other_id and shared_id


def test_pl030_threaded_comments_edit_and_item_scope(client, db_session):
    """PL-030: comments can be posted, replied to, edited and scoped to a work item."""
    wid, headers, pid, base = _setup(client)
    other_headers, other_id = _member(client, wid, headers, "comment-other@example.com")
    item = _item(client, base, headers, "Commented")
    root = client.post(base + "/comments", headers=headers,
                       json={"body": "Root", "item_id": item["id"]})
    assert root.status_code == 201, root.text
    reply = client.post(base + "/comments", headers=headers,
                        json={"body": "Reply", "parent_id": root.json()["id"]})
    assert reply.status_code == 201, reply.text
    assert reply.json()["parent_id"] == root.json()["id"]
    assert reply.json()["item_id"] == item["id"]
    other_item = _item(client, base, headers, "Other item")
    assert client.post(base + "/comments", headers=headers, json={
        "body": "Cross thread", "item_id": other_item["id"],
        "parent_id": root.json()["id"],
    }).status_code == 422
    scoped = client.get(base + "/comments", headers=headers,
                        params={"item_id": item["id"]}).json()
    assert {row["id"] for row in scoped} == {root.json()["id"], reply.json()["id"]}
    edited = client.patch(base + f"/comments/{reply.json()['id']}", headers=headers,
                          json={"body": "Edited reply"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["body"] == "Edited reply" and edited.json()["edited_at"] is not None
    assert client.patch(base + f"/comments/{reply.json()['id']}", headers=other_headers,
                        json={"body": "Hijack"}).status_code == 403
    assert client.patch(base + "/comments/missing", headers=headers,
                        json={"body": "x"}).status_code == 404
    assert pj.PROJECT_COMMENT_UPDATED in _types(db_session, wid)
    assert other_id


def test_pl079_activity_records_are_queryable_per_item_and_immutable(client, db_session):
    """PL-079: activity records are queryable per work item and immutable."""
    wid, headers, pid, base = _setup(client)
    first = _item(client, base, headers, "First")
    second = _item(client, base, headers, "Second")
    assert client.patch(base + f"/items/{first['id']}", headers=headers,
                        json={"status": "in_progress", "priority": "high"}).status_code == 200
    activity = client.get(base + f"/items/{first['id']}/activity", headers=headers)
    assert activity.status_code == 200, activity.text
    status_rows = [row for row in activity.json() if row["field"] == "status"]
    assert status_rows and status_rows[-1]["old_value"] == "todo"
    assert status_rows[-1]["new_value"] == "in_progress"
    priority_rows = [row for row in activity.json() if row["field"] == "priority"]
    assert priority_rows[-1]["old_value"] == "medium"
    assert priority_rows[-1]["new_value"] == "high"
    assert status_rows[-1]["actor_id"]
    assert all(row["item_id"] == first["id"] for row in activity.json())
    assert all(row["item_id"] == second["id"] for row in client.get(
        base + f"/items/{second['id']}/activity", headers=headers).json())

    before = db_session.execute(select(func.count()).select_from(pj.ItemActivity)).scalar_one()
    assert client.patch(base + f"/items/{first['id']}/activity",
                        headers=headers, json={"body": "x"}).status_code == 405
    assert client.delete(base + f"/items/{first['id']}/activity",
                         headers=headers).status_code == 405
    after = db_session.execute(select(func.count()).select_from(pj.ItemActivity)).scalar_one()
    assert before == after
    assert pj.PROJECT_ITEM_ACTIVITY_RECORDED in _types(db_session, wid)


def test_pl094_pages_crud_and_scope(client, db_session):
    """PL-094: pages can be created, read, updated and scoped to project/wiki/teamspace."""
    wid, headers, pid, base = _setup(client)
    created = {}
    for scope in ("project", "wiki", "teamspace"):
        response = client.post(base + "/pages", headers=headers,
                               json={"scope": scope, "title": scope.title(), "body": "# Body"})
        assert response.status_code == 201, response.text
        created[scope] = response.json()["id"]
    assert client.post(base + "/pages", headers=headers,
                       json={"scope": "unknown", "title": "x"}).status_code == 422
    assert len(client.get(base + "/pages", headers=headers).json()) == 3
    assert [row["id"] for row in client.get(
        base + "/pages", headers=headers, params={"scope": "wiki"}).json()] == [created["wiki"]]
    page = client.get(base + f"/pages/{created['project']}", headers=headers)
    assert page.status_code == 200 and page.json()["scope"] == "project"
    patched = client.patch(base + f"/pages/{created['project']}", headers=headers,
                           json={"body": "Updated", "scope": "wiki"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["body"] == "Updated" and patched.json()["scope"] == "wiki"
    assert client.delete(base + f"/pages/{created['teamspace']}",
                         headers=headers).status_code == 200
    assert client.get(base + f"/pages/{created['teamspace']}",
                      headers=headers).status_code == 404
    _, other_headers = _other_workspace(client, headers)
    assert client.get(base + f"/pages/{created['wiki']}",
                      headers=other_headers).status_code == 403
    assert {pj.PROJECT_PAGE_CREATED, pj.PROJECT_PAGE_UPDATED,
            pj.PROJECT_PAGE_DELETED} <= set(_types(db_session, wid))


# ---------------------------------------------------------------------------
# Backend-only coverage for UI-dependent rows (not claimed as closed rows)
# ---------------------------------------------------------------------------


def test_pl005_description_history_backend(client):
    """PL-005 backend: persisted, editable, versioned descriptions."""
    wid, headers, pid, base = _setup(client)
    item = _item(client, base, headers, "Described", description="First")
    iid = item["id"]
    first = client.get(base + f"/items/{iid}/description", headers=headers)
    assert first.status_code == 200 and first.json()["body"] == "First"
    assert first.json()["version"] == 1
    edited = client.patch(base + f"/items/{iid}/description", headers=headers,
                          json={"body": "Second"})
    assert edited.status_code == 200 and edited.json()["body"] == "Second"
    assert edited.json()["version"] == 2
    assert [row["body"] for row in edited.json()["versions"]] == ["First", "Second"]
    assert client.get(base + f"/items/{iid}/description", headers=headers).json()["version"] == 2
    assert client.patch(base + f"/items/{iid}/description", headers=headers,
                        json={"body": "  "}).status_code == 422


def test_pl007_priority_filter_backend(client):
    """PL-007 backend: priority persists and filters work items through the API."""
    wid, headers, pid, base = _setup(client)
    high = _item(client, base, headers, "High", priority="high")
    _item(client, base, headers, "Low", priority="low")
    assert client.patch(base + f"/items/{high['id']}", headers=headers,
                        json={"priority": "urgent"}).status_code == 200
    assert client.patch(base + f"/items/{high['id']}", headers=headers,
                        json={"priority": "critical"}).status_code == 422
    assert [row["id"] for row in client.get(
        base + "/items", headers=headers, params={"priority": "urgent"}).json()] == [high["id"]]


def test_pl009_labels_create_assign_and_filter_backend(client):
    """PL-009 backend: labels are created, assigned and used as API filters."""
    wid, headers, pid, base = _setup(client)
    created = client.post(base + "/labels", headers=headers,
                          json={"name": "frontend", "color": "blue"})
    assert created.status_code == 201, created.text
    lid = created.json()["id"]
    assert client.post(base + "/labels", headers=headers,
                       json={"name": "frontend"}).status_code == 409
    item = _item(client, base, headers, "Labelled")
    assert client.post(base + f"/items/{item['id']}/labels", headers=headers,
                       json={"label_id": lid}).status_code == 201
    assert [row["id"] for row in client.get(
        base + f"/items/{item['id']}/labels", headers=headers).json()] == [lid]
    assert [row["id"] for row in client.get(
        base + "/items", headers=headers, params={"label": "frontend"}).json()] == [item["id"]]
    assert client.delete(base + f"/items/{item['id']}/labels/{lid}",
                         headers=headers).status_code == 200
    assert client.get(base + "/items", headers=headers,
                      params={"label": "frontend"}).json() == []


def test_pl022_board_move_persists_state_and_emits_event(client, db_session):
    """PL-022 backend: a column move persists the state and emits an event."""
    wid, headers, pid, base = _setup(client)
    item = _item(client, base, headers, "Movable", status="todo")
    moved = client.post(base + f"/items/{item['id']}/move", headers=headers,
                        json={"status": "in_progress"})
    assert moved.status_code == 200 and moved.json()["status"] == "in_progress"
    assert client.post(base + f"/items/{item['id']}/move", headers=headers,
                       json={"status": "unknown"}).status_code == 422
    board = client.get(base + "/board", headers=headers)
    assert board.status_code == 200, board.text
    column = next(c for c in board.json()["columns"] if c["name"] == "in_progress")
    assert [row["id"] for row in column["items"]] == [item["id"]]
    events = db_session.execute(
        select(Event).where(Event.workspace_id == wid,
                            Event.event_type == pj.PROJECT_ITEM_MOVED)
    ).scalars().all()
    assert len(events) == 1 and events[0].payload["to"] == "in_progress"
    assert events[0].payload["from"] == "todo"


def test_pl029_item_activity_field_changes_backend(client, db_session):
    """PL-029 backend: field changes create immutable audit events with before/after values."""
    wid, headers, pid, base = _setup(client)
    item = _item(client, base, headers, "Audited")
    assert client.patch(base + f"/items/{item['id']}", headers=headers,
                        json={"title": "Renamed"}).status_code == 200
    rows = client.get(base + f"/items/{item['id']}/activity", headers=headers,
                      params={"field": "title"}).json()
    assert rows and rows[-1]["old_value"] == "Audited"
    assert rows[-1]["new_value"] == "Renamed"
    assert rows[-1]["event_type"] == pj.PROJECT_ITEM_UPDATED
    assert all(row["actor_id"] for row in rows)
