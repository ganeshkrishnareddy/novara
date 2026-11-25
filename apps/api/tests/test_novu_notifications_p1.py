"""Named acceptance tests for Novu P1 feature-matrix rows.

Every test drives the real NOVARA FastAPI app with bootstrap/auth fixtures and
asserts over persisted workspace rows or real HTTP responses. Local adapters,
jobs and notifications never send externally and no mock is presented as a
delivered message. Time-dependent workflow state is advanced by updating the
stored fire_at/locked_at rows, not by faking a provider or a clock in the app.
"""

from __future__ import annotations

import json
from datetime import timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

from novara_core.models import (
    Event,
    Notification,
    User,
    WorkspaceMember,
    new_id,
    now,
)
from novara_core.security import hash_password
from novara_core.modules.adapters import AdapterCall, MessageRecord
from novara_core.modules.automation import (
    AutomationPayloadSchema,
    AutomationRun,
    DigestBucket,
    ScheduledRun,
    ThrottleCounter,
    Topic,
    TopicSubscription,
    WorkflowDelayState,
    WorkflowMessageLink,
    WorkflowRunStep,
)
from novara_core.modules.jobs import Job, MessageFailure

from .conftest import auth, bootstrap

AUTOMATIONS = "/api/v1/workspaces/{wid}/automations"
NOTIFICATIONS = "/api/v1/workspaces/{wid}/notifications"
OPERATIONS = "/api/v1/workspaces/{wid}/operations"
JOBS = "/api/v1/workspaces/{wid}/jobs"
ADAPTERS = "/api/v1/workspaces/{wid}/adapters"
INTEGRATIONS = "/api/v1/workspaces/{wid}/integrations"
PREFERENCES = "/api/v1/workspaces/{wid}/notification-preferences"
WEB_ROOT = Path(__file__).resolve().parents[3] / "apps" / "web"


def _auto_url(wid: str, automation_id: str | None = None) -> str:
    base = AUTOMATIONS.format(wid=wid)
    return base if automation_id is None else f"{base}/{automation_id}"


