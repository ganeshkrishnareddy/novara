"""Named acceptance tests for the PL-021/PL-042/CW-023/CW-075 UI wiring cluster.

Every API assertion drives the real FastAPI app through the shared ``client``
and ``bootstrap``/``auth`` fixtures. Source assertions read the actual SPA so a
control without a live handler cannot pass. No external call is made here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .conftest import auth, bootstrap


API = "/api/v1"
APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def _source() -> str:
    assert APP_JS.is_file(), f"SPA source missing: {APP_JS}"
    return APP_JS.read_text(encoding="utf-8")


def _setup(client, name="UI P1", email="ui-p1-owner@example.com"):
    tokens = bootstrap(client, name, email)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    me = client.get(f"{API}/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return wid, headers, me.json()["user"]["id"]


def _project(client, wid, headers, name):
    response = client.post(
        f"{API}/workspaces/{wid}/projects", headers=headers, json={"name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _item(client, wid, headers, project_id, **fields):
    response = client.post(
        f"{API}/workspaces/{wid}/projects/{project_id}/items",
        headers=headers,
        json={"title": "Wired item", **fields},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _contact(client, wid, headers, email, **extra):
    response = client.post(
        f"{API}/workspaces/{wid}/contacts", headers=headers,
        json={"email": email, **extra},
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def _ticket(client, wid, headers, subject):
    response = client.post(
        f"{API}/workspaces/{wid}/tickets", headers=headers,
        json={"subject": subject, "body": "Local body"},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# PL-021 — work-item-aware grouped list
# ---------------------------------------------------------------------------


def test_pl021_grouped_work_item_list_uses_real_item_fields(client):
    """PL-021: grouped rows read real ItemOut fields, including dates/assignee."""
    wid, headers, actor_id = _setup(client, "PL021", "pl021-owner@example.com")
    project = _project(client, wid, headers, "PL021 project")
    now = datetime.now(timezone.utc)
    item = _item(
        client, wid, headers, project["id"],
        title="Grouped row",
        status="in_progress",
        priority="high",
        assignee_id=actor_id,
        start_at=(now - timedelta(days=2)).isoformat(),
        due_at=(now + timedelta(days=3)).isoformat(),
    )
    assert item["project_id"] == project["id"]
    for field in ("status", "state_group", "priority", "assignee_id", "due_at", "start_at"):
        assert field in item, f"ItemOut is missing {field}"
    assert item["status"] == "in_progress" and item["state_group"] == "in_progress"
    assert item["assignee_id"] == actor_id and item["start_at"] and item["due_at"]

    listed = client.get(
        f"{API}/workspaces/{wid}/projects/{project['id']}/items", headers=headers
    )
    assert listed.status_code == 200, listed.text
    assert any(row["id"] == item["id"] for row in listed.json())

    source = _source()
    for marker in (
        "This is the work-item list, not the legacy task list below.",
        'class="work-item-group"',
        "work-item-assignee-cell",
        "work-item-dates-cell",
        "const due = item.due_at ? fmtDate(item.due_at)",
        "'/projects/' + encodeURIComponent(p.id) + '/items'",
    ):
        assert source.count(marker) == 1, f"UI marker {marker!r} count={source.count(marker)}"


# ---------------------------------------------------------------------------
# PL-042 — delivery progress cards
# ---------------------------------------------------------------------------


def test_pl042_progress_cards_match_sql_counts(client):
    """PL-042: the cards render the exact buckets returned by /progress."""
    wid, headers, _ = _setup(client, "PL042", "pl042-owner@example.com")
    project = _project(client, wid, headers, "PL042 project")
    base = f"{API}/workspaces/{wid}/projects/{project['id']}"
    _item(client, wid, headers, project["id"], title="Pending", status="todo")
    for index in range(2):
        _item(client, wid, headers, project["id"],
              title=f"Shipped {index}", status="done")

    response = client.get(base + "/progress", headers=headers)
    assert response.status_code == 200, response.text
    progress = response.json()
    assert progress["project_id"] == project["id"]
    assert progress["total_items"] == 3
    assert progress["todo_items"] == 1
    assert progress["in_progress_items"] == 0
    assert progress["done_items"] == 2
    assert progress["completion_percent"] == 66.67

    source = _source()
    bucket_row = (
        "[['total_items', 'Total items'], ['todo_items', 'To do'], "
        "['in_progress_items', 'In progress'], ['done_items', 'Done']]"
    )
    assert source.count(bucket_row) == 1
    for marker in (
        "progress-bucket-card",
        "data-progress-percent",
        "String(progress.completion_percent || 0)",
    ):
        assert source.count(marker) == 1, f"UI marker {marker!r} count={source.count(marker)}"


# ---------------------------------------------------------------------------
# CW-023 — saved reply insertion
# ---------------------------------------------------------------------------


def test_cw023_saved_reply_ui_insert_expands_without_sending(client):
    """CW-023: expansion fills the draft and reports unresolved variables."""
    wid, headers, _ = _setup(client, "CW023UI", "cw023-ui-owner@example.com")
    contact = _contact(client, wid, headers, "cw023-ui@example.com", full_name="Ada")
    ticket = _ticket(client, wid, headers, "Insert question")
    base = f"{API}/workspaces/{wid}/tickets"
    created = client.post(base + "/saved-replies", headers=headers, json={
        "name": "ui-greeting",
        "body": "Hi {{ contact.name }} about {{ ticket.subject }} "
                "{{ contact.missing_field }}",
    })
    assert created.status_code == 201, created.text
    reply = created.json()

    expanded = client.post(
        base + f"/saved-replies/{reply['id']}/expand", headers=headers,
        json={"contact_id": contact["id"], "ticket_id": ticket["id"]},
    )
    assert expanded.status_code == 200, expanded.text
    data = expanded.json()
    assert "Hi Ada about Insert question" in data["body"]
    assert data["unresolved"] == ["contact.missing_field"]
    assert "{{ contact.missing_field }}" in data["body"]
    assert client.get(base + f"/{ticket['id']}/messages", headers=headers).json() == []

    source = _source()
    for marker in (
        "case 'insert-saved-reply':",
        "case 'expand-saved-reply':",
        'data-action="expand-saved-reply"',
        "'/tickets/saved-replies/' +",
        "applyExpandedReply(expanded.body || '', unresolved);",
        '<div class="info-banner" data-saved-reply-notice hidden></div>',
    ):
        assert source.count(marker) == 1, f"UI marker {marker!r} count={source.count(marker)}"


# ---------------------------------------------------------------------------
# CW-075 — segment reuse from the inbox toolbar
# ---------------------------------------------------------------------------


def test_cw075_segment_ui_reuse_filters_inbox(client):
    """CW-075: a stored segment resolves contacts and counts for the toolbar."""
    wid, headers, actor_id = _setup(client, "CW075UI", "cw075-ui-owner@example.com")
    base = f"{API}/workspaces/{wid}/tickets"
    alpha = _contact(client, wid, headers, "cw075-ui-a@example.com",
                     full_name="Alice", company_name="Alpha")
    beta = _contact(client, wid, headers, "cw075-ui-b@example.com",
                    full_name="Bob", company_name="Beta")
    for cid in (alpha["id"], beta["id"]):
        patched = client.patch(
            f"{API}/workspaces/{wid}/contacts/{cid}", headers=headers,
            json={"lifecycle_stage": "customer"},
        )
        assert patched.status_code == 200, patched.text

    definition = {"match": "all", "conditions": [
        {"field": "company_name", "op": "eq", "value": "Alpha"},
    ]}
    created = client.post(base + "/segments", headers=headers,
                          json={"name": "Alpha accounts", "definition": definition})
    assert created.status_code == 201, created.text
    segment = created.json()
    assert actor_id  # owner identity is used for all API calls via headers

    contacts_response = client.get(
        base + f"/segments/{segment['id']}/contacts", headers=headers
    )
    assert contacts_response.status_code == 200, contacts_response.text
    assert [row["id"] for row in contacts_response.json()] == [alpha["id"]]
    count_response = client.get(
        base + f"/segments/{segment['id']}/count", headers=headers
    )
    assert count_response.status_code == 200, count_response.text
    assert count_response.json() == {"segment_id": segment["id"], "count": 1}

    source = _source()
    for marker in (
        "kind === 'ticket-segment'",
        'data-change="ticket-segment"',
        "'/tickets/segments/' + encodeURIComponent(segmentId) + '/contacts'",
        "const segmentContacts = new Set(state.ticketSegmentContactIds);",
        "data-ticket-segment-info",
    ):
        assert source.count(marker) == 1, f"UI marker {marker!r} count={source.count(marker)}"
