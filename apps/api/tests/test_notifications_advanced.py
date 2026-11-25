"""P0 notification-centre deep completion (NV-023, NV-030, NV-035, NV-068).

Every assertion here is over persisted workspace rows and the public HTTP API.
No external message is sent and no response body containing a token is logged.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import inspect, select

from novara_core.models import (
    Event,
    Notification,
    User,
    Workspace,
    WorkspaceMember,
    new_id,
    now,
)
from novara_core.security import hash_password

from .conftest import auth, bootstrap

NOTIFS = "/api/v1/workspaces/{wid}/notifications"
SETTINGS = "/api/v1/workspaces/{wid}/notification-settings"


def _make_notification(db, workspace_id, user_id, *, message="Hello", category="general", title=None, link=None, read=False, seen=False):
    row = Notification(
        id=new_id(),
        workspace_id=workspace_id,
        user_id=user_id,
        title=title,
        message=message,
        category=category,
        link=link,
        read=read,
        seen=seen,
        created_at=now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _second_member(db, workspace_id, email="teammate@example.com"):
    user = User(
        id=new_id(),
        email=email,
        display_name="Teammate",
        password_hash=hash_password("Password123!"),
    )
    db.add(user)
    db.add(WorkspaceMember(
        id=new_id(), workspace_id=workspace_id, user_id=user.id,
        role="owner", status="active",
    ))
    db.commit()
    db.refresh(user)
    return user


def test_notification_persists_rich_content_per_workspace_and_user(client, db_session):
    """NV-023: title, category, deep link and timestamps survive a round trip."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()

    row = _make_notification(
        db_session, wid, owner.id,
        message="A lead was qualified", category="sales",
        title="New qualified lead", link="#/leads/abc123",
    )

    listed = client.get(NOTIFS.format(wid=wid), headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert len(body) == 1
    item = body[0]
    assert item["id"] == row.id
    assert item["title"] == "New qualified lead"
    assert item["message"] == "A lead was qualified"
    assert item["category"] == "sales"
    assert item["link"] == "#/leads/abc123"
    assert item["read"] is False and item["seen"] is False
    assert item["read_at"] is None and item["seen_at"] is None
    assert db_session.get(Notification, row.id).workspace_id == wid


def test_seen_and_read_are_independent_states(client, db_session):
    """NV-035: seeing a feed is not the same act as reading a message."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    row = _make_notification(db_session, wid, owner.id)

    seen = client.post(NOTIFS.format(wid=wid) + "/" + row.id + "/seen", headers=headers)
    assert seen.status_code == 200, seen.text
    assert seen.json()["seen"] is True and seen.json()["read"] is False
    assert seen.json()["seen_at"] is not None

    read = client.post(NOTIFS.format(wid=wid) + "/" + row.id + "/read", headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["read"] is True and read.json()["seen"] is True
    assert read.json()["read_at"] is not None

    stored = db_session.get(Notification, row.id)
    assert stored.seen and stored.read

    # Repeat calls are idempotent: no duplicate audit events.
    again = client.post(NOTIFS.format(wid=wid) + "/" + row.id + "/read", headers=headers)
    assert again.status_code == 200
    read_events = db_session.execute(
        select(Event).where(Event.workspace_id == wid, Event.event_type == "notification.read")
    ).scalars().all()
    assert len(read_events) == 1


def test_single_mark_read_is_user_and_workspace_scoped(client, db_session):
    """NV-030/035: another identity's message and another workspace are unreachable."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    other = _second_member(db_session, wid)
    foreign_workspace = Workspace(id=new_id(), name="Other", created_at=now())
    db_session.add(foreign_workspace)
    db_session.commit()
    db_session.add(WorkspaceMember(
        id=new_id(), workspace_id=foreign_workspace.id, user_id=other.id,
        role="owner", status="active",
    ))

    own = _make_notification(db_session, wid, None, message="broadcast")
    not_mine = _make_notification(db_session, wid, other.id, message="private")
    foreign = _make_notification(db_session, foreign_workspace.id, None, message="other workspace")

    assert client.post(NOTIFS.format(wid=wid) + "/" + not_mine.id + "/read", headers=headers).status_code == 404
    assert client.post(NOTIFS.format(wid=wid) + "/" + foreign.id + "/read", headers=headers).status_code == 404

    assert client.post(NOTIFS.format(wid=wid) + "/" + own.id + "/read", headers=headers).status_code == 200
    assert db_session.get(Notification, not_mine.id).read is False
    assert db_session.get(Notification, foreign.id).read is False


def test_bulk_read_all_only_touches_callers_rows(client, db_session):
    """NV-035: mark-all-read never crosses an identity or workspace boundary."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    other = _second_member(db_session, wid)

    mine = [_make_notification(db_session, wid, owner.id, message=f"mine {i}") for i in range(2)]
    broadcast = _make_notification(db_session, wid, None, message="broadcast")
    theirs = _make_notification(db_session, wid, other.id, message="theirs")

    response = client.post(NOTIFS.format(wid=wid) + "/read-all", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["unread"] == 0
    assert response.json()["total"] == 3

    for row in mine + [broadcast]:
        assert db_session.get(Notification, row.id).read is True
    assert db_session.get(Notification, theirs.id).read is False

    bulk_events = db_session.execute(
        select(Event).where(Event.workspace_id == wid, Event.event_type == "notification.read_all")
    ).scalars().all()
    assert len(bulk_events) == 1
    assert bulk_events[0].payload["count"] == 3


def test_bulk_seen_all_and_counts_by_category(client, db_session):
    """NV-023/035: category aggregates come from stored rows, not static data."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()

    _make_notification(db_session, wid, owner.id, category="sales", message="a")
    _make_notification(db_session, wid, owner.id, category="sales", message="b")
    _make_notification(db_session, wid, owner.id, category="support", message="c")

    counts = client.get(NOTIFS.format(wid=wid) + "/counts", headers=headers)
    assert counts.status_code == 200, counts.text
    assert counts.json() == {
        "total": 3, "unread": 3, "unseen": 3,
        "by_category": {"sales": 2, "support": 1},
    }

    seen = client.post(NOTIFS.format(wid=wid) + "/seen-all", headers=headers)
    assert seen.status_code == 200, seen.text
    assert seen.json()["unseen"] == 0
    assert seen.json()["unread"] == 3  # seeing is not reading
    assert all(db_session.get(Notification, r.id).seen for r in
               db_session.execute(select(Notification)).scalars().all())


def test_feed_filters_and_pagination(client, db_session):
    """NV-023: the feed supports category, unread/seen and bounded paging."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()

    base = NOTIFS.format(wid=wid)
    a = _make_notification(db_session, wid, owner.id, category="sales", message="a")
    b = _make_notification(db_session, wid, owner.id, category="sales", message="b")
    b.created_at = now() + timedelta(seconds=1)
    db_session.commit()
    c = _make_notification(db_session, wid, owner.id, category="billing", message="c", read=True, seen=True)

    assert len(client.get(base + "?category=sales", headers=headers).json()) == 2
    assert [r["id"] for r in client.get(base + "?unread_only=true", headers=headers).json()] == [b.id, a.id]
    assert len(client.get(base + "?unseen_only=true", headers=headers).json()) == 2
    assert len(client.get(base + "?limit=1", headers=headers).json()) == 1
    assert len(client.get(base + "?skip=2", headers=headers).json()) == 1
    assert {r["id"] for r in client.get(base + "?category=billing", headers=headers).json()} == {c.id}


def test_one_identity_is_one_recipient_with_no_second_login(client, db_session):
    """NV-030: recipients resolve through the shared user/member identity."""
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    teammate = _second_member(db_session, wid)
    _make_notification(db_session, wid, teammate.id, message="for teammate")
    _make_notification(db_session, wid, None, message="workspace wide")
    _make_notification(db_session, wid, "someone-else", message="owner only")

    login = client.post("/api/v1/auth/login", json={
        "email": teammate.email, "password": "Password123!", "workspace_id": wid,
    })
    assert login.status_code == 200, login.text
    teammate_headers = auth(login.json()["access_token"])
    me = client.get("/api/v1/auth/me", headers=teammate_headers)
    assert me.status_code == 200
    assert me.json()["user"]["id"] == teammate.id

    visible = client.get(NOTIFS.format(wid=wid), headers=teammate_headers).json()
    assert {r["message"] for r in visible} == {"for teammate", "workspace wide"}

    # No parallel subscriber identity exists: the user/member tables are the only
    # recipient source, and the feed resolved this user through them.
    tables = set(inspect(db_session.get_bind()).get_table_names())
    assert "subscribers" not in tables
    assert {"users", "workspace_members", "notifications"} <= tables


def test_notification_settings_persist_and_deny_cross_workspace_access(client, db_session):
    """NV-068: settings are workspace-scoped and validated."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    other_workspace = Workspace(id=new_id(), name="Other", created_at=now())
    db_session.add(other_workspace)
    db_session.commit()

    default = client.get(SETTINGS.format(wid=wid), headers=headers)
    assert default.status_code == 200, default.text
    assert default.json()["timezone"] == "UTC"
    assert default.json()["in_app_enabled"] is True

    updated = client.put(SETTINGS.format(wid=wid), headers=headers, json={
        "digest_enabled": True,
        "quiet_hours_enabled": True,
        "delivery_window_start": "09:30",
        "delivery_window_end": "18:00",
        "timezone": "Asia/Kolkata",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["digest_enabled"] is True
    assert updated.json()["delivery_window_start"] == "09:30"

    reread = client.get(SETTINGS.format(wid=wid), headers=headers).json()
    assert reread["timezone"] == "Asia/Kolkata"
    assert reread["quiet_hours_enabled"] is True

    # Clearing a window with explicit null is supported.
    cleared = client.put(SETTINGS.format(wid=wid), headers=headers, json={"delivery_window_end": None})
    assert cleared.status_code == 200
    assert cleared.json()["delivery_window_end"] is None
    assert cleared.json()["digest_enabled"] is True

    assert client.get(SETTINGS.format(wid=other_workspace.id), headers=headers).status_code == 403
    assert client.put(SETTINGS.format(wid=other_workspace.id), headers=headers, json={"digest_enabled": False}).status_code == 403

    settings_events = db_session.execute(
        select(Event).where(
            Event.workspace_id == wid, Event.event_type == "notification.settings_updated"
        )
    ).scalars().all()
    assert len(settings_events) == 2


def test_notification_settings_reject_invalid_windows(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = SETTINGS.format(wid=wid)

    assert client.put(base, headers=headers, json={"delivery_window_start": "25:00"}).status_code == 422
    assert client.put(base, headers=headers, json={"timezone": "bad zone"}).status_code == 422
    assert client.put(base, headers=headers, json={"unexpected": 1}).status_code == 422
