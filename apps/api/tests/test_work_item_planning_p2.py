"""Named acceptance tests for the clean-room work-item planning cluster.

Every test drives the real FastAPI app with real persisted, workspace-scoped
rows. PL-013/014/016/020/023/024/025/035/036/037/136/141 are proven end to end
without Plane source, a scheduler daemon, a websocket transport or outbound
traffic.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}"
BASE = API + "/work-item-planning"
D1 = "2026-12-01T09:00:00+00:00"
D2 = "2026-12-05T17:00:00+00:00"
D3 = "2026-12-10T09:00:00+00:00"


def _ctx(client):
    tokens = bootstrap(client, "PlanningLab", "planning-owner@example.com")
    wid, h = tokens["workspace_id"], auth(tokens["access_token"])
    project = client.post(API.format(wid=wid) + "/projects", headers=h,
                          json={"name": "Delivery", "status": "planning"})
    assert project.status_code == 201, project.text
    return wid, h, project.json()["id"]


def _items(client, wid, h, pid, count=2):
    base = API.format(wid=wid)
    ids = []
    for index in range(count):
        item = client.post(base + f"/projects/{pid}/items", headers=h,
                           json={"title": f"Item {index + 1}", "status": "todo",
                                 "priority": "medium"})
        assert item.status_code == 201, item.text
        ids.append(item.json()["id"])
    return ids


def _base(wid):
    return BASE.format(wid=wid)


def test_planning_contract_declares_local_only_clean_room(client):
    """The contract must not claim legacy APIs, hosted services or a scheduler daemon."""
    wid, h, _ = _ctx(client)
    contract = client.get(_base(wid) + "/api-contract", headers=h).json()
    assert contract["version"] == "1" and contract["legacy_versions"] == []
    assert contract["delivery"] == "local-only"
    assert contract["external_calls"] is False and contract["external_delivery"] is False
    assert "explicit local materialisation" in contract["scheduler"]
    assert set(contract["relation_types"]) == {
        "relates_to", "duplicate_of", "implements", "implemented_by"}
    assert "finish_before" in contract["dependency_kinds"]
    assert "monthly" in contract["recurrence_frequencies"]


def test_pl013_relations_create_inverse_and_appear_on_both_items(client):
    """PL-013: relation creation creates the inverse relation in both work items."""
    wid, h, pid = _ctx(client)
    first, second = _items(client, wid, h, pid)
    base = _base(wid)
    created = client.post(base + f"/items/{first}/relations", headers=h,
                          json={"target_item_id": second, "relation_type": "implements",
                                "note": "clean-room link"})
    assert created.status_code == 201, created.text
    assert created.json()["created"] == 2
    forward = client.get(base + f"/items/{first}/relations", headers=h).json()
    inverse = client.get(base + f"/items/{second}/relations", headers=h).json()
    assert [r["relation_type"] for r in forward] == ["implements"]
    assert [r["relation_type"] for r in inverse] == ["implemented_by"]
    assert forward[0]["target_item_id"] == second
    assert inverse[0]["target_item_id"] == first
    assert client.post(base + f"/items/{first}/relations", headers=h,
                       json={"target_item_id": second, "relation_type": "implements"}).status_code == 409
    assert client.post(base + f"/items/{first}/relations", headers=h,
                       json={"target_item_id": first, "relation_type": "relates_to"}).status_code == 422
    assert client.post(base + f"/items/{first}/relations", headers=h,
                       json={"target_item_id": second, "relation_type": "unknown"}).status_code == 422


def test_pl014_typed_dependencies_detect_violations(client):
    """PL-014: typed dependencies persist, detect violations and clear when resolved."""
    wid, h, pid = _ctx(client)
    first, second = _items(client, wid, h, pid)
    base = _base(wid)
    dep = client.post(base + f"/items/{first}/dependencies", headers=h,
                      json={"depends_on_id": second, "kind": "blocked_by"})
    assert dep.status_code == 201, dep.text
    assert dep.json()["violation"] is True
    assert "not done" in dep.json()["reason"]
    listed = client.get(base + f"/items/{first}/dependencies", headers=h).json()
    assert listed[0]["kind"] == "blocked_by" and listed[0]["violation"] is True
    assert client.patch(base + f"/items/{second}/table-cell", headers=h,
                        json={"field": "status", "value": "done"}).status_code == 200
    assert client.get(base + f"/items/{first}/dependencies", headers=h).json()[0]["violation"] is False
    dated = client.post(base + f"/items/{second}/dependencies", headers=h,
                        json={"depends_on_id": first, "kind": "finish_before",
                              "target_date": D3})
    assert dated.status_code == 201 and dated.json()["target_date"].startswith("2026-12-10")
    assert client.post(base + f"/items/{first}/dependencies", headers=h,
                       json={"depends_on_id": first, "kind": "blocked_by"}).status_code == 422
    assert client.post(base + f"/items/{first}/dependencies", headers=h,
                       json={"depends_on_id": second, "kind": "unknown"}).status_code == 422


def test_pl016_estimates_persist_and_aggregate_by_project_and_cycle(client):
    """PL-016: estimate schemes and values persist and aggregate in project/cycle reports."""
    wid, h, pid = _ctx(client)
    first, second = _items(client, wid, h, pid)
    base = _base(wid)
    points = client.post(base + "/estimate-schemes", headers=h,
                         json={"name": "story-points", "kind": "points",
                               "values": {"fibonacci": [1, 2, 3, 5]}})
    assert points.status_code == 201, points.text
    risk = client.post(base + "/estimate-schemes", headers=h,
                       json={"name": "risk", "kind": "category",
                             "values": {"low": 1, "high": 2}})
    assert risk.status_code == 201, risk.text
    assert client.post(base + "/estimate-schemes", headers=h,
                       json={"name": "risk", "kind": "category",
                             "values": {"low": 1}}).status_code == 409
    assert client.post(base + f"/items/{first}/estimates", headers=h,
                       json={"scheme_id": points.json()["id"], "value": 3}).status_code == 201
    assert client.post(base + f"/items/{second}/estimates", headers=h,
                       json={"scheme_id": points.json()["id"], "value": 2}).status_code == 201
    assert client.post(base + f"/items/{first}/estimates", headers=h,
                       json={"scheme_id": risk.json()["id"], "value": 0,
                             "category": "high"}).status_code == 201
    assert client.post(base + f"/items/{second}/estimates", headers=h,
                       json={"scheme_id": risk.json()["id"], "value": 0,
                             "category": "extreme"}).status_code == 422
    aggregate = client.get(base + "/estimates/aggregate", headers=h,
                           params={"project_id": pid}).json()
    assert aggregate["total_points"] == 5 and aggregate["items"] == 3
    assert aggregate["by_category"] == {"high": 1}
    assert len(client.get(base + f"/items/{first}/estimates", headers=h).json()) == 2
    cycle = client.post(API.format(wid=wid) + f"/projects/{pid}/cycles", headers=h,
                        json={"name": "December", "start_at": "2026-12-01T00:00:00+00:00",
                              "end_at": "2026-12-31T23:59:59+00:00"})
    assert cycle.status_code == 201, cycle.text
    assigned = client.post(API.format(wid=wid) +
                           f"/projects/{pid}/cycles/{cycle.json()['id']}/items", headers=h,
                           json={"item_id": first})
    assert assigned.status_code == 201, assigned.text
    by_cycle = client.get(base + "/estimates/aggregate", headers=h,
                          params={"cycle_id": cycle.json()["id"]}).json()
    assert by_cycle["items"] == 2 and by_cycle["total_points"] == 3


def test_pl020_roadmap_groups_future_work_by_month_and_project(client):
    """PL-020: the roadmap groups future due dates by month and project."""
    wid, h, pid = _ctx(client)
    base = _base(wid)
    first, second = _items(client, wid, h, pid)
    assert client.patch(base + f"/items/{first}/schedule", headers=h,
                        json={"due_at": D1}).status_code == 200
    assert client.patch(base + f"/items/{second}/schedule", headers=h,
                        json={"due_at": D3}).status_code == 200
    roadmap = client.get(base + "/roadmap", headers=h, params={"project_id": pid}).json()
    assert roadmap["total"] == 2
    assert {g["month"] for g in roadmap["groups"]} == {"2026-12"}
    assert all(g["project_id"] == pid for g in roadmap["groups"])
    assert {i["id"] for g in roadmap["groups"] for i in g["items"]} == {first, second}
    assert client.get(base + "/roadmap", headers=h,
                      params={"project_id": "missing"}).status_code == 404


def test_pl023_calendar_places_items_on_due_dates(client):
    """PL-023: calendar entries are keyed by due date and link to the work item."""
    wid, h, pid = _ctx(client)
    base = _base(wid)
    first, second = _items(client, wid, h, pid)
    for item_id, due in ((first, D1), (second, D3)):
        assert client.patch(base + f"/items/{item_id}/schedule", headers=h,
                            json={"due_at": due}).status_code == 200
    calendar = client.get(base + "/calendar", headers=h,
                          params={"from": "2026-12-01", "to": "2026-12-05"}).json()
    assert calendar["total"] == 1
    assert [e["id"] for e in calendar["groups"]["2026-12-01"]] == [first]
    assert calendar["groups"]["2026-12-01"][0]["item_url"] == f"/local/projects/{pid}/items/{first}"
    assert client.get(base + "/calendar", headers=h).json()["total"] == 2


def test_pl024_timeline_persists_schedule_changes_and_marks_conflicts(client):
    """PL-024: schedule edits persist and dependency conflicts render on the timeline."""
    wid, h, pid = _ctx(client)
    base = _base(wid)
    first, second = _items(client, wid, h, pid)
    assert client.patch(base + f"/items/{first}/schedule", headers=h,
                        json={"start_at": D1, "due_at": D2}).status_code == 200
    saved = client.get(API.format(wid=wid) + f"/projects/{pid}/items", headers=h).json()
    row = next(r for r in saved if r["id"] == first)
    assert row["start_at"].startswith("2026-12-01") and row["due_at"].startswith("2026-12-05")
    assert client.patch(base + f"/items/{first}/schedule", headers=h,
                        json={"start_at": D3, "due_at": D1}).status_code == 422
    assert client.patch(base + f"/items/{second}/schedule", headers=h,
                        json={"due_at": D3}).status_code == 200
    dep = client.post(base + f"/items/{second}/dependencies", headers=h,
                      json={"depends_on_id": first, "kind": "finish_before"})
    assert dep.status_code == 201 and dep.json()["violation"] is True
    timeline = client.get(base + "/timeline", headers=h, params={"project_id": pid}).json()
    assert len(timeline["rows"]) == 2
    assert timeline["dependency_markers"] == 1
    assert timeline["conflicts"][0]["kind"] == "finish_before"


def test_pl025_table_cells_persist_with_validation(client):
    """PL-025: inline table edits persist and respect validation and permissions."""
    wid, h, pid = _ctx(client)
    base = _base(wid)
    item_id = _items(client, wid, h, pid, 1)[0]
    changed = client.patch(base + f"/items/{item_id}/table-cell", headers=h,
                           json={"field": "title", "value": "Edited in table"})
    assert changed.status_code == 200 and changed.json()["title"] == "Edited in table"
    assert client.patch(base + f"/items/{item_id}/table-cell", headers=h,
                        json={"field": "priority", "value": "urgent"}).json()["priority"] == "urgent"
    assert client.patch(base + f"/items/{item_id}/table-cell", headers=h,
                        json={"field": "status", "value": "invented"}).status_code == 422
    assert client.patch(base + f"/items/{item_id}/table-cell", headers=h,
                        json={"field": "due_at", "value": "not-a-date"}).status_code == 422
    assert client.patch(base + f"/items/{item_id}/table-cell", headers=h,
                        json={"field": "secret", "value": "x"}).status_code == 422
    assert client.patch(base + f"/items/{item_id}/table-cell", headers=h,
                        json={"field": "assignee_id", "value": "missing-user"}).status_code == 422
    assert client.patch(base + f"/items/{item_id}/table-cell", headers=h,
                        json={"field": "title", "value": "x" * 301}).status_code == 422
    rows = client.get(API.format(wid=wid) + f"/projects/{pid}/items", headers=h).json()
    assert rows[0]["title"] == "Edited in table" and rows[0]["priority"] == "urgent"


def test_pl035_updates_show_subitem_progress(client):
    """PL-035: short updates are separate records and report sub-item progress."""
    wid, h, pid = _ctx(client)
    base = _base(wid)
    parent, _ = _items(client, wid, h, pid)
    sub = client.post(API.format(wid=wid) + f"/projects/{pid}/items/{parent}/sub-items",
                      headers=h, json={"title": "Child via API"})
    assert sub.status_code == 201, sub.text
    assert client.patch(base + f"/items/{sub.json()['id']}/table-cell", headers=h,
                        json={"field": "status", "value": "done"}).status_code == 200
    posted = client.post(base + f"/items/{parent}/updates", headers=h,
                         json={"body": "Halfway there"})
    assert posted.status_code == 201, posted.text
    assert posted.json()["sub_items_total"] == 1 and posted.json()["sub_items_done"] == 1
    assert posted.json()["status"] == "todo"
    rows = client.get(base + f"/items/{parent}/updates", headers=h).json()
    assert len(rows) == 1 and rows[0]["body"] == "Halfway there"
    assert client.post(base + f"/items/{parent}/updates", headers=h, json={"body": ""}).status_code == 422


def test_pl036_templates_prefill_items_projects_and_pages(client):
    """PL-036: one template can instantiate prefilled items, projects and pages."""
    wid, h, pid = _ctx(client)
    base = _base(wid)
    created = client.post(base + "/templates", headers=h,
                          json={"name": "Release checklist", "target_kind": "item",
                                "payload": {"title": "Prefilled", "description": "from template",
                                            "priority": "high", "status": "in_progress",
                                            "due_at": D1}})
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    assert client.post(base + "/templates", headers=h,
                       json={"name": "Release checklist", "target_kind": "item"}).status_code == 409
    item = client.post(base + f"/templates/{tid}/instantiate", headers=h,
                       json={"project_id": pid})
    assert item.status_code == 201, item.text
    rows = client.get(API.format(wid=wid) + f"/projects/{pid}/items", headers=h).json()
    prefilled = next(r for r in rows if r["id"] == item.json()["item_id"])
    assert prefilled["title"] == "Prefilled" and prefilled["priority"] == "high"
    assert prefilled["description"] == "from template"
    project_template = client.post(base + "/templates", headers=h,
                                   json={"name": "New project", "target_kind": "project",
                                         "payload": {"name": "Templated project", "status": "active"}})
    assert project_template.status_code == 201
    project = client.post(base + f"/templates/{project_template.json()['id']}/instantiate",
                          headers=h, json={})
    assert project.status_code == 201 and project.json()["target_kind"] == "project"
    page_template = client.post(base + "/templates", headers=h,
                                json={"name": "ADR", "target_kind": "page",
                                      "payload": {"scope": "wiki", "title": "Decision",
                                                  "body": "context"}})
    assert page_template.status_code == 201
    page = client.post(base + f"/templates/{page_template.json()['id']}/instantiate",
                       headers=h, json={"project_id": pid})
    assert page.status_code == 201 and page.json()["title"] == "Decision"
    assert client.post(base + f"/templates/{tid}/instantiate", headers=h,
                       json={}).status_code == 422


def test_pl037_recurrence_materializes_on_demand_emits_event(client):
    """PL-037: a recurrence rule creates the next item at the expected time."""
    wid, h, pid = _ctx(client)
    base = _base(wid)
    item_id = _items(client, wid, h, pid, 1)[0]
    rule = client.post(base + f"/items/{item_id}/recurrences", headers=h,
                       json={"frequency": "weekly", "interval": 1, "next_at": D1})
    assert rule.status_code == 201, rule.text
    rid = rule.json()["id"]
    assert client.post(base + f"/recurrences/{rid}/materialize", headers=h,
                       json={"as_of": "2026-11-30T00:00:00+00:00"}).json()["created"] is False
    made = client.post(base + f"/recurrences/{rid}/materialize", headers=h,
                       json={"as_of": D1})
    assert made.status_code == 200 and made.json()["created"] is True
    assert made.json()["next_at"].startswith("2026-12-08")
    assert made.json()["scheduler"] == "explicit local materialisation only"
    duplicated = client.post(base + f"/recurrences/{rid}/materialize", headers=h,
                             json={"as_of": "2026-12-02T00:00:00+00:00"})
    assert duplicated.json()["created"] is False
    rows = client.get(API.format(wid=wid) + f"/projects/{pid}/items", headers=h).json()
    assert any(r["title"] == "Item 1 (recurring)" for r in rows)
    events = client.get(API.format(wid=wid) + "/events", headers=h).json()
    assert any(e["event_type"] == "planning.item_recurred" for e in events), \
        "recurrence must publish an audited event"


def test_pl136_worklogs_persist_and_sum_per_item(client):
    """PL-136: worklogs persist and sum correctly for one work item."""
    wid, h, pid = _ctx(client)
    base = _base(wid)
    item_id = _items(client, wid, h, pid, 1)[0]
    for minutes, note in ((90, "design"), (45, "review")):
        entry = client.post(base + f"/items/{item_id}/time-logs", headers=h,
                            json={"minutes": minutes, "note": note, "logged_at": D1})
        assert entry.status_code == 201, entry.text
    logs = client.get(base + f"/items/{item_id}/time-logs", headers=h).json()
    assert logs["total_minutes"] == 135 and logs["total_hours"] == 2.25
    assert [e["note"] for e in logs["entries"]] == ["design", "review"]
    assert client.post(base + f"/items/{item_id}/time-logs", headers=h,
                       json={"minutes": 0}).status_code == 422


def test_pl141_subscribers_drive_notification_recipients(client):
    """PL-141: the subscriber set is the exact notification recipient source."""
    wid, h, pid = _ctx(client)
    base = _base(wid)
    item_id = _items(client, wid, h, pid, 1)[0]
    user_id = client.get("/api/v1/auth/me", headers=h).json()["user"]["id"]
    assert client.get(base + f"/items/{item_id}/notification-recipients",
                      headers=h).json()["recipients"] == []
    added = client.post(base + f"/items/{item_id}/subscribers", headers=h,
                        json={"user_id": user_id})
    assert added.status_code == 201, added.text
    assert added.json()["recipients"] == [user_id]
    recipients = client.get(base + f"/items/{item_id}/notification-recipients", headers=h).json()
    assert recipients["recipients"] == [user_id]
    assert recipients["source"] == "planning_subscribers"
    assert recipients["external_delivery"] is False
    assert client.post(base + f"/items/{item_id}/subscribers", headers=h,
                       json={"user_id": user_id}).status_code == 409
    removed = client.delete(base + f"/items/{item_id}/subscribers/{user_id}", headers=h)
    assert removed.status_code == 200 and removed.json()["recipients"] == []
    assert client.post(base + f"/items/{item_id}/subscribers", headers=h,
                       json={"user_id": "missing-user"}).status_code == 404


def test_planning_rows_are_workspace_isolated_and_write_protected(client):
    """A second workspace cannot see planning rows; unauthenticated writes fail."""
    wid, h, pid = _ctx(client)
    base = _base(wid)
    item_id = _items(client, wid, h, pid, 1)[0]
    client.post(base + f"/items/{item_id}/relations", headers=h,
                json={"target_item_id": item_id, "relation_type": "relates_to"})
    client.post(base + f"/items/{item_id}/time-logs", headers=h, json={"minutes": 15})
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other planning"})
    assert other.status_code == 200, other.text
    owid, oh = other.json()["workspace_id"], auth(other.json()["access_token"])
    obase = _base(owid)
    assert client.get(obase + "/templates", headers=oh).json() == []
    assert client.get(obase + "/calendar", headers=oh).json()["total"] == 0
    assert client.get(obase + f"/items/{item_id}/relations", headers=oh).status_code == 404
    assert client.get(obase + f"/items/{item_id}/time-logs", headers=oh).status_code == 404
    assert client.post(obase + "/templates", headers=oh,
                       json={"name": "x", "target_kind": "item"}).status_code == 201
    assert client.post(base + "/templates", headers={},
                       json={"name": "x", "target_kind": "item"}).status_code in (401, 403)
