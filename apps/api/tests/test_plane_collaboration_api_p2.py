"""Named acceptance tests for clean-room work-item collaboration and API governance.

Every test drives the real FastAPI app with real persisted, workspace-scoped
rows and a real invited second member where permissions matter. PL-031, PL-032,
PL-039, PL-048, PL-050, PL-051, PL-130 and PL-132 are proven end to end. No
Plane source, Django transport, hosted endpoint, outbound HTTP or external
import provider is used; socket.socket.connect is patched to raise.
"""

from __future__ import annotations

import socket

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}"


def _ctx(client, name="Collab", email="collab-owner@example.com"):
    tokens = bootstrap(client, name, email)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return API.format(wid=wid) + "/work-collab"


def _no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("a collaboration endpoint attempted outbound traffic")
    monkeypatch.setattr(socket.socket, "connect", blocked)


def _project(client, wid, h, name="Delivery", restricted=False):
    response = client.post(API.format(wid=wid) + "/projects", headers=h,
                           json={"name": name, "restricted": restricted})
    assert response.status_code == 201, response.text
    return response.json()


def _item(client, wid, h, project_id, title):
    response = client.post(API.format(wid=wid) + "/projects/" + project_id + "/items",
                           headers=h, json={"title": title})
    assert response.status_code == 201, response.text
    return response.json()


def _member(client, wid, owner_headers, email, role="read_only"):
    invite = client.post(API.format(wid=wid) + "/invitations", headers=owner_headers,
                         json={"email": email, "role": role})
    assert invite.status_code == 200, invite.text
    registered = client.post("/api/v1/auth/register", json={
        "email": email, "password": "Password123!", "display_name": email.split("@")[0],
    })
    assert registered.status_code == 200, registered.text
    accepted = client.post("/api/v1/invitations/accept",
                           headers=auth(registered.json()["access_token"]),
                           json={"token": invite.json()["invite_token"]})
    assert accepted.status_code == 200, accepted.text
    headers = auth(accepted.json()["access_token"])
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return headers, me.json()["user"]["id"]


def _owner_id(client, headers):
    return client.get("/api/v1/auth/me", headers=headers).json()["user"]["id"]


