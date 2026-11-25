"""Clean-room P2/P3 workspace-tools acceptance tests.

Named rows: PL-089, PL-091, PL-092, PL-093, PL-107, PL-137, PL-138, PL-139,
PL-142, PL-145. No upstream source copied. No external service contacted.
"""

from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

from .conftest import auth, bootstrap
from novara_core.main import app


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in clean-room P2 acceptance tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


def _invite(client, owner_tok, email, role):
    reg = client.post("/api/v1/auth/register", json={
        "email": email, "password": "Password123!", "display_name": email.split("@")[0],
    })
    assert reg.status_code in (200, 201), reg.text
    reg_tok = reg.json()
    inv = client.post(f"/api/v1/workspaces/{owner_tok['workspace_id']}/invitations",
                      headers=auth(owner_tok["access_token"]), json={"email": email, "role": role})
    assert inv.status_code in (200, 201), inv.text
    acc = client.post("/api/v1/invitations/accept", headers=auth(reg_tok["access_token"]),
                      json={"token": inv.json()["invite_token"]})
    assert acc.status_code in (200, 201), acc.text
    return acc.json()["access_token"]


def _setup(client, db):
    from novara_core.models import Contact, User, new_id
    from novara_core.modules.projects import Project, ProjectItem

    owner_tok = bootstrap(client, email="pwt-owner@example.com", workspace_name="PWT WS")
    member_tok = _invite(client, owner_tok, "pwt-member@example.com", "sales_rep")
    ws_id = owner_tok["workspace_id"]
    h_owner = auth(owner_tok["access_token"])
    h_member = auth(member_tok)

    owner = db.query(User).filter(User.email == "pwt-owner@example.com").one()
    proj = Project(id=new_id(), workspace_id=ws_id, name="P1", status="active", owner_id=owner.id)
    db.add(proj); db.flush()
    item = ProjectItem(id=new_id(), workspace_id=ws_id, project_id=proj.id, title="Item 1", status="todo")
    item2 = ProjectItem(id=new_id(), workspace_id=ws_id, project_id=proj.id, title="Item 2", status="todo")
    contact = Contact(id=new_id(), workspace_id=ws_id, email="customer@example.com", full_name="Customer")
    db.add_all([item, item2, contact]); db.commit()
    return {
        "ws_id": ws_id, "proj_id": proj.id, "item_id": item.id, "item2_id": item2.id,
        "contact_id": contact.id, "h_owner": h_owner, "h_member": h_member,
        "owner_tok": owner_tok,
    }


def test_pl089_intake_form_creates_one_validated_request(client, db_session):
    ctx = _setup(client, db_session)
    ws, h = ctx["ws_id"], ctx["h_owner"]
    form = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/intake/forms", headers=h, json={
        "name": "Contact us",
        "fields": [
            {"key": "email", "type": "email", "required": True},
            {"key": "message", "type": "text", "required": True},
        ],
    })
    assert form.status_code == 201, form.text
    token = form.json()["token"]

    ok = client.post(f"/api/v1/intake/{token}/submit", json={
        "payload": {"email": "lead@example.com", "message": "Hello"},
    })
    assert ok.status_code == 201, ok.text

    bad = client.post(f"/api/v1/intake/{token}/submit", json={
        "payload": {"email": "not-an-email", "message": "Hello"},
    })
    assert bad.status_code == 422
    missing = client.post(f"/api/v1/intake/{token}/submit", json={"payload": {"email": "x@y.com"}})
    assert missing.status_code == 422

    reqs = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/intake/requests", headers=h)
    assert reqs.status_code == 200
    assert len(reqs.json()) == 1, "exactly one intake request should be created by one valid submission"


def test_pl091_user_assets_are_owner_scoped(client, db_session):
    ctx = _setup(client, db_session)
    ws, ho, hm = ctx["ws_id"], ctx["h_owner"], ctx["h_member"]
    made = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/user-assets", headers=ho,
                       json={"name": "my.txt", "content_type": "text/plain", "size_bytes": 12})
    assert made.status_code == 201, made.text
    aid = made.json()["id"]

    member_list = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/user-assets", headers=hm)
    assert member_list.status_code == 200
    assert all(a["id"] != aid for a in member_list.json())
    assert client.patch(f"/api/v1/workspaces/{ws}/workspace-tools/user-assets/{aid}",
                        headers=hm, json={"name": "hijack"}).status_code == 404
    assert client.delete(f"/api/v1/workspaces/{ws}/workspace-tools/user-assets/{aid}",
                         headers=hm).status_code == 404
    assert client.get(f"/api/v1/workspaces/{ws}/workspace-tools/user-assets", headers=ho).json()[0]["id"] == aid


