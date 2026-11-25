"""Clean-room P2 project governance acceptance tests.

Named rows: PL-034, PL-095, PL-106, PL-119, PL-120, PL-128, PL-129, PL-140.
No upstream source copied. No external service contacted.
"""

from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

from .conftest import auth, bootstrap
from novara_core.main import app


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    # Block real external calls. Loopback stays allowed because Windows' asyncio
    # ProactorEventLoop builds its self-pipe with socket.socketpair(), which
    # connects to 127.0.0.1 when TestClient starts the app lifespan.
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in clean-room P2 acceptance tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)



def _setup(client, db):
    from novara_core.models import User, new_id
    from novara_core.modules.projects import Project, ProjectItem
    owner_tok = bootstrap(client, email="pg-owner@example.com", workspace_name="PG WS")
    member_reg = client.post("/api/v1/auth/register", json={"email": "pg-member@example.com", "password": "Password123!", "display_name": "Member"})
    assert member_reg.status_code in (200, 201), member_reg.text
    member_tok = member_reg.json()
    # invite member
    inv = client.post(f"/api/v1/workspaces/{owner_tok['workspace_id']}/invitations", headers=auth(owner_tok['access_token']), json={"email":"pg-member@example.com","role":"admin"})
    assert inv.status_code in (200,201), inv.text
    acc = client.post("/api/v1/invitations/accept", headers=auth(member_tok['access_token']), json={"token": inv.json()['invite_token']})
    assert acc.status_code in (200,201), acc.text
    ws_id = owner_tok["workspace_id"]
    h_owner = auth(owner_tok["access_token"])
    h_member = auth(acc.json()["access_token"])
    owner = db.query(User).filter(User.email=="pg-owner@example.com").one()
    member = db.query(User).filter(User.email=="pg-member@example.com").one()
    proj = Project(id=new_id(), workspace_id=ws_id, name="P1", status="active", owner_id=owner.id)
    db.add(proj); db.flush()
    proj_id = proj.id
    item = ProjectItem(id=new_id(), workspace_id=ws_id, project_id=proj_id, title="Item 1", status="todo")
    item2 = ProjectItem(id=new_id(), workspace_id=ws_id, project_id=proj_id, title="Item 2", status="todo")
    db.add_all([item,item2]); db.commit()
    item_id, item2_id = item.id, item2.id
    owner_id, member_id = owner.id, member.id
    return ws_id, proj_id, item_id, item2_id, owner_id, member_id, h_owner, h_member


def test_pl034_project_updates_reactions_comments(client, db_session):
    ws_id, proj_id, item_id, _, owner_id, member_id, h_owner, h_member = _setup(client, db_session)
    r = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/updates", headers=h_owner,
                    json={"project_id": proj_id, "health": "on_track", "title": "Weekly", "body": "All good"})
    assert r.status_code == 201, r.text
    upd = r.json()
    assert upd["health"] == "on_track"
    r2 = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/updates/{upd['id']}/reactions", headers=h_member, json={"emoji": "👍"})
    assert r2.status_code == 201
    r3 = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/updates/{upd['id']}/comments", headers=h_member, json={"body": "Nice"})
    assert r3.status_code == 201
    lst = client.get(f"/api/v1/workspaces/{ws_id}/project-governance/updates", headers=h_member, params={"project_id": proj_id})
    assert lst.status_code == 200
    assert any(u["id"] == upd["id"] for u in lst.json())


def test_pl095_workspace_wiki_permission_checked(client, db_session):
    ws_id, proj_id, *_rest, h_owner, h_member = _setup(client, db_session)
    r = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/wiki", headers=h_owner,
                    json={"slug": "home", "title": "Home", "body": "# Hello"})
    assert r.status_code == 201, r.text
    got = client.get(f"/api/v1/workspaces/{ws_id}/project-governance/wiki/home", headers=h_member)
    assert got.status_code == 200
    assert got.json()["title"] == "Home"
    upd = client.patch(f"/api/v1/workspaces/{ws_id}/project-governance/wiki/home", headers=h_member, json={"body": "updated"})
    assert upd.status_code == 200
    # non-member/no-auth gets 401/403
    bad = client.get(f"/api/v1/workspaces/{ws_id}/project-governance/wiki/home")
    assert bad.status_code in (401, 403)


