"""Named acceptance tests for the P0 Plane project-access cluster.

PL-003: project membership (lead/default assignee/subscriber) is managed
independently of workspace membership. PL-040: project roles are enforced on
every project route, with read and write checked from the HTTP verb. Public
projects retain the workspace-role fallback so existing behaviour is intact.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.models import Event
from novara_core.modules import projects as pj

from .conftest import auth, bootstrap


def _workspace_member(client, wid, owner_headers, email, role="sales_rep"):
    invite = client.post(
        f"/api/v1/workspaces/{wid}/invitations", headers=owner_headers,
        json={"email": email, "role": role},
    )
    assert invite.status_code == 200, invite.text
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": email.split("@")[0]},
    )
    assert registered.status_code == 200, registered.text
    accepted = client.post(
        "/api/v1/invitations/accept", headers=auth(registered.json()["access_token"]),
        json={"token": invite.json()["invite_token"]},
    )
    assert accepted.status_code == 200, accepted.text
    teammate = auth(accepted.json()["access_token"])
    me = client.get("/api/v1/auth/me", headers=teammate)
    assert me.status_code == 200, me.text
    return teammate, me.json()["user"]["id"]


def _project(client, wid, headers, name="Release", restricted=True):
    created = client.post(
        f"/api/v1/workspaces/{wid}/projects", headers=headers,
        json={"name": name, "restricted": restricted},
    )
    assert created.status_code == 201, created.text
    return created.json()


def _types(db_session, wid):
    return [e.event_type for e in db_session.execute(
        select(Event).where(Event.workspace_id == wid).order_by(Event.seq)
    ).scalars().all()]


def test_project_membership_registry_and_roles(client, db_session):
    tokens = bootstrap(client)
    wid, owner = tokens["workspace_id"], auth(tokens["access_token"])
    project = _project(client, wid, owner)
    pid = project["id"]
    assert project["restricted"] is True

    members = client.get(f"/api/v1/workspaces/{wid}/projects/{pid}/members", headers=owner)
    assert members.status_code == 200, members.text
    assert len(members.json()) == 1
    creator = members.json()[0]
    assert creator["role"] == "lead" and creator["is_default_assignee"] is True

    teammate, teammate_id = _workspace_member(client, wid, owner, "plmember@example.com")
    added = client.post(
        f"/api/v1/workspaces/{wid}/projects/{pid}/members", headers=owner,
        json={"user_id": teammate_id, "role": "member",
              "is_default_assignee": True, "subscribed": False},
    )
    assert added.status_code == 201, added.text
    assert added.json()["role"] == "member"
    assert added.json()["is_default_assignee"] is True
    assert added.json()["subscribed"] is False
    assert added.json()["email"] == "plmember@example.com"

    # Only one default assignee at a time.
    rows = client.get(f"/api/v1/workspaces/{wid}/projects/{pid}/members", headers=owner).json()
    assert sum(1 for row in rows if row["is_default_assignee"]) == 1

    changed = client.patch(
        f"/api/v1/workspaces/{wid}/projects/{pid}/members/{teammate_id}",
        headers=owner, json={"role": "viewer", "subscribed": True},
    )
    assert changed.status_code == 200 and changed.json()["role"] == "viewer"
    assert changed.json()["subscribed"] is True

    removed = client.delete(
        f"/api/v1/workspaces/{wid}/projects/{pid}/members/{teammate_id}", headers=owner
    )
    assert removed.status_code == 200 and removed.json()["removed"] is True
    remaining = client.get(f"/api/v1/workspaces/{wid}/projects/{pid}/members",
                           headers=owner).json()
    assert len(remaining) == 1
    assert remaining[0]["user_id"] == creator["user_id"]
    assert remaining[0]["id"] == creator["id"]

    types = _types(db_session, wid)
    assert types.count(pj.PROJECT_MEMBER_ADDED) == 1
    assert types.count(pj.PROJECT_MEMBER_UPDATED) == 1
    assert types.count(pj.PROJECT_MEMBER_REMOVED) == 1


def test_project_roles_enforce_read_write_on_every_route(client):
    tokens = bootstrap(client)
    wid, owner = tokens["workspace_id"], auth(tokens["access_token"])
    project = _project(client, wid, owner)
    pid = project["id"]
    teammate, teammate_id = _workspace_member(client, wid, owner, "plroles@example.com")
    base = f"/api/v1/workspaces/{wid}/projects"
    assert client.get(f"{base}/{pid}/members", headers=teammate).status_code == 403

    added = client.post(
        f"{base}/{pid}/members", headers=owner,
        json={"user_id": teammate_id, "role": "viewer"},
    )
    assert added.status_code == 201

    # Viewer can read the project and its items but cannot write.
    assert client.get(f"{base}/{pid}", headers=teammate).status_code == 200
    assert client.get(f"{base}/{pid}/items", headers=teammate).status_code == 200
    assert client.get(f"{base}/{pid}/comments", headers=teammate).status_code == 200
    assert client.post(f"{base}/{pid}/items", headers=teammate,
                       json={"title": "Blocked"}).status_code == 403
    assert client.patch(f"{base}/{pid}", headers=teammate,
                        json={"name": "Blocked"}).status_code == 403
    assert pid in [row["id"] for row in client.get(base, headers=teammate).json()]

    promoted = client.patch(f"{base}/{pid}/members/{teammate_id}",
                            headers=owner, json={"role": "member"})
    assert promoted.status_code == 200
    item = client.post(f"{base}/{pid}/items", headers=teammate, json={"title": "Allowed"})
    assert item.status_code == 201, item.text
    assert client.patch(f"{base}/{pid}/items/{item.json()['id']}", headers=teammate,
                        json={"status": "done"}).status_code == 200
    assert client.delete(f"{base}/{pid}", headers=teammate).status_code == 403

    client.delete(f"{base}/{pid}/members/{teammate_id}", headers=owner)
    assert client.get(f"{base}/{pid}", headers=teammate).status_code == 403
    assert client.get(f"{base}/{pid}/items", headers=teammate).status_code == 403
    assert pid not in [row["id"] for row in client.get(base, headers=teammate).json()]


def test_member_management_requires_project_admin_and_valid_identity(client):
    tokens = bootstrap(client)
    wid, owner = tokens["workspace_id"], auth(tokens["access_token"])
    project = _project(client, wid, owner)
    pid = project["id"]
    teammate, teammate_id = _workspace_member(client, wid, owner, "pladmin@example.com")
    base = f"/api/v1/workspaces/{wid}/projects/{pid}/members"

    assert client.post(base, headers=owner,
                       json={"user_id": teammate_id, "role": "member"}).status_code == 201
    assert client.post(base, headers=owner,
                       json={"user_id": teammate_id, "role": "member"}).status_code == 409
    assert client.post(base, headers=teammate,
                       json={"user_id": teammate_id, "role": "member"}).status_code == 403
    assert client.post(base, headers=owner,
                       json={"user_id": teammate_id, "role": "chief"}).status_code == 422
    assert client.post(base, headers=owner,
                       json={"user_id": "not-a-workspace-member"}).status_code == 422
    assert client.patch(f"{base}/{teammate_id}", headers=owner, json={}).status_code == 422
    assert client.delete(
        f"{base}/{client.get('/api/v1/auth/me', headers=owner).json()['user']['id']}",
        headers=owner,
    ).status_code == 409


def test_public_projects_keep_workspace_role_fallback(client):
    tokens = bootstrap(client)
    wid, owner = tokens["workspace_id"], auth(tokens["access_token"])
    project = _project(client, wid, owner, name="Open", restricted=False)
    teammate, _ = _workspace_member(client, wid, owner, "plpublic@example.com")
    base = f"/api/v1/workspaces/{wid}/projects"
    assert client.get(f"{base}/{project['id']}", headers=teammate).status_code == 200
    item = client.post(f"{base}/{project['id']}/items", headers=teammate,
                       json={"title": "No project role needed"})
    assert item.status_code == 201, item.text