def test_pl092_workspace_assets_are_admin_controlled_and_isolated(client, db_session):
    ctx = _setup(client, db_session)
    ws, ho, hm = ctx["ws_id"], ctx["h_owner"], ctx["h_member"]
    made = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/workspace-assets", headers=ho,
                       json={"name": "brand.png", "content_type": "image/png", "size_bytes": 99})
    assert made.status_code == 201, made.text
    aid = made.json()["id"]
    assert client.patch(f"/api/v1/workspaces/{ws}/workspace-tools/workspace-assets/{aid}",
                        headers=hm, json={"name": "x"}).status_code == 403
    assert client.delete(f"/api/v1/workspaces/{ws}/workspace-tools/workspace-assets/{aid}",
                         headers=hm).status_code == 403
    listed = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/workspace-assets", headers=hm)
    assert any(a["id"] == aid for a in listed.json())
    # a workspace the caller is not a member of is denied
    other = client.post(f"/api/v1/workspaces/{'a' * 36}/workspace-tools/workspace-assets", headers=ho,
                        json={"name": "x"})
    assert other.status_code in (401, 403)


def test_pl093_stickies_are_private_to_owner(client, db_session):
    ctx = _setup(client, db_session)
    ws, ho, hm = ctx["ws_id"], ctx["h_owner"], ctx["h_member"]
    made = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/stickies", headers=ho,
                       json={"title": "Remember", "body": "**draft**", "color": "blue", "formatted": True})
    assert made.status_code == 201, made.text
    sid = made.json()["id"]
    assert made.json()["color"] == "blue"
    member_list = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/stickies", headers=hm)
    assert member_list.json() == []
    assert client.patch(f"/api/v1/workspaces/{ws}/workspace-tools/stickies/{sid}",
                        headers=hm, json={"title": "stolen"}).status_code == 404
    assert client.delete(f"/api/v1/workspaces/{ws}/workspace-tools/stickies/{sid}",
                         headers=hm).status_code == 404
    own = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/stickies", headers=ho).json()
    assert own[0]["id"] == sid and own[0]["body"] == "**draft**"


def test_pl107_theme_preference_persists_and_is_light_only(client, db_session):
    ctx = _setup(client, db_session)
    ws, ho, hm = ctx["ws_id"], ctx["h_owner"], ctx["h_member"]
    saved = client.put(f"/api/v1/workspaces/{ws}/workspace-tools/themes", headers=ho,
                       json={"scope": "user", "palette": {"accent": "teal", "density": "compact"}})
    assert saved.status_code == 200, saved.text
    assert saved.json()["mode"] == "light"
    got = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/themes", headers=ho, params={"scope": "user"})
    assert got.status_code == 200
    assert got.json()["palette"] == {"accent": "teal", "density": "compact"}
    assert got.json()["default"] is False
    # workspace-wide theme is admin-controlled
    assert client.put(f"/api/v1/workspaces/{ws}/workspace-tools/themes", headers=ho,
                      json={"scope": "workspace", "palette": {"accent": "indigo"}}).status_code == 200
    assert client.put(f"/api/v1/workspaces/{ws}/workspace-tools/themes", headers=hm,
                      json={"scope": "workspace", "palette": {}}).status_code == 403


def test_pl137_pql_parses_safely_and_rejects_injection(client, db_session):
    ctx = _setup(client, db_session)
    ws, h = ctx["ws_id"], ctx["h_owner"]
    records = [
        {"status": "todo", "priority": 3, "title": "Fix login"},
        {"status": "done", "priority": 1, "title": "Login polish"},
    ]
    parsed = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/pql/parse", headers=h,
                         json={"expression": 'status = "todo" AND priority >= 2'})
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["sql_generated"] is False
    ev = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/pql/evaluate", headers=h,
                     json={"expression": 'status = "todo" AND priority >= 2', "records": records})
    assert ev.status_code == 200, ev.text
    assert ev.json()["count"] == 1
    assert ev.json()["matched"][0]["title"] == "Fix login"

    contains = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/pql/evaluate", headers=h,
                           json={"expression": 'title CONTAINS "login"', "records": records})
    assert contains.json()["count"] == 2

    for attack in [
        'status = "todo"; DROP TABLE work_items',
        'status = "todo" OR 1=1',
        "status = 'todo' -- comment",
    ]:
        bad = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/pql/parse", headers=h,
                          json={"expression": attack})
        assert bad.status_code == 422, f"injection not rejected: {attack}"