def test_pl106_teamspaces_group_members_and_projects(client, db_session):
    ws_id, proj_id, _i1, _i2, _owner_id, member_id, h_owner, h_member = _setup(client, db_session)
    r = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/teamspaces", headers=h_owner, json={"name": "Platform"})
    assert r.status_code == 201, r.text
    ts = r.json()
    r2 = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/teamspaces/{ts['id']}/members", headers=h_owner, json={"user_id": member_id})
    assert r2.status_code == 201
    r3 = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/teamspaces/{ts['id']}/projects", headers=h_owner, json={"project_id": proj_id})
    assert r3.status_code == 201
    lst = client.get(f"/api/v1/workspaces/{ws_id}/project-governance/teamspaces", headers=h_owner)
    assert lst.status_code == 200
    found = [t for t in lst.json() if t["id"] == ts["id"]][0]
    assert member_id in found["member_ids"]
    assert proj_id in found["project_ids"]


def test_pl119_multiple_workflows_transition_rules(client, db_session):
    ws_id, proj_id, item_id, *_rest, h_owner, h_member = _setup(client, db_session)
    wf = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/workflows", headers=h_owner, json={
        "project_id": proj_id, "name": "Review",
        "states": [{"key": "draft", "label": "Draft"}, {"key": "review", "label": "Review"}, {"key": "done", "label": "Done"}],
        "transitions": [{"from": "draft", "to": "review"}, {"from": "review", "to": "done"}],
    })
    assert wf.status_code == 201, wf.text
    wf_id = wf.json()["id"]
    ok = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/workflows/{wf_id}/transition", headers=h_owner,
                     json={"item_id": item_id, "from_state": "draft", "to_state": "review"})
    assert ok.status_code == 200
    bad = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/workflows/{wf_id}/transition", headers=h_owner,
                      json={"item_id": item_id, "from_state": "review", "to_state": "draft"})
    assert bad.status_code == 409


def test_pl120_approvals_require_assigned_approver(client, db_session):
    ws_id, proj_id, item_id, _, owner_id, member_id, h_owner, h_member = _setup(client, db_session)
    req = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/approvals", headers=h_owner,
                      json={"project_id": proj_id, "item_id": item_id, "approver_id": member_id})
    assert req.status_code == 201, req.text
    aid = req.json()["id"]
    # owner cannot decide
    denied = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/approvals/{aid}/decide", headers=h_owner, json={"decision": "approved"})
    assert denied.status_code == 403
    ok = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/approvals/{aid}/decide", headers=h_member, json={"decision": "approved", "note": "ok"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"


def test_pl128_pl129_private_and_published_dashboards(client, db_session):
    ws_id, proj_id, *_rest, h_owner, h_member = _setup(client, db_session)
    d = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/dashboards", headers=h_owner, json={"name": "Private", "config": {"k": 1}})
    assert d.status_code == 201
    did = d.json()["id"]
    # member cannot see private dashboard
    lst_member = client.get(f"/api/v1/workspaces/{ws_id}/project-governance/dashboards", headers=h_member)
    assert all(x["id"] != did for x in lst_member.json())
    pub = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/dashboards/{did}/release", headers=h_owner)
    assert pub.status_code == 200
    token = pub.json()["publish_token"]
    assert token
    public = client.get(f"/api/v1/workspaces/{ws_id}/project-governance/dashboards/shared/{token}")
    assert public.status_code == 200
    assert public.json()["read_only"] is True
    inv = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/dashboards/{did}/invalidate", headers=h_owner)
    assert inv.status_code == 200
    gone = client.get(f"/api/v1/workspaces/{ws_id}/project-governance/dashboards/shared/{token}")
    assert gone.status_code == 404


def test_pl140_epics_group_children(client, db_session):
    ws_id, proj_id, item_id, item2_id, owner_id, _member_id, h_owner, h_member = _setup(client, db_session)
    e = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/epics", headers=h_owner, json={"project_id": proj_id, "title": "Epic 1"})
    assert e.status_code == 201, e.text
    eid = e.json()["id"]
    c1 = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/epics/{eid}/children", headers=h_owner, json={"item_id": item_id})
    c2 = client.post(f"/api/v1/workspaces/{ws_id}/project-governance/epics/{eid}/children", headers=h_owner, json={"item_id": item2_id})
    assert c1.status_code == 201 and c2.status_code == 201
    lst = client.get(f"/api/v1/workspaces/{ws_id}/project-governance/epics", headers=h_owner, params={"project_id": proj_id})
    assert lst.status_code == 200
    found = [x for x in lst.json() if x["id"] == eid][0]
    assert set(found["child_item_ids"]) == {item_id, item2_id}