def test_pl031_attachments_reference_real_stored_bytes(client, monkeypatch):
    """PL-031: attachment metadata references real stored bytes with permissions."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    project = _project(client, wid, h)
    item = _item(client, wid, h, project["id"], "Attach brief")
    uploaded = client.post(API.format(wid=wid) + "/storage/files", headers=h,
                           files={"file": ("brief.txt", b"real bytes", "text/plain")})
    assert uploaded.status_code == 201, uploaded.text
    file_row = uploaded.json()
    base = _base(wid) + "/items/" + item["id"] + "/attachments"
    created = client.post(base, headers=h, json={"file_id": file_row["id"], "label": "Brief"})
    assert created.status_code == 201, created.text
    assert created.json()["size_bytes"] == len(b"real bytes")
    assert client.post(base, headers=h, json={"file_id": file_row["id"]}).status_code == 409
    rows = client.get(base, headers=h).json()
    assert len(rows["attachments"]) == 1
    assert rows["attachments"][0]["checksum_sha256"] == file_row["checksum_sha256"]
    assert client.post(base, headers=h, json={"file_id": "missing-file"}).status_code == 404
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other attachments"})
    assert other.status_code == 200, other.text
    owid, oh = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.post(_base(owid) + "/items/" + item["id"] + "/attachments", headers=oh,
                       json={"file_id": file_row["id"]}).status_code == 404


def test_pl032_mentions_notify_and_subscribe_a_real_member(client, monkeypatch):
    """PL-032: a mention subscribes the member and emits a local notification event."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    member_h, member_id = _member(client, wid, h, "mentioned@example.com")
    project = _project(client, wid, h)
    item = _item(client, wid, h, project["id"], "Mention target")
    comment = client.post(API.format(wid=wid) + "/projects/" + project["id"] + "/comments",
                          headers=h, json={"item_id": item["id"], "body": "Please review"})
    assert comment.status_code == 201, comment.text
    response = client.post(_base(wid) + "/items/" + item["id"] + "/mentions", headers=h, json={
        "user_ids": [member_id], "body": "Please review",
        "comment_id": comment.json()["id"], "source": "comment",
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert member_id in body["subscribed"]
    assert body["notified"] is True and body["external_delivery"] is False
    subscribers = client.get(API.format(wid=wid) + "/work-item-planning/items/" +
                             item["id"] + "/subscribers", headers=h).json()["subscribers"]
    assert member_id in subscribers
    events = client.get(API.format(wid=wid) + "/events", headers=h).json()
    mention_events = [e for e in events if e["event_type"] == "collab.mention_created"]
    assert len(mention_events) == 1
    assert mention_events[0]["payload"]["external_delivery"] is False
    assert client.post(_base(wid) + "/items/" + item["id"] + "/mentions", headers=h, json={
        "user_ids": [member_id], "body": "Again", "source": "comment",
    }).status_code == 409
    assert client.post(_base(wid) + "/items/" + item["id"] + "/mentions", headers=h, json={
        "user_ids": ["not-a-member"], "body": "Unknown",
    }).status_code == 404


def test_pl039_team_collaboration_composes_comments_and_activity(client, monkeypatch):
    """PL-039: shared discussion and team activity are composed from local rows."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    project = _project(client, wid, h)
    item = _item(client, wid, h, project["id"], "Collaborate")
    note = client.post(_base(wid) + "/projects/" + project["id"] + "/team-notes", headers=h,
                       json={"body": "Kickoff complete", "item_id": item["id"]})
    assert note.status_code == 201, note.text
    comment = client.post(API.format(wid=wid) + "/projects/" + project["id"] + "/comments",
                          headers=h, json={"item_id": item["id"], "body": "Looks good"})
    assert comment.status_code == 201, comment.text
    result = client.get(_base(wid) + "/projects/" + project["id"] + "/collaboration",
                        headers=h).json()
    assert result["source"] == "local-records-only" and result["external_calls"] is False
    assert any(a["kind"] == "team_note" for a in result["activity"])
    assert any(c["body"] == "Looks good" for c in result["comments"])
    restricted = _project(client, wid, h, "Private", restricted=True)
    member_h, _ = _member(client, wid, h, "outside@example.com")
    assert client.get(_base(wid) + "/projects/" + restricted["id"] + "/collaboration",
                      headers=member_h).status_code == 404
    assert client.get(_base(wid) + "/projects/" + restricted["id"] + "/collaboration",
                      headers=h).status_code == 200


def test_pl048_cursor_pagination_has_no_duplicates_or_skips(client, monkeypatch):
    """PL-048: opaque cursors walk a large list forward and back without loss."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    project = _project(client, wid, h)
    expected = []
    for index in range(5):
        expected.append(_item(client, wid, h, project["id"], f"Item {index}")["id"])
    url = _base(wid) + "/projects/" + project["id"] + "/items/cursor"
    first = client.get(url, headers=h, params={"per_page": 2}).json()
    assert first["count"] == 2 and first["has_more"] is True
    assert first["prev_cursor"] is None and first["next_cursor"]
    seen = list(first["rows"])
    cursor = first["next_cursor"]
    second = None
    while cursor:
        page = client.get(url, headers=h, params={"per_page": 2, "cursor": cursor}).json()
        if second is None:
            second = page
        seen.extend(page["rows"])
        cursor = page["next_cursor"]
    assert [row["id"] for row in seen] == expected
    assert len({row["id"] for row in seen}) == 5
    previous = client.get(url, headers=h, params={
        "per_page": 2, "cursor": second["prev_cursor"],
    }).json()
    assert [row["id"] for row in previous["rows"]] == [row["id"] for row in first["rows"]]
    assert client.get(url, headers=h, params={"per_page": 2, "cursor": "forged"}).status_code == 400


def test_pl050_field_projection_and_expansion_are_allow_listed(client, monkeypatch):
    """PL-050: invalid fields are rejected and valid expansions return related rows."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    project = _project(client, wid, h)
    item = _item(client, wid, h, project["id"], "Shape me")
    client.post(API.format(wid=wid) + "/projects/" + project["id"] + "/comments",
                headers=h, json={"item_id": item["id"], "body": "Related comment"})
    url = _base(wid) + "/items/" + item["id"] + "/shaped"
    result = client.get(url, headers=h, params={
        "fields": "id,title", "expand": "project,comments",
    }).json()
    assert set(result["item"]) == {"id", "title", "project", "comments"}
    assert result["item"]["project"]["id"] == project["id"]
    assert result["item"]["comments"][0]["body"] == "Related comment"
    assert client.get(url, headers=h, params={"fields": "secret"}).status_code == 422
    assert client.get(url, headers=h, params={"expand": "everything"}).status_code == 422


def test_pl051_live_contract_and_documentation_routes(client, monkeypatch):
    """PL-051: schema and docs routes are reachable and describe every collab route."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    result = client.get(_base(wid) + "/api-contract", headers=h).json()
    assert result["openapi"].startswith("3.1")
    assert result["generated_from"] == "live FastAPI application"
    assert result["route_count"] >= 9
    assert result["documentation_routes"] == ["/openapi.json", "/docs", "/redoc"]
    assert result["external_delivery"] is False and result["external_calls"] is False
    operation_ids = {oid for route in result["work_collab_routes"]
                     for oid in route["operation_ids"]}
    assert "listWorkItemsByCursor" in operation_ids
    assert "getShapedWorkItem" in operation_ids
    assert "importWorkItemsFromCsv" in operation_ids
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert client.get(path).status_code == 200, path


def test_pl130_restricted_items_are_hidden_from_unauthorized_members(client, monkeypatch):
    """PL-130: restriction rules hide reads and refuse writes for other members."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    member_h, member_id = _member(client, wid, h, "restricted-viewer@example.com")
    project = _project(client, wid, h)
    item = _item(client, wid, h, project["id"], "Restricted")
    owner_id = _owner_id(client, h)
    saved = client.put(_base(wid) + "/items/" + item["id"] + "/restriction", headers=h, json={
        "allowed_user_ids": [owner_id], "reason": "owner-only review",
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["allowed_user_ids"] == [owner_id]
    guarded = _base(wid) + "/items/" + item["id"] + "/guarded"
    assert client.get(guarded, headers=h).status_code == 200
    assert client.get(guarded, headers=member_h).status_code == 404
    assert client.get(_base(wid) + "/items/" + item["id"] + "/shaped",
                      headers=member_h).status_code == 404
    assert client.put(_base(wid) + "/items/" + item["id"] + "/restriction",
                      headers=member_h, json={"allowed_user_ids": [member_id]}).status_code == 403
    assert client.get(_base(wid) + "/items/" + item["id"] + "/restriction",
                      headers=h).json()["restricted"] is True


def test_pl132_csv_import_creates_mapped_items_with_validation(client, monkeypatch):
    """PL-132: provider-neutral CSV import validates all rows before creating items."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    project = _project(client, wid, h)
    base = _base(wid) + "/projects/" + project["id"] + "/csv-import"
    result = client.post(base, headers=h, json={"csv_text": (
        "title,priority,status,description,tags\n"
        "Imported A,high,todo,First,alpha|beta\n"
        "Imported B,low,done,Second,\n"
    )})
    assert result.status_code == 201, result.text
    assert result.json()["count"] == 2
    assert result.json()["source"] == "provider-neutral-csv"
    items = client.get(API.format(wid=wid) + "/projects/" + project["id"] + "/items",
                       headers=h).json()
    titles = {row["title"] for row in items}
    assert {"Imported A", "Imported B"} <= titles
    imported_a = next(row for row in items if row["title"] == "Imported A")
    assert imported_a["description"] == "First"
    assert imported_a["priority"] == "high" and imported_a["status"] == "todo"
    imported_b = next(row for row in items if row["title"] == "Imported B")
    assert imported_b["status"] == "done" and imported_b["priority"] == "low"
    assert client.post(base, headers=h, json={"csv_text": (
        "title,priority\n,high\n"
    )}).status_code == 422
    assert len(client.get(API.format(wid=wid) + "/projects/" + project["id"] + "/items",
                          headers=h).json()) == 2
    events = client.get(API.format(wid=wid) + "/events", headers=h).json()
    assert any(e["event_type"] == "collab.csv_imported" for e in events)


def test_collaboration_workspace_isolation_and_permission_guards(client, monkeypatch):
    """All collab rows are workspace scoped and writes require task write."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    project = _project(client, wid, h)
    item = _item(client, wid, h, project["id"], "Isolated")
    assert client.get(_base(wid) + "/items/" + item["id"] + "/attachments",
                      headers=h).status_code == 200
    assert client.post(_base(wid) + "/items/" + item["id"] + "/mentions", headers={},
                       json={"user_ids": ["x"], "body": "x"}).status_code in (401, 403)
    assert client.put(_base(wid) + "/items/" + item["id"] + "/restriction", headers={},
                      json={"allowed_user_ids": ["x"]}).status_code in (401, 403)
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other collab"})
    assert other.status_code == 200, other.text
    owid, oh = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(owid) + "/items/" + item["id"] + "/attachments",
                      headers=oh).status_code == 404
    assert client.get(_base(owid) + "/projects/" + project["id"] + "/collaboration",
                      headers=oh).status_code == 404
    assert client.get(_base(owid) + "/items/" + item["id"] + "/restriction",
                      headers=oh).status_code == 404