def test_pl138_customer_link_preserves_permissions(client, db_session):
    ctx = _setup(client, db_session)
    ws, ho, hm = ctx["ws_id"], ctx["h_owner"], ctx["h_member"]
    made = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/customers/links", headers=ho, json={
        "contact_id": ctx["contact_id"], "item_id": ctx["item_id"], "kind": "request",
    })
    assert made.status_code == 201, made.text
    assert made.json()["linked"] is True
    dup = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/customers/links", headers=ho, json={
        "contact_id": ctx["contact_id"], "item_id": ctx["item_id"], "kind": "request",
    })
    assert dup.json()["linked"] is False
    listed = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/customers/links", headers=hm,
                        params={"contact_id": ctx["contact_id"]})
    assert listed.status_code == 200 and len(listed.json()) == 1

    # read-only member has contact:read but not contact:write -> cannot link
    ro_tok = _invite(client, ctx["owner_tok"], "pwt-readonly@example.com", "read_only")
    denied = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/customers/links", headers=auth(ro_tok), json={
        "contact_id": ctx["contact_id"], "item_id": ctx["item2_id"],
    })
    assert denied.status_code == 403

    # a contact from another workspace is not linkable
    cross = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/customers/links", headers=ho, json={
        "contact_id": "a" * 36, "item_id": ctx["item2_id"],
    })
    assert cross.status_code == 404


def test_pl139_releases_link_items_without_data_loss(client, db_session):
    ctx = _setup(client, db_session)
    ws, h = ctx["ws_id"], ctx["h_owner"]
    made = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/releases", headers=h, json={
        "project_id": ctx["proj_id"], "name": "v1.0", "description": "First release",
    })
    assert made.status_code == 201, made.text
    rid = made.json()["id"]
    assert client.post(f"/api/v1/workspaces/{ws}/workspace-tools/releases/{rid}/items", headers=h,
                       json={"item_id": ctx["item_id"]}).status_code == 201
    assert client.post(f"/api/v1/workspaces/{ws}/workspace-tools/releases/{rid}/items", headers=h,
                       json={"item_id": ctx["item2_id"]}).status_code == 201
    dup = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/releases/{rid}/items", headers=h,
                      json={"item_id": ctx["item2_id"]})
    assert dup.json()["added"] is False
    listed = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/releases", headers=h,
                        params={"project_id": ctx["proj_id"]})
    found = [r for r in listed.json() if r["id"] == rid][0]
    assert set(found["item_ids"]) == {ctx["item_id"], ctx["item2_id"]}


def test_pl142_vote_toggle_counts_are_correct(client, db_session):
    ctx = _setup(client, db_session)
    ws, ho, hm = ctx["ws_id"], ctx["h_owner"], ctx["h_member"]
    item = ctx["item_id"]
    r1 = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/votes/toggle", headers=ho,
                     json={"item_id": item, "kind": "vote", "value": "up"})
    r2 = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/votes/toggle", headers=hm,
                     json={"item_id": item, "kind": "vote", "value": "up"})
    assert r1.status_code == 200 and r2.status_code == 200
    counts = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/votes/counts", headers=ho,
                        params={"item_id": item}).json()
    assert counts["counts"]["vote:up"] == 2 and counts["total"] == 2

    off = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/votes/toggle", headers=ho,
                      json={"item_id": item, "kind": "vote", "value": "up"})
    assert off.json()["active"] is False
    switch = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/votes/toggle", headers=ho,
                         json={"item_id": item, "kind": "vote", "value": "down"})
    assert switch.json()["active"] is True
    counts = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/votes/counts", headers=ho,
                        params={"item_id": item}).json()
    assert counts["counts"] == {"vote:up": 1, "vote:down": 1}


def test_pl145_hidden_navigation_unreachable_by_direct_url(client, db_session):
    ctx = _setup(client, db_session)
    ws, ho, hm = ctx["ws_id"], ctx["h_owner"], ctx["h_member"]
    made = client.post(f"/api/v1/workspaces/{ws}/workspace-tools/nav", headers=ho, json={
        "key": "reports", "label": "Reports", "route": "/reports", "visible": True,
    })
    assert made.status_code == 201, made.text
    assert client.get(f"/api/v1/workspaces/{ws}/workspace-tools/nav/target/reports", headers=hm).status_code == 200

    hidden = client.patch(f"/api/v1/workspaces/{ws}/workspace-tools/nav/reports", headers=ho,
                          json={"visible": False})
    assert hidden.status_code == 200
    assert client.get(f"/api/v1/workspaces/{ws}/workspace-tools/nav/target/reports", headers=hm).status_code == 404
    visible_list = client.get(f"/api/v1/workspaces/{ws}/workspace-tools/nav", headers=hm).json()
    assert all(n["key"] != "reports" for n in visible_list)

    # role restriction: visible but disallowed role cannot reach it directly
    client.post(f"/api/v1/workspaces/{ws}/workspace-tools/nav", headers=ho, json={
        "key": "billing", "label": "Billing", "route": "/billing",
        "visible": True, "allowed_roles": ["owner"],
    })
    assert client.get(f"/api/v1/workspaces/{ws}/workspace-tools/nav/target/billing", headers=hm).status_code == 403
