"""Named acceptance tests for the remaining Mautic P1 parity rows.

Every test exercises clean-room NOVARA code. Contacts, events and local delivery
records are real rows in the isolated test database; the only socket opened is a
loopback HTTP server owned by the webhook test itself. No Mautic source, external
service, credential, fake success or placeholder delivery is used.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from sqlalchemy import select

from novara_core.events import EVENT_TYPES, publish_event
from novara_core.models import Contact, Event, Lead, new_id, now
from novara_core.modules import crm_intelligence as crm
from novara_core.modules import email_campaigns as email_mod
from novara_core.modules import marketing
from novara_core.permissions import (
    ALL,
    CONTACT_READ,
    CONTACT_WRITE,
    EVENT_READ,
    LEAD_READ,
    ROLE_PERMISSIONS,
    WORKSPACE_MANAGE,
    has_permission,
)

from .conftest import auth, bootstrap

API = "/api/v1"


def _setup(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _contact(db, workspace_id: str, email_address: str, **fields) -> Contact:
    payload = dict(
        id=new_id(),
        workspace_id=workspace_id,
        email=email_address,
        created_at=now(),
        updated_at=now(),
    )
    payload.update(fields)
    contact = Contact(**payload)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def _lead(db, workspace_id: str, contact: Contact, **fields) -> Lead:
    lead = Lead(
        id=new_id(),
        workspace_id=workspace_id,
        contact_id=contact.id,
        score=int(fields.pop("score", 0)),
        created_at=now(),
        **fields,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _publish(db, workspace_id: str, event_type: str, **kwargs) -> None:
    publish_event(db, workspace_id=workspace_id, event_type=event_type, **kwargs)
    db.commit()


def _event_types(client, workspace_id: str, headers: dict) -> set[str]:
    response = client.get(f"{API}/workspaces/{workspace_id}/events?limit=500", headers=headers)
    assert response.status_code == 200, response.text
    return {row["event_type"] for row in response.json()}


def _campaign(client, workspace_id: str, headers: dict, name: str = "Launch") -> dict:
    response = client.post(
        f"{API}/workspaces/{workspace_id}/campaigns",
        headers=headers,
        json={"name": name, "channel": "email", "status": "draft"},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# MT-001 — a real NOVARA-native marketing module
# ---------------------------------------------------------------------------


def test_mt001_native_marketing_module_is_real_and_workspace_scoped(client, db_session):
    wid, headers = _setup(client)
    base = f"{API}/workspaces/{wid}/campaigns"

    invalid = client.post(base, headers=headers, json={"name": "", "channel": "email", "extra": 1})
    assert invalid.status_code == 422, invalid.text
    assert client.get(base).status_code == 401

    campaign = _campaign(client, wid, headers, "Native launch")
    segment = client.post(
        f"{base}/segments", headers=headers,
        json={"name": "High intent", "criteria": {"lifecycle_stage": "lead"}},
    )
    assert segment.status_code == 201, segment.text
    contact = _contact(db_session, wid, "native@example.com", full_name="Native User")
    step = client.post(
        f"{base}/{campaign['id']}/journey-steps", headers=headers,
        json={"position": 1, "channel": "email", "action": marketing.EMAIL_SENT, "label": "Local send"},
    )
    assert step.status_code == 201, step.text
    enrolled = client.post(
        f"{base}/{campaign['id']}/enrollments", headers=headers,
        json={"contact_id": contact.id, "segment_id": segment.json()["id"]},
    )
    assert enrolled.status_code == 201, enrolled.text
    run = client.post(f"{base}/{campaign['id']}/run", headers=headers)
    assert run.status_code == 200, run.text
    assert set(run.json()["event_types"]) >= {
        marketing.EMAIL_SENT, marketing.JOURNEY_STEP_COMPLETED, marketing.CAMPAIGN_EXITED,
    }
    for kind in ("opened", "clicked"):
        response = client.post(
            f"{base}/{campaign['id']}/engagement", headers=headers,
            json={"contact_id": contact.id, "kind": kind},
        )
        assert response.status_code == 201, response.text

    emitted = _event_types(client, wid, headers)
    assert {
        marketing.CAMPAIGN_CREATED, marketing.CONTACT_SEGMENTED, marketing.CAMPAIGN_ENTERED,
        marketing.EMAIL_SENT, marketing.EMAIL_OPENED, marketing.EMAIL_CLICKED,
        marketing.JOURNEY_STEP_COMPLETED, marketing.CAMPAIGN_EXITED,
    } <= emitted

    source = Path(marketing.__file__).read_text(encoding="utf-8")
    for forbidden in ("import mautic", "from mautic", "import httpx", "import requests", "import smtplib"):
        assert forbidden not in source
    assert "Nothing is sent externally" in source

    # Bootstrap is single-use: create the second workspace with the normal
    # authenticated endpoint instead of re-running first-run setup.
    other_response = client.post(
        f"{API}/workspaces", headers=headers, json={"name": "Other"}
    )
    assert other_response.status_code == 200, other_response.text
    other = other_response.json()
    other_headers = auth(other["access_token"])
    assert client.get(base, headers=other_headers).status_code == 403
    assert client.get(
        f"{API}/workspaces/{other['workspace_id']}/campaigns", headers=other_headers
    ).json() == []


# ---------------------------------------------------------------------------
# MT-003 — extension contract
# ---------------------------------------------------------------------------


def test_mt003_extension_contract_is_documented_and_enforced(client):
    assert "name:" in marketing.MARKETING_EXTENSION_CONTRACT
    assert "events:" in marketing.MARKETING_EXTENSION_CONTRACT
    assert "handle(event_type, context)" in marketing.MARKETING_EXTENSION_CONTRACT

    seen: list[dict] = []

    class Observer:
        name = "p1_observer"
        events = frozenset({marketing.FORM_SUBMITTED})

        def handle(self, event_type: str, context: dict) -> None:
            context["observed"] = True
            seen.append({"event_type": event_type, "context": dict(context)})

    observer = Observer()
    assert marketing.register_marketing_extension(observer) == "p1_observer"
    try:
        context = {"form_id": "form-1"}
        called = marketing.dispatch_marketing_extension(marketing.FORM_SUBMITTED, context)
        assert called == ["p1_observer"]
        assert context == {"form_id": "form-1"}, "dispatch must not mutate caller context"
        assert seen == [{
            "event_type": marketing.FORM_SUBMITTED,
            "context": {"form_id": "form-1", "observed": True},
        }]
        assert marketing.dispatch_marketing_extension(marketing.EMAIL_SENT, {}) == []

        with pytest.raises(ValueError):
            marketing.register_marketing_extension(observer)
        with pytest.raises(ValueError):
            marketing.register_marketing_extension(type("Bad", (), {"name": "Bad Name", "events": ["x"], "handle": lambda *a: None})())
        with pytest.raises(ValueError):
            marketing.register_marketing_extension(type("Bad", (), {"name": "no_events", "events": [], "handle": lambda *a: None})())
    finally:
        marketing.unregister_marketing_extension("p1_observer")


# ---------------------------------------------------------------------------
# MT-007 — contact profile richness and search
# ---------------------------------------------------------------------------


def test_mt007_contact_profile_search_and_update_are_auditable(client, db_session):
    wid, headers = _setup(client)
    crm_base = f"{API}/workspaces/{wid}/crm"
    alice = _contact(
        db_session, wid, "alice@example.com", full_name="Alice Owner", phone="555-1000",
        company_name="Acme", tags=["vip", "launch"], custom_fields={"plan": "pro"},
        lifecycle_stage="lead",
    )
    _contact(db_session, wid, "bob@example.com", full_name="Bob Buyer", tags=["buyer"])

    field = client.post(
        f"{crm_base}/contact-fields", headers=headers,
        json={"key": "plan", "label": "Plan", "type": "select", "options": ["free", "pro"]},
    )
    assert field.status_code == 201, field.text

    patched = client.patch(
        f"{crm_base}/contact-profiles/{alice.id}", headers=headers,
        json={"tags": ["vip", "priority"], "custom_fields": {"plan": "pro"}},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["tags"] == ["vip", "priority"]
    assert body["custom_fields"]["plan"] == "pro"
    assert body["company_name"] == "Acme"

    assert [row["id"] for row in client.get(
        f"{crm_base}/contact-profiles/search", headers=headers, params={"query": "alice"}
    ).json()] == [alice.id]
    assert [row["id"] for row in client.get(
        f"{crm_base}/contact-profiles/search", headers=headers, params={"tag": "priority"}
    ).json()] == [alice.id]
    assert [row["id"] for row in client.get(
        f"{crm_base}/contact-profiles/search", headers=headers,
        params={"field_key": "plan", "field_value": "pro"},
    ).json()] == [alice.id]

    invalid = client.patch(
        f"{crm_base}/contact-profiles/{alice.id}", headers=headers, json={"tags": [7]}
    )
    assert invalid.status_code == 422, invalid.text
    assert {crm.CONTACT_PROFILE_UPDATED, crm.CONTACT_FIELD_DEFINED} <= _event_types(client, wid, headers)


# ---------------------------------------------------------------------------
# MT-011 — configurable custom fields
# ---------------------------------------------------------------------------


def test_mt011_custom_fields_validate_filter_and_public_update(client, db_session):
    wid, headers = _setup(client)
    crm_base = f"{API}/workspaces/{wid}/crm"

    plan = client.post(
        f"{crm_base}/contact-fields", headers=headers,
        json={
            "key": "plan", "label": "Plan", "type": "select", "required": True,
            "public_update": True, "options": ["free", "pro"],
        },
    )
    assert plan.status_code == 201, plan.text
    age = client.post(
        f"{crm_base}/contact-fields", headers=headers,
        json={"key": "age", "label": "Age", "type": "number", "public_update": False},
    )
    assert age.status_code == 201, age.text
    assert client.post(
        f"{crm_base}/contact-fields", headers=headers,
        json={"key": "email", "label": "Email", "type": "email"},
    ).status_code == 422

    contact = _contact(
        db_session, wid, "fields@example.com", custom_fields={"plan": "free", "age": 30}
    )
    profile_url = f"{crm_base}/contact-profiles/{contact.id}"
    ok = client.patch(
        profile_url, headers=headers, json={"custom_fields": {"plan": "pro", "age": 31}}
    )
    assert ok.status_code == 200, ok.text
    assert client.patch(
        profile_url, headers=headers, json={"custom_fields": {"age": 32}}
    ).status_code == 422
    assert client.patch(
        profile_url, headers=headers, json={"custom_fields": {"plan": "gold"}}
    ).status_code == 422
    assert [row["id"] for row in client.get(
        f"{crm_base}/contact-profiles/search", headers=headers,
        params={"field_key": "plan", "field_value": "pro"},
    ).json()] == [contact.id]

    token_response = client.get(
        f"{crm_base}/contact-fields/public-token", headers=headers,
        params={"contact_id": contact.id},
    )
    assert token_response.status_code == 200, token_response.text
    token = token_response.json()["token"]
    public_url = f"{crm_base}/contact-fields/public-update"
    assert client.post(public_url, json={"token": "wrong", "values": {"plan": "pro"}}).status_code == 400
    assert client.post(public_url, json={"token": token, "values": {"age": 33}}).status_code == 422
    updated = client.post(public_url, json={"token": token, "values": {"plan": "pro"}})
    assert updated.status_code == 200, updated.text
    db_session.refresh(contact)
    assert contact.custom_fields["plan"] == "pro"
    assert contact.custom_fields["age"] == 31

    # CONTACT_FIELD_UPDATED audits a change to a field *definition*: exercise
    # that endpoint rather than expecting it from a contact-value update.
    relabeled = client.patch(
        f"{crm_base}/contact-fields/{plan.json()['id']}", headers=headers,
        json={"label": "Plan (revised)"},
    )
    assert relabeled.status_code == 200, relabeled.text
    assert relabeled.json()["label"] == "Plan (revised)"

    assert {
        crm.CONTACT_FIELD_DEFINED, crm.CONTACT_FIELD_UPDATED,
        crm.CONTACT_PUBLIC_FIELD_UPDATED, crm.CONTACT_PROFILE_UPDATED,
    } <= _event_types(client, wid, headers)


# ---------------------------------------------------------------------------
# MT-016 — safe token substitution
# ---------------------------------------------------------------------------


def test_mt016_token_rendering_escapes_defaults_urls_and_dates(client):
    wid, headers = _setup(client)
    url = f"{API}/workspaces/{wid}/email/templates/render"
    template = (
        "Hi {{ contact.first_name }}, "
        "link={{ contact.link|urlencode }} "
        "when={{ contact.when|date:%Y-%m-%d }} "
        "note={{ contact.note }}"
    )
    response = client.post(
        url, headers=headers,
        json={
            "template": template,
            "values": {
                "contact": {
                    "first_name": "",
                    "link": "a b&c",
                    "when": "2026-11-23T10:30:00Z",
                    "note": "<script>alert(1)</script>",
                }
            },
            "defaults": {"contact": {"first_name": "Guest"}},
        },
    )
    assert response.status_code == 200, response.text
    rendered = response.json()["rendered"]
    assert "Hi Guest" in rendered
    assert "link=a%20b%26c" in rendered
    assert "when=2026-11-23" in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "<script>" not in rendered
    assert response.json()["local_only"] is True

    nested = client.post(
        url, headers=headers,
        json={"template": "{{ contact.raw }}", "values": {"contact": {"raw": "{{ contact.note }}"}}},
    )
    assert nested.status_code == 200, nested.text
    assert nested.json()["rendered"] == "{{ contact.note }}"
    assert client.post(
        url, headers=headers,
        json={"template": "{{ contact.link|execute }}", "values": {}},
    ).status_code == 422
    assert email_mod.TOKENS_RENDERED in _event_types(client, wid, headers)


# ---------------------------------------------------------------------------
# MT-030 — forms
# ---------------------------------------------------------------------------


def test_mt030_forms_create_or_update_contacts_and_trigger_actions(client, db_session):
    wid, headers = _setup(client)
    campaign = _campaign(client, wid, headers, "Form nurture")
    base = f"{API}/workspaces/{wid}/campaigns/forms"

    bad_form = client.post(
        base, headers=headers,
        json={"name": "Bad", "slug": "bad", "fields": [{"key": "name", "type": "text"}]},
    )
    assert bad_form.status_code == 422, bad_form.text
    form = client.post(
        base, headers=headers,
        json={
            "name": "Signup", "slug": "signup",
            "fields": [
                {"key": "email", "type": "email", "required": True},
                {"key": "name", "type": "text", "required": True},
                {"key": "phone", "type": "text"},
            ],
            "actions": [
                {"type": "tag", "value": "vip"},
                {"type": "lifecycle", "value": "qualified"},
                {"type": "campaign_enroll", "value": campaign["id"]},
            ],
        },
    )
    assert form.status_code == 201, form.text
    form_id = form.json()["id"]

    token = client.get(f"{base}/{form_id}/token", headers=headers).json()["token"]
    submit_url = f"{base}/{form_id}/submit"
    assert client.post(
        submit_url, json={"answers": {"email": "not-an-email", "name": "Ann"}},
        headers={"X-Form-Token": token},
    ).status_code == 422
    assert client.post(
        submit_url, json={"answers": {"email": "ann@example.com", "name": "Ann"}}
    ).status_code == 401

    first = client.post(
        submit_url, headers={"X-Form-Token": token},
        json={"answers": {"email": "ann@example.com", "name": "Ann", "phone": "555-2000"}},
    )
    assert first.status_code == 201, first.text
    result = first.json()
    assert result["contact_created"] is True
    assert result["actions_applied"] == [
        "tag:vip", "lifecycle:qualified", f"campaign_enroll:{campaign['id']}",
    ]
    contact = db_session.get(Contact, result["contact_id"])
    assert contact.tags == ["vip"]
    assert contact.lifecycle_stage == "qualified"
    assert contact.source == "form:signup"
    assert contact.custom_fields["email"] == "ann@example.com"
    enrollments = db_session.execute(
        select(marketing.CampaignEnrollment).where(
            marketing.CampaignEnrollment.contact_id == contact.id
        )
    ).scalars().all()
    assert len(enrollments) == 1

    second = client.post(
        submit_url, headers={"X-Form-Token": token},
        json={"answers": {"email": "ann@example.com", "name": "Anne"}},
    )
    assert second.status_code == 201, second.text
    assert second.json()["contact_id"] == contact.id
    assert second.json()["contact_created"] is False
    assert len(db_session.execute(
        select(Contact).where(Contact.workspace_id == wid, Contact.email == "ann@example.com")
    ).scalars().all()) == 1

    submissions = client.get(f"{base}/{form_id}/submissions", headers=headers)
    assert submissions.status_code == 200, submissions.text
    assert len(submissions.json()) == 2
    assert {marketing.FORM_SUBMITTED, marketing.CAMPAIGN_ENTERED} <= _event_types(client, wid, headers)


# ---------------------------------------------------------------------------
# MT-033 — configurable scoring
# ---------------------------------------------------------------------------


def test_mt033_scoring_rules_apply_with_history(client, db_session):
    wid, headers = _setup(client)
    crm_base = f"{API}/workspaces/{wid}/crm"
    contact = _contact(
        db_session, wid, "score@example.com", company_name="Score Co",
        tags=["vip"], custom_fields={"plan": "pro"},
    )
    lead = _lead(db_session, wid, contact)

    rules = (
        {"name": "has-company", "field": "company_present", "operator": "present", "points": 10},
        {"name": "vip-tag", "field": "tag", "operator": "equals", "value": "vip", "points": 15},
        {"name": "pro-plan", "field": "custom_field", "operator": "equals", "value": "plan=pro", "points": 5},
    )
    for body in rules:
        response = client.post(f"{crm_base}/scoring-rules", headers=headers, json=body)
        assert response.status_code == 201, response.text
    assert client.post(
        f"{crm_base}/scoring-rules", headers=headers,
        json={"name": "bad", "field": "unknown", "operator": "present", "points": 1},
    ).status_code == 422
    assert client.post(
        f"{crm_base}/scoring-rules", headers=headers,
        json={"name": "zero", "field": "email_present", "operator": "present", "points": 0},
    ).status_code == 422

    applied = client.post(
        f"{crm_base}/scoring/apply", headers=headers, json={"contact_id": contact.id}
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["score_before"] == 0
    assert body["score"] == 30
    assert {row["name"] for row in body["matched"]} == {"has-company", "vip-tag", "pro-plan"}
    db_session.refresh(lead)
    assert lead.score == 30

    history = client.get(
        f"{crm_base}/scoring/history", headers=headers, params={"contact_id": contact.id}
    )
    assert history.status_code == 200, history.text
    assert [row["score_after"] for row in history.json()] == [10, 25, 30]
    assert all(row["actor_id"] for row in history.json())

    listed = client.get(f"{crm_base}/scoring-rules", headers=headers)
    rule_id = next(row["id"] for row in listed.json() if row["name"] == "vip-tag")
    patched = client.patch(
        f"{crm_base}/scoring-rules/{rule_id}", headers=headers, json={"points": 20}
    )
    assert patched.status_code == 200, patched.text
    assert {
        crm.SCORING_RULE_CREATED, crm.SCORING_RULE_UPDATED, crm.LEAD_SCORED
    } <= _event_types(client, wid, headers)


# ---------------------------------------------------------------------------
# MT-035 — lifecycle stages
# ---------------------------------------------------------------------------


def test_mt035_stage_definitions_guard_transitions_and_record_history(client, db_session):
    wid, headers = _setup(client)
    crm_base = f"{API}/workspaces/{wid}/crm"
    contact = _contact(db_session, wid, "stage@example.com", lifecycle_stage="lead")

    defined = client.post(
        f"{crm_base}/stages", headers=headers,
        json={"stages": [
            {"key": "lead", "label": "Lead", "position": 0, "allowed_next": ["qualified"]},
            {"key": "qualified", "label": "Qualified", "position": 1, "allowed_next": ["won"]},
            {"key": "won", "label": "Won", "position": 2, "allowed_next": []},
        ]},
    )
    assert defined.status_code == 200, defined.text
    assert client.post(
        f"{crm_base}/stages", headers=headers,
        json={"stages": [{"key": "Bad Key", "label": "Bad"}]},
    ).status_code == 422
    assert client.post(
        f"{crm_base}/stages/transition", headers=headers,
        json={"contact_id": contact.id, "to_stage": "won", "reason": "skip"},
    ).status_code == 409

    first = client.post(
        f"{crm_base}/stages/transition", headers=headers,
        json={"contact_id": contact.id, "to_stage": "qualified", "reason": "called"},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"{crm_base}/stages/transition", headers=headers,
        json={"contact_id": contact.id, "to_stage": "won", "reason": "signed"},
    )
    assert second.status_code == 200, second.text
    db_session.refresh(contact)
    assert contact.lifecycle_stage == "won"

    history = client.get(
        f"{crm_base}/stages/history", headers=headers, params={"contact_id": contact.id}
    )
    assert history.status_code == 200, history.text
    assert [(row["from"], row["to"]) for row in history.json()] == [
        ("lead", "qualified"), ("qualified", "won"),
    ]
    assert {crm.STAGE_DEFINED, crm.LIFECYCLE_CHANGED, crm.STAGE_TRANSITION_RECORDED} <= _event_types(
        client, wid, headers
    )


# ---------------------------------------------------------------------------
# MT-042 — SMS STOP and DNC
# ---------------------------------------------------------------------------


def test_mt042_sms_stop_reply_blocks_local_sms_delivery(client, db_session):
    wid, headers = _setup(client)
    email_base = f"{API}/workspaces/{wid}/email"
    contact = _contact(db_session, wid, "sms@example.com", phone="555-3000")

    assert email_mod.is_stop_reply("STOP") is True
    assert email_mod.is_stop_reply("Please STOP all") is True
    assert email_mod.is_stop_reply("stopped") is False

    reply = client.post(
        f"{email_base}/sms/reply", headers=headers,
        json={"contact_id": contact.id, "message": "Please STOP all"},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json() == {
        "stop_detected": True, "sms_do_not_contact": True, "contact_id": contact.id,
    }
    dnc = client.get(
        f"{email_base}/sms/dnc", headers=headers, params={"contact_id": contact.id}
    )
    assert dnc.status_code == 200, dnc.text
    assert len(dnc.json()) == 1

    blocked = client.post(
        f"{email_base}/sms/deliver-local", headers=headers,
        json={"contact_id": contact.id, "message": "Offer"},
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["status"] == "blocked"
    assert blocked.json()["reason"] == "sms_dnc"
    assert db_session.execute(
        select(email_mod.LocalDelivery.id).where(
            email_mod.LocalDelivery.workspace_id == wid,
            email_mod.LocalDelivery.contact_id == contact.id,
        )
    ).scalars().all() == []
    assert {
        email_mod.SMS_REPLY_RECORDED, email_mod.SMS_DNC_RECORDED, email_mod.SMS_DELIVERY_BLOCKED
    } <= _event_types(client, wid, headers)


# ---------------------------------------------------------------------------
# MT-045 — preferred-channel messages
# ---------------------------------------------------------------------------


def test_mt045_marketing_messages_resolve_preferred_channel_and_send_once(client, db_session):
    wid, headers = _setup(client)
    email_base = f"{API}/workspaces/{wid}/email"
    default_contact = _contact(db_session, wid, "default-channel@example.com")
    sms_contact = _contact(db_session, wid, "sms-channel@example.com", phone="555-4000")

    preference = client.post(
        f"{email_base}/channel-preferences", headers=headers,
        json={"contact_id": sms_contact.id, "channel": "sms"},
    )
    assert preference.status_code == 200, preference.text
    resolved = client.get(
        f"{email_base}/channel-preferences", headers=headers,
        params={"contact_id": sms_contact.id},
    )
    assert resolved.json()["channel"] == "sms"

    first = client.post(
        f"{email_base}/marketing-message/deliver-local", headers=headers,
        json={"contact_id": default_contact.id, "message_key": "welcome", "body": "Hello"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["channel"] == "email"
    assert first.json()["status"] == "queued_local"
    assert first.json()["local_only"] is True

    second = client.post(
        f"{email_base}/marketing-message/deliver-local", headers=headers,
        json={"contact_id": sms_contact.id, "message_key": "welcome", "body": "Hello"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["channel"] == "sms"
    assert second.json()["status"] == "queued_local"

    deliveries = client.get(
        f"{email_base}/marketing-message/deliveries", headers=headers,
        params={"contact_id": sms_contact.id},
    )
    assert len(deliveries.json()) == 1
    assert deliveries.json()[0]["channel"] == "sms"
    assert {
        email_mod.CHANNEL_PREFERENCE_UPDATED, email_mod.MESSAGE_DELIVERED
    } <= _event_types(client, wid, headers)


# ---------------------------------------------------------------------------
# MT-046 — frequency caps and pause
# ---------------------------------------------------------------------------


def test_mt046_channel_frequency_caps_and_pause_are_enforced(client, db_session):
    wid, headers = _setup(client)
    email_base = f"{API}/workspaces/{wid}/email"
    contact = _contact(db_session, wid, "frequency@example.com")
    url = f"{email_base}/marketing-message/deliver-local"

    rule = client.put(
        f"{email_base}/channel-rules", headers=headers,
        json={"contact_id": contact.id, "channel": "email", "max_per_day": 1, "paused": False},
    )
    assert rule.status_code == 200, rule.text
    first = client.post(
        url, headers=headers,
        json={"contact_id": contact.id, "message_key": "notice", "body": "One"},
    )
    assert first.status_code == 200, first.text
    capped = client.post(
        url, headers=headers,
        json={"contact_id": contact.id, "message_key": "notice", "body": "Two"},
    )
    assert capped.status_code == 409, capped.text
    assert "frequency cap" in capped.json()["detail"]

    paused = client.put(
        f"{email_base}/channel-rules", headers=headers,
        json={"contact_id": contact.id, "channel": "email", "max_per_day": 5, "paused": True},
    )
    assert paused.status_code == 200, paused.text
    blocked = client.post(
        url, headers=headers,
        json={"contact_id": contact.id, "message_key": "notice", "body": "Three"},
    )
    assert blocked.status_code == 409, blocked.text
    assert "paused" in blocked.json()["detail"]

    current = client.get(
        f"{email_base}/channel-rules", headers=headers,
        params={"contact_id": contact.id, "channel": "email"},
    )
    assert current.json()["max_per_day"] == 5
    assert current.json()["paused"] is True
    assert email_mod.MESSAGE_BLOCKED in _event_types(client, wid, headers)


# ---------------------------------------------------------------------------
# MT-047 — configurable reports
# ---------------------------------------------------------------------------


def test_mt047_configurable_marketing_reports_run_from_local_data(client, db_session):
    wid, headers = _setup(client)
    campaigns = f"{API}/workspaces/{wid}/campaigns"
    campaign = _campaign(client, wid, headers, "Report campaign")
    metric = client.put(
        f"{campaigns}/{campaign['id']}/metrics", headers=headers,
        json={"date": "2026-11-01", "impressions": 100, "clicks": 20, "leads": 4, "spend": 12.50},
    )
    assert metric.status_code == 200, metric.text

    bad = client.post(
        f"{campaigns}/reports", headers=headers,
        json={"name": "Bad", "entity": "campaign_metrics", "metrics": ["password"]},
    )
    assert bad.status_code == 422, bad.text
    report = client.post(
        f"{campaigns}/reports", headers=headers,
        json={
            "name": "Campaign spend",
            "entity": "campaign_metrics",
            "metrics": ["impressions", "clicks", "spend"],
            "filters": {"campaign_id": campaign["id"]},
        },
    )
    assert report.status_code == 201, report.text
    report_id = report.json()["id"]

    listed = client.get(f"{campaigns}/reports/list", headers=headers)
    assert [row["id"] for row in listed.json()] == [report_id]
    run = client.get(f"{campaigns}/reports/{report_id}/run", headers=headers)
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["report_id"] == report_id
    assert len(body["rows"]) == 1
    assert body["rows"][0]["impressions"] == 100
    assert body["totals"]["clicks"] == 20
    assert body["totals"]["spend"] == pytest.approx(12.5)
    assert marketing.MARKETING_REPORT_CREATED in _event_types(client, wid, headers)


# ---------------------------------------------------------------------------
# MT-050 — signed webhooks with real retries and logs
# ---------------------------------------------------------------------------


def test_mt050_webhooks_are_signed_retried_and_logged(client, db_session):
    wid, headers = _setup(client)
    email_base = f"{API}/workspaces/{wid}/email"
    received: list[dict] = []
    attempts: dict[str, int] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            delivery_id = self.headers.get("X-NOVARA-Delivery", "")
            attempts[delivery_id] = attempts.get(delivery_id, 0) + 1
            received.append({
                "path": self.path,
                "event": self.headers.get("X-NOVARA-Event"),
                "delivery_id": delivery_id,
                "signature": self.headers.get("X-NOVARA-Signature"),
                "body": body,
            })
            if self.path.startswith("/always-fail") or attempts[delivery_id] < 2:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"retry")
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        secret = "a-long-webhook-signing-secret"
        created = client.post(
            f"{email_base}/webhooks", headers=headers,
            json={
                "name": "local-hook", "url": f"http://127.0.0.1:{port}/hook",
                "secret": secret, "event_types": [email_mod.BROADCAST_SENT],
            },
        )
        assert created.status_code == 201, created.text
        assert "secret" not in created.json()
        subscription_id = created.json()["id"]

        assert client.post(
            f"{email_base}/webhooks", headers=headers,
            json={
                "name": "unsubscribed", "url": f"http://127.0.0.1:{port}/hook",
                "secret": secret, "event_types": [email_mod.SMS_DNC_RECORDED],
            },
        ).status_code == 201

        result = email_mod.deliver_webhook(
            db_session, workspace_id=wid, subscription_id=subscription_id,
            event_type=email_mod.BROADCAST_SENT, payload={"hello": "world"},
        )
        assert result["status"] == "delivered", result
        assert result["attempts"] == 2
        delivery_id = result["delivery_id"]
        assert len(received) == 2
        assert all(row["delivery_id"] == delivery_id for row in received)
        assert all(row["event"] == email_mod.BROADCAST_SENT for row in received)
        expected_signature = email_mod.webhook_signature(secret, delivery_id, received[0]["body"])
        assert all(row["signature"] == expected_signature for row in received)

        failed_sub = client.post(
            f"{email_base}/webhooks", headers=headers,
            json={
                "name": "always-fails", "url": f"http://127.0.0.1:{port}/always-fail",
                "secret": secret, "event_types": [email_mod.BROADCAST_SENT],
            },
        ).json()["id"]
        failed = email_mod.deliver_webhook(
            db_session, workspace_id=wid, subscription_id=failed_sub,
            event_type=email_mod.BROADCAST_SENT, payload={"x": 1}, max_attempts=2,
        )
        assert failed["status"] == "failed"
        assert failed["attempts"] == 2
        assert failed["status_code"] == 500

        logs = client.get(f"{email_base}/webhooks/{subscription_id}/deliveries", headers=headers)
        assert logs.status_code == 200, logs.text
        rows = logs.json()
        assert [row["attempt"] for row in rows] == [1, 2]
        assert [row["status"] for row in rows] == ["failed", "delivered"]
        assert rows[0]["status_code"] == 500
        assert rows[1]["status_code"] == 200
        assert rows[0]["signature_prefix"] == expected_signature[:16]
        assert {email_mod.WEBHOOK_DELIVERED, email_mod.WEBHOOK_DELIVERY_FAILED} <= _event_types(
            client, wid, headers
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# MT-069 — scheduled jobs
# ---------------------------------------------------------------------------


def test_mt069_scheduled_jobs_run_and_leave_observable_runs(client, db_session):
    wid, headers = _setup(client)
    base = f"{API}/workspaces/{wid}/campaigns"
    campaign = _campaign(client, wid, headers, "Metrics job")
    db_session.add(marketing.CampaignMetric(
        id=new_id(), workspace_id=wid, campaign_id=campaign["id"],
        date=marketing.date(2026, 11, 1), impressions=50, clicks=5, leads=1,
        created_at=now(),
    ))
    db_session.commit()

    assert client.post(
        f"{base}/jobs", headers=headers,
        json={"name": "bad", "job_type": "unknown"},
    ).status_code == 422
    job = client.post(
        f"{base}/jobs", headers=headers,
        json={"name": "nightly-rollup", "job_type": "metrics_rollup", "interval_minutes": 60},
    )
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]

    disabled = client.post(
        f"{base}/jobs", headers=headers,
        json={"name": "paused", "job_type": "metrics_rollup", "enabled": False},
    )
    assert disabled.status_code == 201, disabled.text
    assert client.post(
        f"{base}/jobs/{disabled.json()['id']}/run", headers=headers
    ).status_code == 409

    run = client.post(f"{base}/jobs/{job_id}/run", headers=headers)
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["status"] == "completed"
    assert body["details"]["metric_days"] == 1
    assert body["details"]["impressions"] == 50

    runs = client.get(f"{base}/jobs/{job_id}/runs", headers=headers)
    assert runs.status_code == 200, runs.text
    assert [row["status"] for row in runs.json()] == ["completed"]
    jobs = client.get(f"{base}/jobs/list", headers=headers)
    assert jobs.status_code == 200, jobs.text
    assert next(row for row in jobs.json() if row["id"] == job_id)["last_run_at"] is not None
    assert marketing.MARKETING_JOB_COMPLETED in _event_types(client, wid, headers)


# ---------------------------------------------------------------------------
# MT-070 — event catalogue and extension points
# ---------------------------------------------------------------------------


def test_mt070_marketing_event_catalogue_registers_extension_events(client):
    catalogue = {
        marketing.FORM_SUBMITTED, marketing.CAMPAIGN_ENTERED, marketing.EMAIL_SENT,
        marketing.EMAIL_OPENED, marketing.EMAIL_CLICKED, marketing.CAMPAIGN_EXITED,
        crm.CONTACT_PROFILE_UPDATED, crm.SCORING_RULE_CREATED, crm.STAGE_DEFINED,
        crm.CONTACT_ANONYMIZED, email_mod.TOKENS_RENDERED, email_mod.MESSAGE_DELIVERED,
        email_mod.SMS_DNC_RECORDED, email_mod.WEBHOOK_DELIVERED,
    }
    assert catalogue <= EVENT_TYPES
    assert all(isinstance(name, str) and name for name in catalogue)
    assert "handle(event_type, context)" in marketing.MARKETING_EXTENSION_CONTRACT
    assert callable(marketing.register_marketing_extension)


# ---------------------------------------------------------------------------
# MT-107 — legal review scope record
# ---------------------------------------------------------------------------


def test_mt107_derivative_distribution_is_explicitly_out_of_scope(client):
    status = marketing.DERIVATIVE_DISTRIBUTION_STATUS
    assert status["status"] == "out_of_scope"
    assert "clean-room" in status["scope"]
    assert "no Mautic source" in status["scope"]
    assert "derivative distribution is ever proposed" in status["review"]

    for module in (marketing, crm, email_mod):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "import mautic" not in source
        assert "from mautic" not in source


# ---------------------------------------------------------------------------
# MT-114 — legacy scope translation
# ---------------------------------------------------------------------------


def test_mt114_legacy_scope_translation_maps_to_existing_rbac(client):
    translated = marketing.translate_legacy_scopes(
        ["lead:view", "lead:edit", "lead:view", "report:view"]
    )
    assert translated == (CONTACT_READ, CONTACT_WRITE, EVENT_READ)
    assert set(marketing.LEGACY_SCOPE_TO_PERMISSION.values()) <= {
        permission for permissions in ROLE_PERMISSIONS.values() for permission in permissions
    } | {ALL}
    assert all(has_permission("admin", value) for value in marketing.LEGACY_SCOPE_TO_PERMISSION.values())
    with pytest.raises(ValueError):
        marketing.translate_legacy_scopes(["unknown:scope"])
    with pytest.raises(ValueError):
        marketing.translate_legacy_scopes("lead:view")
    assert marketing.role_satisfies_legacy_scopes(
        "owner", ["lead:view", "campaign:edit", "settings:manage"]
    ) is True
    assert marketing.role_satisfies_legacy_scopes("read_only", ["lead:view"]) is True
    assert marketing.role_satisfies_legacy_scopes("read_only", ["lead:edit"]) is False


# ---------------------------------------------------------------------------
# MT-117 — funnel, engagement and attribution from local events
# ---------------------------------------------------------------------------


def test_mt117_funnel_engagement_and_attribution_use_local_events(client, db_session):
    wid, headers = _setup(client)
    base = f"{API}/workspaces/{wid}/campaigns"
    campaign = _campaign(client, wid, headers, "Analytics campaign")
    contact = _contact(db_session, wid, "funnel@example.com")

    _publish(
        db_session, wid, marketing.FORM_SUBMITTED,
        entity_id=contact.id,
        payload={"contact_id": contact.id, "source": "newsletter"},
    )
    step = client.post(
        f"{base}/{campaign['id']}/journey-steps", headers=headers,
        json={"position": 1, "channel": "email", "action": marketing.EMAIL_SENT, "label": "Send"},
    )
    assert step.status_code == 201, step.text
    enrolled = client.post(
        f"{base}/{campaign['id']}/enrollments", headers=headers,
        json={"contact_id": contact.id},
    )
    assert enrolled.status_code == 201, enrolled.text
    run = client.post(f"{base}/{campaign['id']}/run", headers=headers)
    assert run.status_code == 200, run.text
    for kind in ("opened", "clicked"):
        response = client.post(
            f"{base}/{campaign['id']}/engagement", headers=headers,
            json={"contact_id": contact.id, "kind": kind},
        )
        assert response.status_code == 201, response.text

    funnel = client.get(
        f"{base}/analytics/funnel", headers=headers,
        params={"campaign_id": campaign["id"]},
    )
    assert funnel.status_code == 200, funnel.text
    funnel_body = funnel.json()
    assert funnel_body["source"] == "local_events"
    assert all(funnel_body["stages"][stage] == 1 for stage in marketing.FUNNEL_STAGES)
    assert funnel_body["entry_to_sent_rate"] == 1.0
    assert funnel_body["sent_to_opened_rate"] == 1.0
    assert funnel_body["opened_to_clicked_rate"] == 1.0

    engagement = client.get(
        f"{base}/analytics/engagement", headers=headers,
        params={"campaign_id": campaign["id"]},
    )
    assert engagement.status_code == 200, engagement.text
    rows = engagement.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["campaign_id"] == campaign["id"]
    assert (rows[0]["sent"], rows[0]["opened"], rows[0]["clicked"]) == (1, 1, 1)
    assert rows[0]["open_rate"] == 1.0
    assert rows[0]["click_rate"] == 1.0

    attribution = client.get(f"{base}/analytics/attribution", headers=headers)
    assert attribution.status_code == 200, attribution.text
    assert attribution.json()["rows"] == [{
        "source": "newsletter", "submissions": 1, "contacts": 1,
        "entered": 1, "clicked": 1,
    }]


# ---------------------------------------------------------------------------
# MT-122 — anonymization preserving audit history
# ---------------------------------------------------------------------------


def test_mt122_contact_anonymization_preserves_audit_trail(client, db_session):
    wid, headers = _setup(client)
    crm_base = f"{API}/workspaces/{wid}/crm"
    contact = _contact(
        db_session, wid, "privacy@example.com", full_name="Privacy Person",
        phone="555-9000", company_name="Private Co", tags=["vip"],
        custom_fields={"plan": "pro"}, lifecycle_stage="lead",
    )
    _publish(
        db_session, wid, crm.CONTACT_PROFILE_UPDATED,
        entity_id=contact.id, payload={"fields": ["phone"]}, actor_id="seed-actor",
    )

    assert client.post(
        f"{crm_base}/contacts/{contact.id}/anonymize", headers=headers, json={"reason": "x"}
    ).status_code == 422
    response = client.post(
        f"{crm_base}/contacts/{contact.id}/anonymize", headers=headers,
        json={"reason": "GDPR erasure request"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["anonymized"] is True
    assert body["events_preserved"] >= 1
    assert "email" in body["fields_masked"]

    profile = client.get(f"{crm_base}/contact-profiles/{contact.id}", headers=headers)
    assert profile.status_code == 200, profile.text
    profile_body = profile.json()
    assert profile_body["email"] == f"anon+{contact.id}@invalid.local"
    assert profile_body["full_name"] == "Anonymized contact"
    assert profile_body["phone"] is None
    assert profile_body["company_name"] is None
    assert profile_body["custom_fields"] == {}
    assert profile_body["tags"] == []
    assert profile_body["archived"] is True

    record = client.get(f"{crm_base}/contacts/{contact.id}/anonymization", headers=headers)
    assert record.status_code == 200, record.text
    assert record.json()["reason"] == "GDPR erasure request"
    assert record.json()["actor_id"]

    emitted = _event_types(client, wid, headers)
    assert crm.CONTACT_ANONYMIZED in emitted
    assert crm.CONTACT_PROFILE_UPDATED in emitted
    assert client.post(
        f"{crm_base}/contacts/{contact.id}/anonymize", headers=headers,
        json={"reason": "repeat request"},
    ).status_code == 409
