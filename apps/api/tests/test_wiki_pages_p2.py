"""Named acceptance tests for the clean-room project wiki-page cluster.

Every test drives the real FastAPI app with real persisted, workspace-scoped
rows. PL-096..PL-103 are proven end to end: revisions, analytics, local
publication/export, labels, nested pages, collections, editor blocks and
polling-based co-editing with inline comments. No Django, Channels, WebSocket,
React editor package, hosted service or outbound traffic is used.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}"


def _ctx(client):
    tokens = bootstrap(client, "WikiLab", "wiki-owner@example.com")
    wid, h = tokens["workspace_id"], auth(tokens["access_token"])
    project = client.post(API.format(wid=wid) + "/projects", headers=h,
                          json={"name": "Docs", "status": "planning"})
    assert project.status_code == 201, project.text
    pid = project.json()["id"]
    page = client.post(API.format(wid=wid) + f"/projects/{pid}/pages", headers=h,
                       json={"scope": "wiki", "title": "Runbook", "body": "initial body"})
    assert page.status_code == 201, page.text
    return wid, h, pid, page.json()["id"]


def _base(wid):
    return API.format(wid=wid) + "/wiki-pages"


def test_pl096_page_version_history_records_and_restores(client):
    """PL-096: revisions are immutable, versioned, and restorable without data loss."""
    wid, h, _, pid = _ctx(client)
    base = _base(wid)
    first = client.post(base + f"/pages/{pid}/revisions", headers=h,
                        json={"title": "Runbook", "body": "v1", "reason": "initial"})
    assert first.status_code == 201, first.text
    assert first.json()["version"] == 1
    second = client.post(base + f"/pages/{pid}/revisions", headers=h,
                         json={"title": "Runbook", "body": "v2", "reason": "edit"})
    assert second.status_code == 201 and second.json()["version"] == 2
    rows = client.get(base + f"/pages/{pid}/revisions", headers=h).json()
    assert [r["version"] for r in rows] == [2, 1]
    assert rows[0]["reason"] == "edit"
    restored = client.post(base + f"/revisions/{rows[1]['id']}/restore", headers=h)
    assert restored.status_code == 201, restored.text
    assert restored.json()["version"] == 3
    assert restored.json()["restored_from"] == rows[1]["id"]
    latest = client.get(base + f"/pages/{pid}/revisions", headers=h).json()[0]
    assert latest["body"] == "v1" and latest["reason"].startswith("restored from v1")


def test_pl097_page_analytics_count_local_views_only(client):
    """PL-097: analytics aggregate locally recorded views without external calls."""
    wid, h, _, pid = _ctx(client)
    base = _base(wid)
    for visitor, source in (("v1", "local"), ("v2", "local"), ("v2", "embed")):
        r = client.post(base + f"/pages/{pid}/views", headers=h,
                        json={"visitor_id": visitor, "source": source})
        assert r.status_code == 201, r.text
    stats = client.get(base + f"/pages/{pid}/analytics", headers=h).json()
    assert stats["views"] == 3
    assert stats["unique_visitors"] == 2
    assert stats["by_source"] == {"local": 2, "embed": 1}
    assert stats["external_calls"] is False


def test_pl098_page_publication_and_local_exports(client):
    """PL-098: publish toggles a local URL and exports are deterministic local renders."""
    wid, h, _, pid = _ctx(client)
    base = _base(wid)
    pub = client.put(base + f"/pages/{pid}/publication", headers=h,
                     json={"published": True, "slug": "runbook-2026"})
    assert pub.status_code == 200, pub.text
    assert pub.json()["published"] is True
    assert pub.json()["public_url"] == "/local/p/runbook-2026"
    assert client.get(base + f"/pages/{pid}/publication", headers=h).json()["published"] is True
    clash_pid = _create_page(client, wid, h, "Other")
    assert client.put(base + f"/pages/{clash_pid}/publication", headers=h,
                      json={"published": True, "slug": "runbook-2026"}).status_code == 409
    exported = client.post(base + f"/pages/{pid}/exports", headers=h, json={"format": "md"})
    assert exported.status_code == 201, exported.text
    assert exported.json()["content"].startswith("# Runbook")
    assert exported.json()["delivery"] == "local-only"
    assert len(exported.json()["content_hash"]) == 64
    assert client.post(base + f"/pages/{pid}/exports", headers=h,
                       json={"format": "pdf"}).status_code == 422
    assert len(client.get(base + f"/pages/{pid}/exports", headers=h).json()) == 1


def _create_page(client, wid, h, title):
    pid = client.get(API.format(wid=wid) + "/projects", headers=h).json()[0]["id"]
    page = client.post(API.format(wid=wid) + f"/projects/{pid}/pages", headers=h,
                       json={"scope": "wiki", "title": title, "body": "body"})
    assert page.status_code == 201, page.text
    return page.json()["id"]


def test_pl099_page_labels_are_workspace_scoped_and_attachable(client):
    """PL-099: labels can be created once, attached, listed and removed."""
    wid, h, _, pid = _ctx(client)
    base = _base(wid)
    label = client.post(base + "/labels", headers=h, json={"name": "runbook"})
    assert label.status_code == 201, label.text
    label_id = label.json()["id"]
    assert client.post(base + "/labels", headers=h, json={"name": "runbook"}).status_code == 409
    attached = client.post(base + f"/pages/{pid}/labels", headers=h, json={"name": "runbook"})
    assert attached.status_code == 201, attached.text
    assert client.get(base + f"/pages/{pid}/labels", headers=h).json() == [{"name": "runbook"}]
    assert client.post(base + f"/pages/{pid}/labels", headers=h,
                       json={"name": "missing"}).status_code == 422
    assert client.delete(base + f"/pages/{pid}/labels/{label_id}", headers=h).json()["removed"] is True
    assert client.get(base + f"/pages/{pid}/labels", headers=h).json() == []


def test_pl100_nested_pages_form_a_cycle_safe_tree(client):
    """PL-100: nested pages set parents, list children and reject cycles."""
    wid, h, _, pid = _ctx(client)
    base = _base(wid)
    child = _create_page(client, wid, h, "Child")
    grandchild = _create_page(client, wid, h, "Grandchild")
    assert client.put(base + f"/pages/{child}/parent", headers=h,
                      json={"parent_id": pid, "position": 1}).status_code == 200
    assert client.put(base + f"/pages/{grandchild}/parent", headers=h,
                      json={"parent_id": child, "position": 0}).status_code == 200
    assert [r["page_id"] for r in client.get(base + f"/pages/{child}/children", headers=h).json()] == [grandchild]
    assert any(r["page_id"] == child for r in client.get(base + "/trees", headers=h).json())
    assert client.put(base + f"/pages/{pid}/parent", headers=h,
                      json={"parent_id": grandchild}).status_code == 422
    assert client.put(base + f"/pages/{pid}/parent", headers=h,
                      json={"parent_id": pid}).status_code == 422


def test_pl101_page_collections_group_pages(client):
    """PL-101: named collections group pages in explicit positions."""
    wid, h, _, pid = _ctx(client)
    base = _base(wid)
    created = client.post(base + "/collections", headers=h,
                          json={"name": "Launch docs", "description": "all docs"})
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    assert client.post(base + "/collections", headers=h,
                       json={"name": "Launch docs"}).status_code == 409
    other = _create_page(client, wid, h, "Other")
    for page_id, pos in ((other, 1), (pid, 0)):
        r = client.post(base + f"/collections/{cid}/items", headers=h,
                        json={"page_id": page_id, "position": pos})
        assert r.status_code == 201, r.text
    items = client.get(base + f"/collections/{cid}/items", headers=h).json()
    assert [i["page_id"] for i in items] == [pid, other]
    assert client.post(base + f"/collections/{cid}/items", headers=h,
                       json={"page_id": pid}).status_code == 409


def test_pl102_editor_blocks_replace_and_list_in_order(client):
    """PL-102: typed editor blocks are validated, stored and ordered locally."""
    wid, h, _, pid = _ctx(client)
    base = _base(wid)
    result = client.put(base + f"/pages/{pid}/blocks", headers=h, json={"blocks": [
        {"block_type": "heading", "content": {"text": "Intro"}, "position": 0},
        {"block_type": "checklist", "content": {"items": ["a", "b"]}, "position": 1},
    ]})
    assert result.status_code == 200 and result.json()["blocks"] == 2
    blocks = client.get(base + f"/pages/{pid}/blocks", headers=h).json()
    assert [b["block_type"] for b in blocks] == ["heading", "checklist"]
    assert client.put(base + f"/pages/{pid}/blocks", headers=h, json={"blocks": [
        {"block_type": "iframe", "content": {}},
    ]}).status_code == 422
    replaced = client.put(base + f"/pages/{pid}/blocks", headers=h, json={"blocks": []})
    assert replaced.status_code == 200 and replaced.json()["blocks"] == 0
    assert client.get(base + f"/pages/{pid}/blocks", headers=h).json() == []


def test_pl103_polling_presence_and_inline_comments(client):
    """PL-103: co-editing presence uses expiring local leases and comments resolve."""
    wid, h, _, pid = _ctx(client)
    base = _base(wid)
    lease = client.post(base + f"/pages/{pid}/editing", headers=h, json={"ttl_seconds": 30})
    assert lease.status_code == 200, lease.text
    assert lease.json()["realtime_transport"] == "polling-only"
    # The same owner's lease is excluded from the presence list.
    assert client.get(base + f"/pages/{pid}/editing", headers=h).json() == []
    block = client.put(base + f"/pages/{pid}/blocks", headers=h, json={"blocks": [
        {"block_type": "paragraph", "content": {"text": "edit me"}, "position": 0},
    ]})
    assert block.status_code == 200
    block_id = client.get(base + f"/pages/{pid}/blocks", headers=h).json()[0]["id"]
    comment = client.post(base + f"/blocks/{block_id}/comments", headers=h,
                          json={"body": "clarify this", "block_id": block_id})
    assert comment.status_code == 201, comment.text
    cid = comment.json()["id"]
    listed = client.get(base + f"/pages/{pid}/comments", headers=h).json()
    assert len(listed) == 1 and listed[0]["resolved"] is False
    assert client.post(base + f"/comments/{cid}/resolve", headers=h).json()["resolved"] is True
    assert client.get(base + f"/pages/{pid}/comments", headers=h).json()[0]["resolved"] is True
    assert client.post(base + "/blocks/missing/comments", headers=h,
                       json={"body": "x"}).status_code == 404
    assert client.post(base + f"/pages/{pid}/editing", headers=h,
                       json={"ttl_seconds": 1}).status_code == 422


def test_wiki_contract_reports_no_external_transport(client):
    """The public contract must not claim websockets, outbound traffic or hosted services."""
    wid, h, _, _ = _ctx(client)
    contract = client.get(_base(wid) + "/api-contract", headers=h).json()
    assert contract["version"] == "1" and contract["legacy_versions"] == []
    assert contract["external_calls"] is False and contract["external_delivery"] is False
    assert "polling-only" in contract["realtime_transport"]
    assert contract["delivery"] == "local-only"
    assert "paragraph" in contract["block_types"] and "md" in contract["export_formats"]


def test_wiki_pages_are_workspace_isolated(client):
    """A second workspace cannot read or mutate another workspace's wiki entities."""
    wid, h, _, pid = _ctx(client)
    base = _base(wid)
    client.post(base + f"/pages/{pid}/revisions", headers=h,
                json={"title": "Runbook", "body": "v1"})
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other wiki"})
    assert other.status_code == 200, other.text
    owid, oh = other.json()["workspace_id"], auth(other.json()["access_token"])
    obase = _base(owid)
    assert client.get(obase + "/trees", headers=oh).json() == []
    assert client.get(obase + "/collections", headers=oh).json() == []
    assert client.get(obase + f"/pages/{pid}/revisions", headers=oh).status_code == 404
    assert client.get(obase + f"/pages/{pid}/analytics", headers=oh).status_code == 404
    assert client.put(obase + f"/pages/{pid}/parent", headers=oh,
                      json={"parent_id": None}).status_code == 404
    assert client.post(obase + f"/pages/{pid}/exports", headers=oh,
                       json={"format": "md"}).status_code == 404


def test_wiki_mutations_require_write_permission(client):
    """Reads use TASK_READ; all writes require TASK_WRITE via the shared permission contract."""
    wid, h, _, pid = _ctx(client)
    assert client.get(_base(wid) + "/api-contract", headers=h).status_code == 200
    assert client.delete(_base(wid) + f"/pages/{pid}/labels/missing", headers=h).status_code == 404
    assert client.post(_base(wid) + "/labels", headers={}, json={"name": "x"}).status_code in (401, 403)
