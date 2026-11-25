"""Named acceptance tests for the clean-room conversation operations cluster.

Every test drives the real FastAPI app with real persisted workspace-scoped
rows (including real invited second members). No Chatwoot source, ActionCable
transport, outbound notification or external holiday service is used.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}"


def _ctx(client):
    tokens = bootstrap(client, "ConvOps", "convops-owner@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def _ops(wid):
    return API.format(wid=wid) + "/conversation-ops"


def _tickets(wid):
    return API.format(wid=wid) + "/tickets"


def _member(client, wid, owner_headers, email, role="support"):
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


def _ticket(client, wid, h, subject="Help"):
    response = client.post(_tickets(wid), headers=h, json={"subject": subject, "body": "Details"})
    assert response.status_code == 201, response.text
    return response.json()


def _hours(client, wid, h, inbox="web", tz="UTC", slots=None, away="Away right now"):
    response = client.post(_ops(wid) + "/inbox-hours", headers=h, json={
        "inbox_key": inbox, "timezone": tz, "away_message": away,
        "slots": slots if slots is not None else [
            {"day_of_week": d, "start_minute": 540, "end_minute": 1020} for d in range(5)
        ],
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_cw006_agent_presence_states_drive_visibility(client):
    """Presence is per active member, updatable and rejected for invalid states."""
    wid, h = _ctx(client)
    member_h, member_id = _member(client, wid, h, "presence-agent@example.com")
    owner = client.get("/api/v1/auth/me", headers=h).json()["user"]["id"]
    assert client.put(_ops(wid) + "/presence", headers=h,
                      json={"state": "online"}).json()["state"] == "online"
    assert client.put(_ops(wid) + "/presence", headers=member_h,
                      json={"state": "away"}).json()["state"] == "away"
    rows = client.get(_ops(wid) + "/presence", headers=h).json()
    assert {r["user_id"]: r["state"] for r in rows}[owner] == "online"
    assert len(rows) == 2
    assert client.put(_ops(wid) + "/presence", headers=h,
                      json={"state": "busy"}).status_code == 422


def test_cw010_snoozed_conversations_leave_and_reenter_the_queue(client):
    """Snoozes remove a conversation temporarily and can be unsnoozed or expired."""
    wid, h = _ctx(client)
    ticket = _ticket(client, wid, h)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    assert client.post(_ops(wid) + f"/tickets/{ticket['id']}/snooze", headers=h,
                       json={"until": past}).status_code == 422
    result = client.post(_ops(wid) + f"/tickets/{ticket['id']}/snooze", headers=h,
                         json={"until": future, "reason": "wait for customer"})
    assert result.status_code == 201, result.text
    assert any(s["ticket_id"] == ticket["id"] for s in client.get(_ops(wid) + "/snoozes", headers=h).json())
    assert client.post(_ops(wid) + f"/tickets/{ticket['id']}/snooze", headers=h,
                       json={"until": future}).status_code == 201  # idempotent resnooze
    assert client.post(_ops(wid) + "/snoozes/expire-due", headers=h).json()["expired"] == 0
    assert client.post(_ops(wid) + f"/tickets/{ticket['id']}/unsnooze", headers=h).json()["active"] is False
    assert client.get(_ops(wid) + "/snoozes", headers=h).json() == []
    assert client.post(_ops(wid) + f"/tickets/{ticket['id']}/unsnooze", headers=h).status_code == 404


def test_cw010_due_snoozes_return_to_the_active_queue(db_session, client):
    """A due snooze is deactivated by the expiry sweep, returning the conversation."""
    from novara_core.models import new_id, now
    from novara_core.modules.conversation_ops import ConversationSnooze

    wid, h = _ctx(client)
    ticket = _ticket(client, wid, h)
    db_session.add(ConversationSnooze(
        id=new_id(), workspace_id=wid, ticket_id=ticket["id"],
        snoozed_until=now() - timedelta(minutes=1), reason="expired", active=True,
        created_at=now() - timedelta(hours=1),
    ))
    db_session.commit()
    result = client.post(_ops(wid) + "/snoozes/expire-due", headers=h)
    assert result.status_code == 200, result.text
    assert result.json()["returned_to_queue"] == [ticket["id"]]
    assert client.get(_ops(wid) + "/snoozes", headers=h).json() == []


def test_cw020_mentions_notify_active_teammates_in_private_notes(client):
    """@mentions create local notifications only for active workspace teammates."""
    wid, h = _ctx(client)
    member_h, member_id = _member(client, wid, h, "mention-agent@example.com")
    ticket = _ticket(client, wid, h)
    result = client.post(_ops(wid) + f"/tickets/{ticket['id']}/mention-note", headers=h, json={
        "body": "@mention-agent please take a look",
        "mentions": [member_id, member_id],
    })
    assert result.status_code == 201, result.text
    assert result.json()["mentioned"] == [member_id]  # deduplicated
    assert result.json()["notification_delivery"] == "local-event-only"
    assert len(client.get(_ops(wid) + "/mentions", headers=member_h).json()) == 1
    assert client.get(_ops(wid) + "/mentions", headers=h).json() == []
    assert client.post(_ops(wid) + f"/tickets/{ticket['id']}/mention-note", headers=h,
                       json={"body": "hi", "mentions": ["not-a-member"]}).status_code == 422


def test_cw021_collision_detection_and_duplicate_reply_prevention(client):
    """A typing teammate raises a warning and duplicate replies are refused."""
    wid, h = _ctx(client)
    member_h, _ = _member(client, wid, h, "typing-agent@example.com")
    ticket = _ticket(client, wid, h)
    typing = client.post(_ops(wid) + f"/tickets/{ticket['id']}/typing", headers=member_h,
                         json={"ttl_seconds": 30})
    assert typing.status_code == 200, typing.text
    collision = client.get(_ops(wid) + f"/tickets/{ticket['id']}/collision", headers=h).json()
    assert collision["warning"] is True and len(collision["others_typing"]) == 1
    assert client.post(_ops(wid) + f"/tickets/{ticket['id']}/reply", headers=h,
                       json={"body": "duplicate risk", "client_msg_id": "m1"}).status_code == 409
    forced = client.post(_ops(wid) + f"/tickets/{ticket['id']}/reply", headers=h,
                         json={"body": "reviewed reply", "client_msg_id": "m1", "force": True})
    assert forced.status_code == 201, forced.text
    assert forced.json()["overrode_typing_warning"] is True
    assert client.post(_ops(wid) + f"/tickets/{ticket['id']}/reply", headers=h,
                       json={"body": "again", "client_msg_id": "m1"}).status_code == 409
    assert client.post(_ops(wid) + f"/tickets/{ticket['id']}/typing", headers=member_h,
                       json={"ttl_seconds": 121}).status_code == 422


def test_cw022_delivery_and_read_receipts_are_per_message_and_user(client):
    """Each message records delivered and read confirmations independently."""
    wid, h = _ctx(client)
    member_h, _ = _member(client, wid, h, "receipt-agent@example.com")
    ticket = _ticket(client, wid, h)
    reply = client.post(_ops(wid) + f"/tickets/{ticket['id']}/reply", headers=h,
                        json={"body": "hello"}).json()
    mid = reply["message_id"]
    first = client.post(_ops(wid) + f"/messages/{mid}/receipt", headers=h, json={"read": False})
    assert first.status_code == 200, first.text
    assert first.json()["delivered"] is True and first.json()["read_at"] is None
    second = client.post(_ops(wid) + f"/messages/{mid}/receipt", headers=member_h, json={"read": True})
    assert second.json()["read_at"] is not None
    rows = client.get(_ops(wid) + f"/messages/{mid}/receipts", headers=h).json()
    assert len(rows) == 2 and sum(1 for r in rows if r["read_at"]) == 1
    assert client.post(_ops(wid) + "/messages/not-a-message/receipt", headers=h,
                       json={"read": True}).status_code == 404


def test_cw025_bulk_actions_apply_status_assignee_and_labels(client):
    """Bulk actions update many conversations atomically with validated targets."""
    wid, h = _ctx(client)
    member_h, member_id = _member(client, wid, h, "bulk-agent@example.com")
    label = client.post(_tickets(wid) + "/labels", headers=h, json={"name": "vip"})
    assert label.status_code == 201, label.text
    tickets = [_ticket(client, wid, h, f"Bulk {i}") for i in range(3)]
    ids = [t["id"] for t in tickets]
    result = client.post(_ops(wid) + "/tickets/bulk", headers=h, json={
        "ticket_ids": ids, "status": "pending", "assignee_id": member_id, "label": "vip",
    })
    assert result.status_code == 200, result.text
    assert result.json()["updated"] == 3
    for tid in ids:
        ticket = client.get(_tickets(wid) + f"/{tid}", headers=h).json()["ticket"]
        assert ticket["status"] == "pending" and ticket["assignee_id"] == member_id
    assert client.post(_ops(wid) + "/tickets/bulk", headers=h,
                       json={"ticket_ids": ids[:1]}).status_code == 422
    assert client.post(_ops(wid) + "/tickets/bulk", headers=h, json={
        "ticket_ids": ids, "label": "missing-label",
    }).status_code == 422
    assert client.post(_ops(wid) + "/tickets/bulk", headers=h, json={
        "ticket_ids": ["missing"], "status": "open",
    }).status_code == 404


def test_cw029_saved_filter_folders_show_live_counts(client):
    """Saved filter folders compute counts from current ticket state."""
    wid, h = _ctx(client)
    _ticket(client, wid, h, "One")
    _ticket(client, wid, h, "Two")
    created = client.post(_ops(wid) + "/folders", headers=h,
                          json={"name": "Open inbox", "filters": {"status": "open"}})
    assert created.status_code == 201, created.text
    assert created.json()["count"] == 2
    folder_id = created.json()["id"]
    client.post(_ops(wid) + "/tickets/bulk", headers=h,
                json={"ticket_ids": [t["id"] for t in client.get(_tickets(wid), headers=h).json()],
                      "status": "resolved"})
    folders = client.get(_ops(wid) + "/folders", headers=h).json()
    assert folders[0]["count"] == 0  # live count, not a stored snapshot
    assert client.post(_ops(wid) + "/folders", headers=h,
                       json={"name": "Open inbox", "filters": {}}).status_code == 409
    assert client.post(_ops(wid) + "/folders", headers=h,
                       json={"name": "bad", "filters": {"unknown": 1}}).status_code == 422
    assert client.delete(_ops(wid) + f"/folders/{folder_id}", headers=h).json()["removed"] is True


def test_cw032_mute_suppresses_notifications_for_one_conversation(client):
    """Mutes are per user and per conversation and are listable."""
    wid, h = _ctx(client)
    member_h, _ = _member(client, wid, h, "mute-agent@example.com")
    one = _ticket(client, wid, h, "Mute me")
    two = _ticket(client, wid, h, "Keep me")
    assert client.post(_ops(wid) + f"/tickets/{one['id']}/mute", headers=h,
                       json={"muted": True}).json()["notifications"] == "suppressed-locally"
    assert [m["ticket_id"] for m in client.get(_ops(wid) + "/mutes", headers=h).json()] == [one["id"]]
    assert client.get(_ops(wid) + "/mutes", headers=member_h).json() == []
    client.post(_ops(wid) + f"/tickets/{one['id']}/mute", headers=h, json={"muted": False})
    assert client.get(_ops(wid) + "/mutes", headers=h).json() == []
    assert client.post(_ops(wid) + "/tickets/missing/mute", headers=h,
                       json={"muted": True}).status_code == 404


def test_cw052_business_hours_are_timezone_aware_and_per_inbox(client):
    """Weekly schedules evaluate in the configured timezone for each inbox."""
    wid, h = _ctx(client)
    row = _hours(client, wid, h, inbox="web", tz="Asia/Kolkata")
    assert client.get(_ops(wid) + "/inbox-hours", headers=h).json()[0]["timezone"] == "Asia/Kolkata"
    open_result = client.get(_ops(wid) + f"/inbox-hours/{row['id']}/availability",
                             headers=h, params={"at": "2026-11-23T06:00:00+00:00"}).json()
    assert open_result["open"] is True and open_result["reason"] == "scheduled"
    assert "11:30" in open_result["local_time"]
    closed = client.get(_ops(wid) + f"/inbox-hours/{row['id']}/availability",
                        headers=h, params={"at": "2026-11-23T20:00:00+05:30"}).json()
    assert closed["open"] is False and closed["away_message"] == "Away right now"
    assert client.post(_ops(wid) + "/inbox-hours", headers=h,
                       json={"inbox_key": "web", "timezone": "UTC"}).status_code == 409
    assert client.post(_ops(wid) + "/inbox-hours", headers=h,
                       json={"inbox_key": "bad", "timezone": "Mars/Olympus"}).status_code == 422


def test_cw053_date_overrides_reduce_or_close_hours(client):
    """Per-date overrides supersede the weekly schedule."""
    wid, h = _ctx(client)
    row = _hours(client, wid, h)
    closed = client.post(_ops(wid) + f"/inbox-hours/{row['id']}/overrides", headers=h,
                         json={"date": "2026-11-24", "closed": True})
    assert closed.status_code == 201, closed.text
    reduced = client.post(_ops(wid) + f"/inbox-hours/{row['id']}/overrides", headers=h,
                          json={"date": "2026-11-25", "closed": False,
                                "start_minute": 600, "end_minute": 720})
    assert reduced.status_code == 201, reduced.text
    assert client.get(_ops(wid) + f"/inbox-hours/{row['id']}/availability", headers=h,
                      params={"at": "2026-11-24T10:00:00+00:00"}).json()["reason"] == "date-override-closed"
    assert client.get(_ops(wid) + f"/inbox-hours/{row['id']}/availability", headers=h,
                      params={"at": "2026-11-25T10:30:00+00:00"}).json()["reason"] == "date-override"
    assert client.get(_ops(wid) + f"/inbox-hours/{row['id']}/availability", headers=h,
                      params={"at": "2026-11-25T13:00:00+00:00"}).json()["open"] is False
    assert client.post(_ops(wid) + f"/inbox-hours/{row['id']}/overrides", headers=h,
                       json={"date": "2026-11-24", "closed": True}).status_code == 409
    assert client.post(_ops(wid) + f"/inbox-hours/{row['id']}/overrides", headers=h,
                       json={"date": "2026-11-26", "closed": False}).status_code == 422


def test_cw054_regional_holidays_close_dates_in_one_click(client):
    """Holiday and region-closure lists override availability without external lookup."""
    wid, h = _ctx(client)
    row = _hours(client, wid, h)
    holiday = client.post(_ops(wid) + f"/inbox-hours/{row['id']}/holidays", headers=h,
                          json={"date": "2026-11-26", "name": "Founders Day", "region": "IN"})
    assert holiday.status_code == 201, holiday.text
    result = client.post(_ops(wid) + f"/inbox-hours/{row['id']}/holidays/close-region", headers=h,
                         json={"region": "IN", "dates": ["2026-11-27", "2026-11-28", "2026-11-27"]})
    assert result.status_code == 200, result.text
    assert result.json()["closed_dates"] == 2
    assert result.json()["source"] == "operator-supplied-list"
    availability = client.get(_ops(wid) + f"/inbox-hours/{row['id']}/availability", headers=h,
                              params={"at": "2026-11-27T10:00:00+00:00"}).json()
    assert availability["open"] is False and "closure" in availability["reason"]
    assert client.post(_ops(wid) + f"/inbox-hours/{row['id']}/holidays", headers=h,
                       json={"date": "2026-13-01", "name": "bad"}).status_code == 422


def test_cw055_split_shifts_allow_multiple_windows_per_day(client):
    """Two windows per weekday support split shifts with a lunch gap."""
    wid, h = _ctx(client)
    slots = [{"day_of_week": 0, "start_minute": 540, "end_minute": 720},
             {"day_of_week": 0, "start_minute": 840, "end_minute": 1020}]
    row = _hours(client, wid, h, slots=slots)
    assert len(client.get(_ops(wid) + "/inbox-hours", headers=h).json()[0]["slots"]) == 2
    morning = client.get(_ops(wid) + f"/inbox-hours/{row['id']}/availability", headers=h,
                         params={"at": "2026-11-23T09:30:00+00:00"}).json()
    lunch = client.get(_ops(wid) + f"/inbox-hours/{row['id']}/availability", headers=h,
                       params={"at": "2026-11-23T12:30:00+00:00"}).json()
    evening = client.get(_ops(wid) + f"/inbox-hours/{row['id']}/availability", headers=h,
                         params={"at": "2026-11-23T14:30:00+00:00"}).json()
    assert morning["open"] is True and lunch["open"] is False and evening["open"] is True
    assert client.post(_ops(wid) + "/inbox-hours", headers=h, json={
        "inbox_key": "bad-slots", "slots": [{"day_of_week": 0, "start_minute": 600, "end_minute": 600}],
    }).status_code == 422


def test_cw056_away_message_is_shown_outside_business_hours(client):
    """Outside-hours visitors see the configured message, with a safe default."""
    wid, h = _ctx(client)
    row = _hours(client, wid, h, away="Back Monday at 9am")
    outside = client.get(_ops(wid) + f"/inbox-hours/{row['id']}/availability", headers=h,
                         params={"at": "2026-11-23T19:00:00+00:00"}).json()
    assert outside["open"] is False and outside["away_message"] == "Back Monday at 9am"
    fallback = _hours(client, wid, h, inbox="fallback", away="")
    result = client.get(_ops(wid) + f"/inbox-hours/{fallback['id']}/availability", headers=h,
                        params={"at": "2026-11-23T19:00:00+00:00"}).json()
    assert "unavailable" in result["away_message"].lower()
    assert result["external_calls"] is False


def test_conversation_ops_workspace_isolation(client):
    """A second workspace cannot address this workspace's conversations or hours."""
    wid, h = _ctx(client)
    ticket = _ticket(client, wid, h)
    folder = client.post(_ops(wid) + "/folders", headers=h,
                         json={"name": "Private", "filters": {}}).json()
    hours = _hours(client, wid, h)
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other convops"})
    assert other.status_code == 200, other.text
    other_wid, other_h = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_ops(other_wid) + "/presence", headers=other_h).json() == []
    assert client.get(_ops(other_wid) + "/folders", headers=other_h).json() == []
    assert client.post(_ops(other_wid) + f"/tickets/{ticket['id']}/mute", headers=other_h,
                       json={"muted": True}).status_code == 404
    assert client.delete(_ops(other_wid) + f"/folders/{folder['id']}", headers=other_h).status_code == 404
    assert client.get(_ops(other_wid) + f"/inbox-hours/{hours['id']}/availability",
                      headers=other_h).status_code == 404