def _create_automation(client, wid, headers, definition, *, name="Flow") -> str:
    response = client.post(
        _auto_url(wid),
        headers=headers,
        json={
            "name": name,
            "trigger_type": "manual",
            "definition": definition,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _member(db, wid: str, email: str) -> User:
    user = User(
        id=new_id(),
        email=email,
        display_name=email.split("@")[0],
        password_hash=hash_password("Password123!"),
        is_active=True,
    )
    db.add(user)
    db.add(
        WorkspaceMember(
            id=new_id(), workspace_id=wid, user_id=user.id,
            role="owner", status="active",
        )
    )
    db.commit()
    db.refresh(user)
    return user


def _notification(db, wid: str, user_id: str | None, message: str, **fields) -> Notification:
    row = Notification(
        id=new_id(), workspace_id=wid, user_id=user_id, message=message,
        read=fields.get("read", False), seen=fields.get("seen", False),
        category=fields.get("category", "general"), title=fields.get("title"),
        created_at=now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _second_workspace(client, headers):
    response = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Other workspace"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["workspace_id"], auth(data["access_token"])


def _count(db, model, *conditions) -> int:
    return int(db.execute(select(func.count()).select_from(model).where(*conditions)).scalar() or 0)


# ---------------------------------------------------------------------------
# NV-003 / NV-004: bulk and topic triggers
# ---------------------------------------------------------------------------


def test_nv003_bulk_trigger_creates_one_audited_run_per_recipient_and_is_idempotent(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    members = [_member(db_session, wid, f"bulk{i}@example.test") for i in range(2)]
    automation_id = _create_automation(
        client, wid, headers, [{"id": "act", "type": "action"}], name="Bulk flow"
    )

    body = {
        "recipients": [owner.id] + [member.id for member in members],
        "payload": {"plan": "pro"},
        "message": "bulk hello",
        "idempotency_key": "bulk-key-1",
    }
    response = client.post(_auto_url(wid, automation_id) + "/bulk_trigger", headers=headers, json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 3 and data["replayed"] is False
    assert {run["user_id"] for run in data["runs"]} == set(body["recipients"])

    runs = db_session.execute(
        select(AutomationRun).where(AutomationRun.workspace_id == wid)
    ).scalars().all()
    assert len(runs) == 3
    events = db_session.execute(
        select(Event).where(
            Event.workspace_id == wid, Event.event_type == "workflow.trigger_received"
        )
    ).scalars().all()
    assert len(events) == 3
    assert len({event.correlation_id for event in events}) == 1

    replay = client.post(_auto_url(wid, automation_id) + "/bulk_trigger", headers=headers, json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True and replay.json()["count"] == 3
    assert _count(db_session, AutomationRun, AutomationRun.workspace_id == wid) == 3

    over_limit = dict(body, idempotency_key="bulk-too-many", recipients=[f"u-{i}" for i in range(51)])
    assert client.post(
        _auto_url(wid, automation_id) + "/bulk_trigger", headers=headers, json=over_limit
    ).status_code == 422
    foreign = User(id=new_id(), email="foreign@example.test", display_name="F",
                   password_hash=hash_password("Password123!"))
    db_session.add(foreign)
    db_session.commit()
    assert client.post(
        _auto_url(wid, automation_id) + "/bulk_trigger", headers=headers,
        json=dict(body, idempotency_key="bulk-foreign", recipients=[foreign.id]),
    ).status_code == 422
    audit = client.get(
        OPERATIONS.format(wid=wid) + "/audit",
        params={"event_type": "workflow.trigger_received"}, headers=headers,
    )
    assert audit.status_code == 200 and len(audit.json()) == 3


def test_nv004_topic_trigger_fans_out_only_to_matching_subscriptions_with_actor_exclusion(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    m1, m2, m3 = [_member(db_session, wid, f"topic{i}@example.test") for i in range(3)]
    automation_id = _create_automation(
        client, wid, headers, [{"id": "act", "type": "action"}], name="Topic flow"
    )
    topic = client.post(
        _auto_url(wid) + "/topics/create", headers=headers,
        json={"key": "alerts", "name": "Alerts"},
    )
    assert topic.status_code == 201, topic.text
    topic_id = topic.json()["id"]

    condition = {"field": "payload.plan", "op": "eq", "value": "pro"}
    subscriptions = [
        (owner.id, {"tenant": "A"}, condition),
        (m1.id, {"tenant": "A"}, condition),
        (m2.id, {"tenant": "B"}, condition),
        (m3.id, {"tenant": "A"}, {"field": "payload.plan", "op": "eq", "value": "free"}),
    ]
    for user_id, context, conditions in subscriptions:
        created = client.post(
            _auto_url(wid) + f"/topics/{topic_id}/subscriptions/create",
            headers=headers,
            json={"user_id": user_id, "context": context, "conditions": conditions},
        )
        assert created.status_code == 201, created.text

    trigger = {
        "topic_key": "alerts", "payload": {"plan": "pro"},
        "context": {"tenant": "A"}, "message": "topic hello",
    }
    excluded = client.post(
        _auto_url(wid, automation_id) + "/topic_trigger", headers=headers,
        json=dict(trigger, idempotency_key="topic-exclude"),
    )
    assert excluded.status_code == 200, excluded.text
    assert excluded.json()["count"] == 1
    assert {run["user_id"] for run in excluded.json()["runs"]} == {m1.id}

    included = client.post(
        _auto_url(wid, automation_id) + "/topic_trigger", headers=headers,
        json=dict(trigger, idempotency_key="topic-include", exclude_actor=False),
    )
    assert included.status_code == 200, included.text
    assert {run["user_id"] for run in included.json()["runs"]} == {owner.id, m1.id}
    run_ids = [run["run_id"] for run in excluded.json()["runs"]]
    run_ids += [run["run_id"] for run in included.json()["runs"]]
    # Each run generated a real in-app message; its recipient is stored on that
    # notification and linked back to the run through WorkflowMessageLink.
    recipients = set(db_session.execute(
        select(Notification.user_id).join(
            WorkflowMessageLink, WorkflowMessageLink.notification_id == Notification.id
        ).where(
            Notification.workspace_id == wid,
            WorkflowMessageLink.run_id.in_(run_ids),
        )
    ).scalars().all())
    assert recipients == {owner.id, m1.id}
    assert m2.id not in recipients and m3.id not in recipients


# ---------------------------------------------------------------------------
# NV-008 / NV-010 / NV-011 / NV-048 / NV-106: workflow execution detail
# ---------------------------------------------------------------------------


def test_nv008_nested_conditions_include_exclude_real_steps_with_skip_reasons(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    definition = [
        {
            "id": "gate", "type": "noop",
            "conditions": {
                "all": [
                    {"field": "payload.tier", "op": "eq", "value": "gold"},
                    {"any": [
                        {"field": "subscriber.id", "op": "exists"},
                        {"field": "payload.vip", "op": "eq", "value": True},
                    ]},
                ]
            },
        },
        {"id": "prior", "type": "noop"},
        {
            "id": "after", "type": "action",
            "conditions": {"field": "steps.prior.result", "op": "eq", "value": "noop"},
        },
        {
            "id": "blocked", "type": "action",
            "conditions": {"not": {"field": "payload.tier", "op": "eq", "value": "gold"}},
        },
    ]
    automation_id = _create_automation(client, wid, headers, definition, name="Conditions flow")
    response = client.post(
        _auto_url(wid, automation_id) + "/bulk_trigger", headers=headers,
        json={
            "recipients": [db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one().id],
            "payload": {"tier": "gold"}, "idempotency_key": "conditions-1",
        },
    )
    assert response.status_code == 200, response.text
    run_id = response.json()["runs"][0]["run_id"]
    steps = db_session.execute(
        select(WorkflowRunStep).where(
            WorkflowRunStep.workspace_id == wid, WorkflowRunStep.run_id == run_id
        ).order_by(WorkflowRunStep.occurred_at)
    ).scalars().all()
    by_id = {step.step_id: step for step in steps}
    assert set(by_id) == {"gate", "prior", "after", "blocked"}
    assert by_id["gate"].outcome == "noop" and "all group matched" in by_id["gate"].reason
    assert by_id["prior"].outcome == "noop"
    assert by_id["after"].outcome == "noop" and "steps.prior.result" in by_id["after"].reason
    assert by_id["blocked"].outcome == "skipped" and "negation" in by_id["blocked"].reason
    timeline = client.get(
        _auto_url(wid, automation_id) + f"/runs/{run_id}/timeline", headers=headers
    )
    assert timeline.status_code == 200, timeline.text
    assert [entry["step_id"] for entry in timeline.json()["steps"]] == [
        "gate", "prior", "after", "blocked"
    ]


def test_nv010_delayed_run_stays_observable_and_resumes_the_same_run(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    automation_id = _create_automation(
        client, wid, headers,
        [
            {"id": "before", "type": "noop"},
            {"id": "wait", "type": "delay", "seconds": 60},
            {"id": "after", "type": "notify", "channel": "in_app"},
        ],
        name="Delay flow",
    )
    response = client.post(
        _auto_url(wid, automation_id) + "/bulk_trigger", headers=headers,
        json={"recipients": [owner.id], "payload": {}, "idempotency_key": "delay-fixed"},
    )
    assert response.status_code == 200, response.text
    run_id = response.json()["runs"][0]["run_id"]
    run = db_session.get(AutomationRun, run_id)
    assert run.status == "delayed"
    delay = db_session.execute(
        select(WorkflowDelayState).where(WorkflowDelayState.run_id == run_id)
    ).scalar_one()
    assert delay.status == "waiting" and delay.fire_at.replace(tzinfo=timezone.utc) > now()

    early = client.post(_auto_url(wid, automation_id) + f"/runs/{run_id}/resume", headers=headers)
    assert early.status_code == 409
    # Advance the stored timer to simulate the configured instant arriving.
    delay.fire_at = now() - timedelta(seconds=1)
    db_session.commit()
    resumed = client.post(_auto_url(wid, automation_id) + f"/runs/{run_id}/resume", headers=headers)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["id"] == run_id and resumed.json()["status"] == "success"
    assert db_session.get(WorkflowDelayState, delay.id).status == "resumed"
    timeline = client.get(
        _auto_url(wid, automation_id) + f"/runs/{run_id}/timeline", headers=headers
    ).json()
    assert [step["step_id"] for step in timeline["steps"]] == ["before", "after"]
    assert client.post(
        _auto_url(wid, automation_id) + f"/runs/{run_id}/resume", headers=headers
    ).status_code == 409

    dynamic_id = _create_automation(
        client, wid, headers,
        [
            {"id": "wait", "type": "delay", "seconds_field": "payload.wait_seconds"},
            {"id": "after", "type": "notify", "channel": "in_app"},
        ],
        name="Dynamic delay flow",
    )
    dynamic = client.post(
        _auto_url(wid, dynamic_id) + "/bulk_trigger", headers=headers,
        json={
            "recipients": [owner.id], "payload": {"wait_seconds": 90},
            "idempotency_key": "delay-dynamic",
        },
    )
    assert dynamic.status_code == 200, dynamic.text
    dynamic_run_id = dynamic.json()["runs"][0]["run_id"]
    dynamic_delay = db_session.execute(
        select(WorkflowDelayState).where(WorkflowDelayState.run_id == dynamic_run_id)
    ).scalar_one()
    remaining = (dynamic_delay.fire_at.replace(tzinfo=timezone.utc) - now()).total_seconds()
    assert 80 < remaining <= 90

    timestamp_id = _create_automation(
        client, wid, headers,
        [
            {"id": "wait", "type": "delay", "fire_at": "2030-01-01T00:00:00Z"},
            {"id": "after", "type": "action"},
        ],
        name="Timestamp delay flow",
    )
    timestamp = client.post(
        _auto_url(wid, timestamp_id) + "/bulk_trigger", headers=headers,
        json={"recipients": [owner.id], "payload": {}, "idempotency_key": "delay-timestamp"},
    )
    assert timestamp.status_code == 200, timestamp.text
    timestamp_delay = db_session.execute(
        select(WorkflowDelayState).where(
            WorkflowDelayState.run_id == timestamp.json()["runs"][0]["run_id"]
        )
    ).scalar_one()
    assert timestamp_delay.fire_at.year == 2030

    invalid_id = _create_automation(
        client, wid, headers,
        [
            {"id": "wait", "type": "delay", "seconds_field": "payload.missing"},
            {"id": "after", "type": "action"},
        ],
        name="Bad delay flow",
    )
    assert client.post(
        _auto_url(wid, invalid_id) + "/bulk_trigger", headers=headers,
        json={"recipients": [owner.id], "payload": {}, "idempotency_key": "delay-invalid"},
    ).status_code == 422


def test_nv011_scheduled_notification_resolves_recipient_timezone_and_fires(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    automation_id = _create_automation(
        client, wid, headers,
        [{
            "id": "wake", "type": "condition",
            "conditions": {"field": "payload.message", "op": "eq", "value": "wake up"},
        }],
        name="Schedule flow",
    )
    base = _auto_url(wid, automation_id) + "/schedule"
    response = client.post(
        base, headers=headers,
        json={
            "user_id": owner.id, "timezone": "Asia/Kolkata",
            "schedule": {"cadence": "day", "hour": 9, "minute": 30},
            "message": "wake up", "idempotency_key": "schedule-1",
        },
    )
    assert response.status_code == 201, response.text
    scheduled = response.json()
    scheduled_id = scheduled["id"]
    assert scheduled["timezone"] == "Asia/Kolkata" and scheduled["status"] == "scheduled"
    row = db_session.get(ScheduledRun, scheduled_id)
    # The local build has no IANA database; Asia/Kolkata is a fixed UTC+05:30
    # zone and the app resolves it through its documented fixed-offset table.
    kolkata = timezone(timedelta(hours=5, minutes=30))
    local = row.fire_at.replace(tzinfo=timezone.utc).astimezone(kolkata)
    assert (local.hour, local.minute) == (9, 30)

    assert client.post(
        base, headers=headers,
        json={
            "user_id": owner.id, "timezone": "Not/AZone",
            "schedule": {"cadence": "day", "hour": 9}, "idempotency_key": "schedule-bad",
        },
    ).status_code == 422
    listing = client.get(base, headers=headers)
    assert listing.status_code == 200 and [item["id"] for item in listing.json()] == [scheduled_id]

    assert client.post(
        base + f"/{scheduled_id}/fire", headers=headers
    ).status_code == 409
    row.fire_at = now() - timedelta(seconds=1)
    db_session.commit()
    fired = client.post(base + f"/{scheduled_id}/fire", headers=headers)
    assert fired.status_code == 200, fired.text
    assert fired.json()["trigger_event"] == "scheduled"
    assert db_session.get(ScheduledRun, scheduled_id).status == "fired"
    steps = db_session.execute(
        select(WorkflowRunStep).where(WorkflowRunStep.run_id == fired.json()["id"])
    ).scalars().all()
    assert len(steps) == 1 and steps[0].outcome == "ok"
    assert client.post(base + f"/{scheduled_id}/fire", headers=headers).status_code == 409


def test_nv048_run_timeline_records_real_step_outcomes_and_linked_messages(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    automation_id = _create_automation(
        client, wid, headers,
        [
            {"id": "matched", "type": "condition",
             "conditions": {"field": "payload.plan", "op": "eq", "value": "pro"}},
            {"id": "not_matched", "type": "condition",
             "conditions": {"field": "payload.plan", "op": "eq", "value": "free"}},
            {"id": "notify", "type": "notify", "channel": "in_app"},
            {"id": "approval", "type": "approval"},
        ],
        name="Timeline flow",
    )
    response = client.post(
        _auto_url(wid, automation_id) + "/bulk_trigger", headers=headers,
        json={
            "recipients": [owner.id], "payload": {"plan": "pro"},
            "message": "timeline message", "idempotency_key": "timeline-1",
        },
    )
    assert response.status_code == 200, response.text
    run_id = response.json()["runs"][0]["run_id"]
    timeline = client.get(
        _auto_url(wid, automation_id) + f"/runs/{run_id}/timeline", headers=headers
    )
    assert timeline.status_code == 200, timeline.text
    body = timeline.json()
    assert [step["step_id"] for step in body["steps"]] == [
        "matched", "not_matched", "notify", "approval"
    ]
    assert [step["outcome"] for step in body["steps"]] == [
        "ok", "skipped", "queued", "pending_approval"
    ]
    assert "not met" in body["steps"][1]["reason"]
    assert len(body["messages"]) == 1
    assert body["messages"][0]["message"] == "timeline message"
    assert body["messages"][0]["transaction_id"] == "bulk:timeline-1:0"
    link = db_session.execute(
        select(WorkflowMessageLink).where(WorkflowMessageLink.run_id == run_id)
    ).scalar_one()
    assert link.correlation_id == body["correlation_id"]
    assert db_session.get(Notification, link.notification_id).message == "timeline message"


def test_nv106_event_retrieve_exposes_real_steps_and_generated_messages(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    automation_id = _create_automation(
        client, wid, headers,
        [
            {"id": "include", "type": "condition",
             "conditions": {"field": "payload.plan", "op": "eq", "value": "pro"}},
            {"id": "exclude", "type": "condition",
             "conditions": {"field": "payload.plan", "op": "eq", "value": "free"}},
        ],
        name="Event detail flow",
    )
    triggered = client.post(
        _auto_url(wid, automation_id) + "/bulk_trigger", headers=headers,
        json={
            "recipients": [owner.id], "payload": {"plan": "pro"},
            "message": "linked message", "idempotency_key": "event-detail-1",
        },
    )
    assert triggered.status_code == 200, triggered.text
    event = db_session.execute(
        select(Event).where(
            Event.workspace_id == wid, Event.event_type == "workflow.trigger_received"
        )
    ).scalar_one()
    detail = client.get(
        OPERATIONS.format(wid=wid) + f"/events/{event.id}", headers=headers
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["event_id"] == event.id and body["correlation_id"] == event.correlation_id
    assert [(step["step_id"], step["outcome"]) for step in body["steps"]] == [
        ("include", "ok"), ("exclude", "skipped")
    ]
    assert len(body["messages"]) == 1
    assert body["messages"][0]["message"] == "linked message"
    assert body["messages"][0]["transaction_id"].startswith("bulk:event-detail-1:")

    listed = client.get(
        OPERATIONS.format(wid=wid) + "/audit",
        params={"event_type": "workflow.step_recorded", "correlation_id": event.correlation_id},
        headers=headers,
    )
    assert listed.status_code == 200 and len(listed.json()) == 2
    assert all(row["correlation_id"] == event.correlation_id for row in listed.json())
    missing = client.get(
        OPERATIONS.format(wid=wid) + "/events/does-not-exist", headers=headers
    )
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# NV-012 / NV-014 / NV-018: digest, throttle and schemas
# ---------------------------------------------------------------------------


def test_nv012_digest_window_batches_events_into_one_downstream_execution(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    automation_id = _create_automation(
        client, wid, headers,
        [{
            "id": "three_events", "type": "condition",
            "conditions": {
                "all": [
                    {"field": "payload.event_count", "op": "eq", "value": 3},
                    {"field": "payload.group_key", "op": "eq", "value": "invoice"},
                ]
            },
        }],
        name="Digest flow",
    )
    base = _auto_url(wid, automation_id) + "/digest"
    bucket_ids = set()
    for index in range(3):
        response = client.post(
            base + "/events", headers=headers,
            json={
                "user_id": owner.id, "group_key": "invoice",
                "payload": {"invoice": index}, "window_seconds": 3600,
                "idempotency_key": f"digest-{index}",
            },
        )
        assert response.status_code == 200, response.text
        bucket_ids.add(response.json()["id"])
    assert len(bucket_ids) == 1
    replay = client.post(
        base + "/events", headers=headers,
        json={
            "user_id": owner.id, "group_key": "invoice", "payload": {"invoice": 0},
            "window_seconds": 3600, "idempotency_key": "digest-0",
        },
    )
    assert replay.json()["event_count"] == 3
    buckets = client.get(base + "/buckets", headers=headers).json()
    assert len(buckets) == 1 and buckets[0]["event_count"] == 3
    bucket = db_session.get(DigestBucket, bucket_ids.pop())
    assert len(bucket.events) == 3 and bucket.status == "open"

    flushed = client.post(base + f"/buckets/{bucket.id}/flush", headers=headers)
    assert flushed.status_code == 200, flushed.text
    assert flushed.json()["status"] == "success"
    steps = db_session.execute(
        select(WorkflowRunStep).where(WorkflowRunStep.run_id == flushed.json()["id"])
    ).scalars().all()
    assert len(steps) == 1 and steps[0].outcome == "ok"
    assert "all group matched" in steps[0].reason
    assert client.post(base + f"/buckets/{bucket.id}/flush", headers=headers).status_code == 409
    flush_events = db_session.execute(
        select(Event).where(Event.workspace_id == wid, Event.event_type == "digest.flushed")
    ).scalars().all()
    assert len(flush_events) == 1 and flush_events[0].payload["event_count"] == 3


def test_nv014_throttle_skips_extra_triggers_without_creating_a_message(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    automation_id = _create_automation(
        client, wid, headers, [{"id": "act", "type": "action"}], name="Throttle flow"
    )
    base = _auto_url(wid, automation_id) + "/throttle"

    def trigger(key: str):
        return client.post(
            base, headers=headers,
            json={
                "user_id": owner.id, "payload": {"plan": "pro"}, "group_key": "plan:pro",
                "max_events": 1, "window_seconds": 3600, "message": "throttle message",
                "idempotency_key": key,
            },
        )

    first = trigger("throttle-1")
    assert first.status_code == 200, first.text
    assert first.json()["outcome"] == "success" and first.json()["message_created"] is True
    second = trigger("throttle-2")
    assert second.status_code == 200, second.text
    assert second.json()["outcome"] == "skipped"
    assert second.json()["message_created"] is False and second.json()["run_id"] == ""
    replay = trigger("throttle-2")
    assert replay.json()["outcome"] == "skipped"

    counter = db_session.execute(
        select(ThrottleCounter).where(ThrottleCounter.workspace_id == wid)
    ).scalar_one()
    assert counter.count == 2 and counter.group_key == "plan:pro"
    assert _count(db_session, AutomationRun, AutomationRun.workspace_id == wid) == 1
    assert _count(
        db_session, Notification, Notification.workspace_id == wid,
        Notification.user_id == owner.id,
    ) == 1
    skipped_events = db_session.execute(
        select(Event).where(Event.workspace_id == wid, Event.event_type == "throttle.skipped")
    ).scalars().all()
    assert len(skipped_events) == 1


def test_nv018_payload_schema_rejects_invalid_triggers_before_any_run(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    automation_id = _create_automation(
        client, wid, headers, [{"id": "act", "type": "action"}], name="Schema flow"
    )
    schema_url = _auto_url(wid, automation_id) + "/payload_schema"
    schema = client.put(
        schema_url, headers=headers,
        json={
            "fields": {
                "email": {"type": "str", "required": True},
                "age": {"type": "int", "required": False},
            }
        },
    )
    assert schema.status_code == 200, schema.text
    assert set(schema.json()["fields"]) == {"email", "age"}
    assert client.get(schema_url, headers=headers).json()["fields"]["email"]["required"] is True

    trigger_url = _auto_url(wid, automation_id) + "/bulk_trigger"

    def trigger(key, payload):
        return client.post(
            trigger_url, headers=headers,
            json={
                "recipients": [owner.id], "payload": payload, "idempotency_key": key,
            },
        )

    missing = trigger("schema-missing", {"age": 30})
    assert missing.status_code == 422 and "email" in str(missing.json()["detail"])
    wrong_type = trigger("schema-type", {"email": "a@example.test", "age": "old"})
    assert wrong_type.status_code == 422 and "age" in str(wrong_type.json()["detail"])
    unknown = trigger("schema-unknown", {"email": "a@example.test", "extra": 1})
    assert unknown.status_code == 422 and "extra" in str(unknown.json()["detail"])
    assert _count(db_session, AutomationRun, AutomationRun.workspace_id == wid) == 0
    assert _count(db_session, AutomationPayloadSchema, AutomationPayloadSchema.workspace_id == wid) == 1

    valid = trigger("schema-valid", {"email": "a@example.test", "age": 30})
    assert valid.status_code == 200, valid.text
    assert _count(db_session, AutomationRun, AutomationRun.workspace_id == wid) == 1


# ---------------------------------------------------------------------------
# NV-025 / NV-051 / NV-052 / NV-081 / NV-085: adapters, jobs and queue health
# ---------------------------------------------------------------------------


def test_nv025_provider_catalog_reports_four_truthful_capability_states(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    assert client.put(
        INTEGRATIONS.format(wid=wid), headers=headers,
        json={"provider": "gmail", "status": "configured", "config": {"region": "eu"}},
    ).status_code == 200
    assert client.put(
        INTEGRATIONS.format(wid=wid), headers=headers,
        json={"provider": "whatsapp", "status": "disabled", "config": {}},
    ).status_code == 200

    response = client.get(ADAPTERS.format(wid=wid) + "/capabilities", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    states = {entry["provider"]: entry["status"] for entry in body["providers"]}
    assert states["gmail"] == "configured"
    assert states["whatsapp"] == "disabled"
    assert states["sms"] == "not_configured"
    assert states["sendgrid"] == "blocked"
    assert set(body["states"]) == {"configured", "disabled", "not_configured", "blocked"}
    assert sum(body["counts"].values()) == len(body["providers"])
    assert all(body["counts"][state] >= 1 for state in body["states"])
    assert body["blocked_provider_count"] == 10
    assert body["configurable_provider_count"] <= 20
    assert "local mocks" in body["notes"]

    invoked = client.post(
        ADAPTERS.format(wid=wid) + "/gmail/invoke", headers=headers,
        json={"operation": "send", "request": {"to": "nobody@example.test"}},
    )
    assert invoked.status_code == 200, invoked.text
    assert invoked.json()["status"] == "recorded"
    assert invoked.json()["response"]["delivered"] is False
    assert invoked.json()["response"]["mode"] == "local_mock"
    blocked = client.post(
        ADAPTERS.format(wid=wid) + "/sendgrid/invoke", headers=headers,
        json={"operation": "send", "request": {}},
    )
    assert blocked.json()["status"] == "blocked"
    assert blocked.json()["response"]["delivered"] is False
    assert _count(db_session, AdapterCall, AdapterCall.workspace_id == wid) == 2


def test_nv051_retry_policy_is_documented_per_layer_and_mocks_are_not_deliveries(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    policy = client.get(JOBS.format(wid=wid) + "/policy/retry", headers=headers)
    assert policy.status_code == 200, policy.text
    policies = policy.json()["policies"]
    assert policies["local_job"]["implemented"] is True
    assert policies["provider"]["implemented"] is False
    assert policies["webhook"]["implemented"] is False
    assert "local mocks" in policy.json()["notes"].lower()

    failed = client.post(
        JOBS.format(wid=wid), headers=headers,
        json={
            "job_type": "notification.create", "max_attempts": 1,
            "payload": {
                "workspace_id": wid, "message": "", "channel": "email",
                "user_id": "ignored", "transaction_id": "retry-failure",
            },
        },
    )
    assert failed.status_code == 201, failed.text
    ran = client.post(JOBS.format(wid=wid) + "/run", headers=headers, json={"limit": 10})
    assert ran.status_code == 200, ran.text
    job = client.get(JOBS.format(wid=wid) + "/" + failed.json()["id"], headers=headers).json()
    assert job["status"] == "dead_letter" and job["result"] is None
    assert job["notes"].startswith("Jobs execute only registered local handlers")

    retried = client.post(
        JOBS.format(wid=wid), headers=headers,
        json={
            "job_type": "notification.create", "max_attempts": 3,
            "payload": {"workspace_id": wid, "message": "", "channel": "sms"},
        },
    )
    assert retried.status_code == 201, retried.text
    ran_again = client.post(JOBS.format(wid=wid) + "/run", headers=headers, json={"limit": 10})
    assert ran_again.json()["retried"] == 1
    retry_job = client.get(
        JOBS.format(wid=wid) + "/" + retried.json()["id"], headers=headers
    ).json()
    assert retry_job["status"] == "queued" and retry_job["attempts"] == 1
    assert retry_job["run_at"] > retry_job["created_at"]
    assert _count(db_session, Notification, Notification.workspace_id == wid) == 0


def test_nv052_failed_messages_are_queryable_and_emit_audit_events(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    other_wid, other_headers = _second_workspace(client, headers)
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()

    created = client.post(
        JOBS.format(wid=wid), headers=headers,
        json={
            "job_type": "notification.create", "max_attempts": 1,
            "payload": {
                "workspace_id": wid, "message": "", "channel": "push",
                "user_id": owner.id, "transaction_id": "failed-tx-1",
            },
        },
    )
    assert created.status_code == 201, created.text
    assert client.post(JOBS.format(wid=wid) + "/run", headers=headers, json={}).status_code == 200

    failures = client.get(
        JOBS.format(wid=wid) + "/messages/failed",
        params={"transaction_id": "failed-tx-1", "channel": "push"}, headers=headers,
    )
    assert failures.status_code == 200, failures.text
    assert len(failures.json()) == 1
    failure = failures.json()[0]
    assert failure["job_id"] == created.json()["id"]
    assert "requires a non-empty message" in failure["error"]
    assert "no delivery DLQ" in failure["notes"]
    assert _count(db_session, MessageFailure, MessageFailure.workspace_id == wid) == 1
    assert _count(db_session, MessageFailure, MessageFailure.workspace_id == other_wid) == 0
    assert client.get(
        JOBS.format(wid=wid) + "/messages/failed", headers=other_headers
    ).status_code == 403

    events = client.get(
        OPERATIONS.format(wid=wid) + "/audit",
        params={"event_type": "message.failed"}, headers=headers,
    )
    assert events.status_code == 200 and len(events.json()) == 1
    assert events.json()[0]["payload"]["transaction_id"] == "failed-tx-1"
    assert "delivered" not in events.json()[0]["payload"] or events.json()[0]["payload"]["delivered"] is False


def test_nv081_queue_health_reports_local_state_and_recovery_is_workspace_scoped(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    other_wid, other_headers = _second_workspace(client, headers)

    def enqueue(wid_value, headers_value):
        response = client.post(
            JOBS.format(wid=wid_value), headers=headers_value,
            json={"job_type": "noop", "payload": {"ok": True}},
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    own_job = enqueue(wid, headers)
    foreign_job = enqueue(other_wid, other_headers)
    job = db_session.get(Job, own_job)
    job.status = "running"
    job.locked_at = now() - timedelta(seconds=600)
    job.locked_by = "crashed-worker"
    db_session.commit()

    health = client.get(
        OPERATIONS.format(wid=wid) + "/queue-health",
        params={"stale_after_seconds": 300}, headers=headers,
    )
    assert health.status_code == 200, health.text
    assert health.json()["running"] == 1 and health.json()["stale_running"] == 1
    assert health.json()["total"] == 1 and "no external broker" in health.json()["notes"]
    other_health = client.get(
        OPERATIONS.format(wid=other_wid) + "/queue-health",
        params={"stale_after_seconds": 300}, headers=other_headers,
    )
    assert other_health.json()["stale_running"] == 0

    recovered = client.post(
        JOBS.format(wid=wid) + "/recover",
        params={"stale_after_seconds": 300}, headers=headers,
    )
    assert recovered.status_code == 200 and recovered.json()["recovered"] == 1
    assert db_session.get(Job, own_job).status == "queued"
    assert db_session.get(Job, foreign_job).status == "queued"
    assert "local" in recovered.json()["notes"].lower()
    after = client.get(
        OPERATIONS.format(wid=wid) + "/queue-health",
        params={"stale_after_seconds": 300}, headers=headers,
    )
    assert after.json()["stale_running"] == 0 and after.json()["queued"] == 1


def test_nv085_message_records_are_queryable_by_channel_subscriber_and_transaction(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    base = ADAPTERS.format(wid=wid) + "/messages"
    created = client.post(
        base + "/record", headers=headers,
        json={
            "channel": "Email", "subscriber_id": owner.id,
            "transaction_id": "message-record-1", "provider": "gmail",
            "content": "local only",
        },
    )
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["delivered"] is False and record["status"] == "recorded"
    assert "no external delivery" in record["note"]
    assert client.post(
        base + "/record", headers=headers,
        json={
            "channel": "email", "subscriber_id": owner.id,
            "transaction_id": "message-record-1",
        },
    ).status_code == 409

    listing = client.get(
        base, headers=headers,
        params={"channel": "email", "subscriber_id": owner.id, "transaction_id": "message-record-1"},
    )
    assert listing.status_code == 200 and [row["id"] for row in listing.json()] == [record["id"]]
    assert client.get(base + f"/{record['id']}", headers=headers).json()["delivered"] is False
    assert _count(db_session, MessageRecord, MessageRecord.workspace_id == wid) == 1

    deleted = client.delete(base + f"/{record['id']}", headers=headers)
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True
    assert client.get(base + f"/{record['id']}", headers=headers).status_code == 404
    assert client.get(base, headers=headers).json() == []


# ---------------------------------------------------------------------------
# NV-033 / NV-034 / NV-042 / NV-089 / NV-099: inbox and notification API
# ---------------------------------------------------------------------------


def test_nv033_native_light_theme_notification_panel_uses_only_the_local_api():
    app_js = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")
    assert "async function loadNotifications(token)" in app_js
    assert "case 'notifications': return loadNotifications(token)" in app_js
    assert "api(apiW('/notifications'))" in app_js
    assert "api(apiW('/notifications/counts'))" in app_js
    assert "data-action=\"read-notification\"" in app_js
    assert "data-action=\"read-all-notifications\"" in app_js
    assert "icon('bell'" in app_js
    assert "subscribeNotificationStream()" in app_js
    assert "@novu" not in app_js and "<Inbox" not in app_js
    assert "prefers-color-scheme" not in styles and "Light-only" in styles


def test_nv034_bell_unread_counts_match_the_database_after_create_and_read(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    first = _notification(db_session, wid, owner.id, "first", category="sales")
    _notification(db_session, wid, owner.id, "second", category="sales")
    _notification(db_session, wid, None, "broadcast", category="general")

    counts_url = NOTIFICATIONS.format(wid=wid) + "/counts"
    counts = client.get(counts_url, headers=headers)
    assert counts.status_code == 200, counts.text
    assert counts.json() == {
        "total": 3, "unread": 3, "unseen": 3,
        "by_category": {"sales": 2, "general": 1},
    }
    read = client.post(NOTIFICATIONS.format(wid=wid) + f"/{first.id}/read", headers=headers)
    assert read.status_code == 200 and read.json()["id"] == first.id
    assert read.json()["read"] is True
    assert client.get(counts_url, headers=headers).json()["unread"] == 2
    seen = client.post(NOTIFICATIONS.format(wid=wid) + "/seen-all", headers=headers)
    assert seen.status_code == 200 and seen.json()["unseen"] == 0
    app_js = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
    assert "data-unread-dot" in app_js and "updateUnreadBadge()" in app_js


def test_nv042_notification_api_cannot_be_read_by_guessing_a_subscriber_id(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    teammate = _member(db_session, wid, "subscriber-guess@example.test")
    private = _notification(db_session, wid, owner.id, "owner private message")
    mine = _notification(db_session, wid, teammate.id, "teammate message")

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": teammate.email, "password": "Password123!", "workspace_id": wid,
        },
    )
    assert login.status_code == 200, login.text
    teammate_headers = auth(login.json()["access_token"])
    base = NOTIFICATIONS.format(wid=wid)
    for attempt in (
        client.get(base),
        client.get(base, params={"subscriber_id": owner.id}),
        client.get(base, headers={"X-Subscriber-Id": owner.id}),
        client.get(base + "/counts", headers={"X-Subscriber-Id": owner.id}),
    ):
        assert attempt.status_code == 401

    guessed = client.get(
        base, headers=teammate_headers, params={"subscriber_id": owner.id}
    )
    assert guessed.status_code == 200, guessed.text
    visible = {row["id"] for row in guessed.json()}
    assert mine.id in visible and private.id not in visible
    assert all(row["message"] != "owner private message" for row in guessed.json())
    assert client.get(
        base + f"/{private.id}/read", headers=teammate_headers
    ).status_code == 404
    assert db_session.get(Notification, private.id).read is False


def test_nv089_notification_stream_updates_without_a_manual_reload_and_is_workspace_scoped(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    other_wid, other_headers = _second_workspace(client, headers)
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    _notification(db_session, wid, owner.id, "first")

    denied = client.get(
        NOTIFICATIONS.format(wid=wid) + "/stream", headers=other_headers
    )
    assert denied.status_code == 403

    app_js = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
    assert "subscribeNotificationStream();" in app_js
    assert "fetch(apiW('/notifications/stream')" in app_js
    assert "loadNotificationsSilently();" in app_js

    with client.stream(
        "GET", NOTIFICATIONS.format(wid=wid) + "/stream", headers=headers
    ) as response:
        assert response.status_code == 200, str(response.headers)
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = response.iter_lines()

        def next_snapshot():
            for line in lines:
                if line.startswith("data: "):
                    return json.loads(line[len("data: "):])
            raise AssertionError("stream ended before a counts snapshot arrived")

        initial = next_snapshot()
        assert initial["unread"] == 1 and initial["total"] == 1
        _notification(db_session, wid, owner.id, "second")
        updated = next_snapshot()
        assert updated["unread"] == 2 and updated["total"] == 2
        other_snapshot = client.get(
            NOTIFICATIONS.format(wid=other_wid) + "/counts", headers=other_headers
        ).json()
        assert other_snapshot["total"] == 0


def test_nv099_templates_resolve_allowed_variables_and_reject_scripts_or_credentials(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = PREFERENCES.format(wid=wid) + "/preview"

    rendered = client.post(
        base, headers=headers,
        json={
            "template": "Hello {{ payload.name | lower }} ({{ payload.count }})",
            "values": {"payload": {"name": "ANN<SMITH>", "count": 2}},
        },
    )
    assert rendered.status_code == 200, rendered.text
    assert rendered.json()["rendered"] == "Hello ann&lt;smith&gt; (2)"

    escaped = client.post(
        base, headers=headers,
        json={"template": "{{ payload.value | upper }}", "values": {"payload": {"value": "a&b"}}},
    )
    assert escaped.status_code == 200 and escaped.json()["rendered"] == "A&amp;B"

    for template, values in (
        ("<script>alert(1)</script>", {}),
        ("{{ payload.name }}", {"payload": {"name": "<iframe src='x'></iframe>"}}),
        ("{{ secrets.api_token }}", {"secrets": {"api_token": "do-not-leak"}}),
        ("{{ payload.password }}", {"payload": {"password": "do-not-leak"}}),
        ("{{ payload.name + 1 }}", {"payload": {"name": "x"}}),
    ):
        rejected = client.post(
            base, headers=headers, json={"template": template, "values": values}
        )
        assert rejected.status_code == 422, (template, rejected.text)
        assert "do-not-leak" not in rejected.text


# ---------------------------------------------------------------------------
# NV-045 / NV-046: topics and subscriptions
# ---------------------------------------------------------------------------


def test_nv045_topics_are_workspace_unique_with_full_lifecycle(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    other_wid, other_headers = _second_workspace(client, headers)
    base = _auto_url(wid) + "/topics"
    created = client.post(
        base + "/create", headers=headers, json={"key": "release", "name": "Release notes"}
    )
    assert created.status_code == 201, created.text
    topic_id = created.json()["id"]
    assert client.post(
        base + "/create", headers=headers, json={"key": "release", "name": "Duplicate"}
    ).status_code == 409
    assert [row["id"] for row in client.get(base + "/list", headers=headers).json()] == [topic_id]
    assert client.get(base + f"/get/{topic_id}", headers=headers).json()["name"] == "Release notes"

    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    subscribed = client.post(
        _auto_url(wid) + f"/topics/{topic_id}/subscriptions/create", headers=headers,
        json={"user_id": owner.id},
    )
    assert subscribed.status_code == 201, subscribed.text

    patched = client.patch(
        base + f"/update/{topic_id}", headers=headers, json={"name": "Product updates"}
    )
    assert patched.status_code == 200 and patched.json()["name"] == "Product updates"
    assert client.get(
        _auto_url(other_wid) + "/topics/get/" + topic_id, headers=other_headers
    ).status_code == 404
    assert client.get(base + "/list", headers=other_headers).status_code == 403

    deleted = client.delete(base + f"/delete/{topic_id}", headers=headers)
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True
    assert client.get(base + f"/get/{topic_id}", headers=headers).status_code == 404
    assert _count(db_session, TopicSubscription, TopicSubscription.workspace_id == wid) == 0
    assert _count(db_session, Topic, Topic.workspace_id == wid) == 0


def test_nv046_only_subscriptions_matching_payload_conditions_and_context_fan_out(
    client, db_session
):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(select(User).where(User.email == "owner@example.com")).scalar_one()
    matching, wrong_condition, wrong_context, disabled = [
        _member(db_session, wid, f"sub{i}@example.test") for i in range(4)
    ]
    automation_id = _create_automation(
        client, wid, headers, [{"id": "act", "type": "action"}], name="Subscription flow"
    )
    topic = client.post(
        _auto_url(wid) + "/topics/create", headers=headers,
        json={"key": "regional", "name": "Regional"},
    )
    assert topic.status_code == 201, topic.text
    topic_id = topic.json()["id"]
    condition = {
        "all": [
            {"field": "payload.region", "op": "eq", "value": "EU"},
            {"field": "subscriber.id", "op": "exists"},
        ]
    }

    def subscribe(user_id, context, enabled=True):
        response = client.post(
            _auto_url(wid) + f"/topics/{topic_id}/subscriptions/create", headers=headers,
            json={
                "user_id": user_id, "conditions": condition,
                "context": context, "enabled": enabled,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    matching_sub = subscribe(matching.id, {"tenant": "acme"})
    wrong_condition_sub = subscribe(
        wrong_condition.id, {"tenant": "acme"},
    )
    wrong_context_sub = subscribe(wrong_context.id, {"tenant": "other"})
    disabled_sub = subscribe(disabled.id, {"tenant": "acme"}, enabled=False)

    original_condition = client.get(
        _auto_url(wid) + f"/topics/{topic_id}/subscriptions/list", headers=headers
    ).json()
    assert len(original_condition) == 4
    # Make the second subscriber's condition different from the matching one.
    assert client.patch(
        _auto_url(wid) + f"/topics/{topic_id}/subscriptions/update/{wrong_condition_sub}",
        headers=headers,
        json={"conditions": {"field": "payload.region", "op": "eq", "value": "US"}},
    ).status_code == 200

    trigger = {
        "topic_key": "regional", "payload": {"region": "EU"},
        "context": {"tenant": "acme"}, "exclude_actor": True,
    }
    first = client.post(
        _auto_url(wid, automation_id) + "/topic_trigger", headers=headers,
        json=dict(trigger, idempotency_key="sub-first"),
    )
    assert first.status_code == 200, first.text
    assert {run["user_id"] for run in first.json()["runs"]} == {matching.id}

    for subscription_id, body in (
        (wrong_condition_sub, {"conditions": condition}),
        (wrong_context_sub, {"context": {"tenant": "acme"}}),
        (disabled_sub, {"enabled": True}),
    ):
        response = client.patch(
            _auto_url(wid) + f"/topics/{topic_id}/subscriptions/update/{subscription_id}",
            headers=headers, json=body,
        )
        assert response.status_code == 200, response.text
    second = client.post(
        _auto_url(wid, automation_id) + "/topic_trigger", headers=headers,
        json=dict(trigger, idempotency_key="sub-second"),
    )
    assert second.status_code == 200, second.text
    assert {run["user_id"] for run in second.json()["runs"]} == {
        matching.id, wrong_condition.id, wrong_context.id, disabled.id
    }
    assert owner.id not in {run["user_id"] for run in second.json()["runs"]}
    assert matching_sub in {row["id"] for row in original_condition}
