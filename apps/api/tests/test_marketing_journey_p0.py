"""Named acceptance tests for the P0 Mautic marketing/journey cluster.

MT-025: a campaign can be authored, scheduled and executed locally through a
UI-backed API. MT-112: the clean-room marketing module satisfies FEATURE_MATRIX
M1-M3 with no embedded Mautic code and no delivery client. MT-115: every
lifecycle event named in 03-plane-mautic.md section 2.15 is emitted by a real
action, persisted on the shared event spine and queryable for analytics.

Nothing in this module sends an email, message, page or webhook externally.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from novara_core.events import EVENT_TYPES
from novara_core.models import Contact, Event
from novara_core.modules import marketing

from .conftest import auth, bootstrap


def _campaign(client, wid, headers, name="Launch", **extra):
    body = {"name": name, "channel": "email", "status": "draft"}
    body.update(extra)
    created = client.post(f"/api/v1/workspaces/{wid}/campaigns", headers=headers, json=body)
    assert created.status_code == 201, created.text
    return created.json()


def _contact(client, wid, headers, email="journey@example.com"):
    created = client.post(f"/api/v1/workspaces/{wid}/contacts", headers=headers,
                          json={"full_name": "Journey Contact", "email": email})
    assert created.status_code == 201, created.text
    return created.json()


def _event_types(db_session, wid):
    return {e.event_type for e in db_session.execute(
        select(Event).where(Event.workspace_id == wid)
    ).scalars().all()}


def test_campaign_can_be_authored_scheduled_and_activated_locally(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/campaigns"
    campaign = _campaign(client, wid, headers)

    bad = client.post(f"{base}/{campaign['id']}/schedule", headers=headers, json={
        "start_at": "2026-05-01T00:00:00Z", "end_at": "2026-04-01T00:00:00Z",
    })
    assert bad.status_code == 422, bad.text

    past = (marketing.now() - timedelta(days=1)).isoformat()
    future = (marketing.now() + timedelta(days=1)).isoformat()
    scheduled = client.post(f"{base}/{campaign['id']}/schedule", headers=headers, json={
        "start_at": past, "end_at": future,
    })
    assert scheduled.status_code == 200, scheduled.text
    # FastAPI serialises UTC as "...Z"; compare the instant, not the spelling.
    assert scheduled.json()["start_at"][:19] == past[:19]
    assert scheduled.json()["end_at"] is not None

    due = client.post(f"{base}/due", headers=headers)
    assert due.status_code == 200, due.text
    assert [row["id"] for row in due.json()] == [campaign["id"]]
    assert client.get(f"{base}/{campaign['id']}", headers=headers).json()["campaign"]["status"] == "active"
    assert marketing.CAMPAIGN_STATUS_CHANGED in _event_types(db_session, wid)


def test_journey_execution_records_local_events_and_respects_consent(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/campaigns"
    campaign = _campaign(client, wid, headers)
    cb = f"{base}/{campaign['id']}"
    contact = _contact(client, wid, headers)

    for position, action in ((1, marketing.EMAIL_SENT), (2, marketing.EMAIL_OPENED)):
        step = client.post(f"{cb}/journey-steps", headers=headers, json={
            "position": position, "channel": "email", "action": action,
            "label": f"Local {action} record",
        })
        assert step.status_code == 201, step.text
    duplicate = client.post(f"{cb}/journey-steps", headers=headers, json={
        "position": 1, "channel": "email", "action": marketing.EMAIL_SENT, "label": "Dup",
    })
    assert duplicate.status_code == 409
    bad_action = client.post(f"{cb}/journey-steps", headers=headers, json={
        "position": 3, "channel": "email", "action": "email.delivered_externally", "label": "Bad",
    })
    assert bad_action.status_code == 422

    enrolled = client.post(f"{cb}/enrollments", headers=headers,
                           json={"contact_id": contact["id"]})
    assert enrolled.status_code == 201, enrolled.text
    assert enrolled.json()["status"] == "active"
    assert client.post(f"{cb}/enrollments", headers=headers,
                       json={"contact_id": contact["id"]}).status_code == 409

    first = client.post(f"{cb}/run", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["advanced"] == 1
    assert marketing.EMAIL_SENT in first.json()["event_types"]
    second = client.post(f"{cb}/run", headers=headers)
    assert second.json()["advanced"] == 1
    assert second.json()["completed"] == 1
    assert marketing.CAMPAIGN_EXITED in second.json()["event_types"]
    assert client.get(f"{cb}/enrollments", headers=headers).json()[0]["status"] == "exited"

    engagement = client.post(f"{cb}/engagement", headers=headers, json={
        "contact_id": contact["id"], "kind": "clicked",
    })
    assert engagement.status_code == 201 and engagement.json()["recorded"] == marketing.EMAIL_CLICKED

    # Re-running is idempotent: one email.sent event, not one per run.
    types = _event_types(db_session, wid)
    assert {marketing.EMAIL_SENT, marketing.EMAIL_OPENED, marketing.EMAIL_CLICKED,
            marketing.JOURNEY_STEP_COMPLETED, marketing.CAMPAIGN_ENTERED,
            marketing.CAMPAIGN_EXITED}.issubset(types)
    sent_events = [e for e in db_session.execute(
        select(Event).where(Event.workspace_id == wid, Event.event_type == marketing.EMAIL_SENT)
    ).scalars().all()]
    assert len(sent_events) == 1

    # A suppressed contact is refused at enrollment, before any step can run.
    blocked = _contact(client, wid, headers, email="blocked@example.com")
    row = db_session.get(Contact, blocked["id"])
    row.do_not_contact = True
    db_session.commit()
    refused = client.post(f"{cb}/enrollments", headers=headers, json={"contact_id": blocked["id"]})
    assert refused.status_code == 409, refused.text


def test_all_listed_lifecycle_events_are_registered_emitted_and_queryable(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/campaigns"
    campaign = _campaign(client, wid, headers)
    cb = f"{base}/{campaign['id']}"
    contact = _contact(client, wid, headers)

    segment = client.post(f"{base}/segments", headers=headers,
                          json={"name": "Interested", "criteria": {"source": "website"}})
    assert segment.status_code == 201, segment.text
    assert client.post(f"{cb}/enrollments", headers=headers, json={
        "contact_id": contact["id"], "segment_id": segment.json()["id"],
    }).status_code == 201
    assert client.post(f"{cb}/journey-steps", headers=headers, json={
        "position": 1, "channel": "email", "action": marketing.EMAIL_SENT, "label": "Record send",
    }).status_code == 201
    assert client.post(f"{cb}/run", headers=headers).status_code == 200
    for kind in ("opened", "clicked"):
        assert client.post(f"{cb}/engagement", headers=headers,
                           json={"contact_id": contact["id"], "kind": kind}).status_code == 201
    assert client.delete(f"{cb}/enrollments/{contact['id']}", headers=headers).status_code == 200
    for kind in ("form.submitted", "page.visited", "webhook.received"):
        intake = client.post(f"{base}/analytics/lifecycle", headers=headers,
                             json={"kind": kind, "source": "local-test"})
        assert intake.status_code == 201, intake.text

    expected = set(marketing.LIFECYCLE_EVENTS)
    assert expected.issubset(EVENT_TYPES)
    emitted = _event_types(db_session, wid)
    assert expected.issubset(emitted), f"missing events: {expected - emitted}"

    listed = client.get(f"{base}/analytics/lifecycle", headers=headers)
    assert listed.status_code == 200, listed.text
    kinds = {row["event_type"] for row in listed.json()}
    assert kinds == expected
    filtered = client.get(f"{base}/analytics/lifecycle", headers=headers,
                          params={"kind": marketing.WEBHOOK_RECEIVED})
    assert [row["event_type"] for row in filtered.json()] == [marketing.WEBHOOK_RECEIVED]
    assert client.get(f"{base}/analytics/lifecycle", headers=headers,
                      params={"kind": "email.delivered_externally"}).status_code == 422


def test_marketing_module_is_clean_room_and_satisfies_m1_to_m3():
    source = Path(marketing.__file__).read_text(encoding="utf-8")
    for forbidden in ("import mautic", "from mautic", "import httpx", "import requests",
                      "import smtplib", "import aiohttp", "from novara_core.modules.mautic"):
        assert forbidden not in source, f"forbidden dependency: {forbidden}"
    assert "Nothing is sent externally" in source
    assert "local_only" in source

    suite = (Path(marketing.__file__).parents[2] / "tests" / "test_marketing.py").read_text(encoding="utf-8")
    for named_test in (
        "test_campaign_metrics_rollups_summary_and_events",
        "test_duplicate_campaign_names_are_rejected",
        "test_invalid_campaign_payloads_are_rejected",
        "test_campaigns_are_isolated_by_workspace",
    ):
        assert f"def {named_test}(" in suite, f"missing M1-M3 evidence: {named_test}"
