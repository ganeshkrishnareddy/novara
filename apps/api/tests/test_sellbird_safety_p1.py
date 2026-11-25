"""Named local acceptance tests for the remaining Sellbird P1 safety rows.

Every test drives the real FastAPI application (``client``) against the shared
test database. Local mocks and helper functions are only used for setup; none is
presented as a delivery. The tests prove review-only behaviour, human gates,
workspace scoping and that no role or route can send in this build.
"""

from __future__ import annotations

import socket
from datetime import timedelta

import pytest
from sqlalchemy import select

from novara_core.main import app
from novara_core.models import (
    Company,
    Contact,
    Event,
    OutreachDraft,
    SuppressionEntry,
    User,
    WorkspaceMember,
    in_hours,
    new_id,
    now,
)
from novara_core.modules.adapters import AdapterCall
from novara_core.modules.agents import (
    AGENT_CREATED,
    AGENT_NOTES,
    AGENT_ROLE_DESCRIPTORS,
    AGENT_RUN_APPROVED,
    AGENT_RUN_REQUESTED,
    AGENT_STATUS_CHANGED,
    AgentConfig,
    AgentRun,
)
from novara_core.modules.outreach_safety import (
    DEFAULT_COMPLIANCE_FOOTER,
    FOOTER_UPDATED,
    GATE_REJECTED,
    OPTOUT_RECORDED,
    SUPPRESSION_ADDED,
)
from novara_core.permissions import ROLE_PERMISSIONS
from novara_core.security import create_session, hash_password

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}"
DRAFTS = BASE + "/outreach-drafts"
SAFETY = BASE + "/outreach-safety"
AGENTS = BASE + "/agents"
INTEGRATIONS = BASE + "/integrations"
ADAPTERS = BASE + "/adapters"


def _role_headers(db_session, workspace_id: str, role: str, email: str):
    """Local setup only: an active member with a real server-side session."""
    user = User(
        id=new_id(),
        email=email,
        display_name="P1 Test Member",
        password_hash=hash_password("Password123!"),
        created_at=now(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        WorkspaceMember(
            id=new_id(),
            workspace_id=workspace_id,
            user_id=user.id,
            role=role,
            status="active",
            created_at=now(),
        )
    )
    db_session.flush()
    _, access, _ = create_session(db_session, user_id=user.id, workspace_id=workspace_id)
    db_session.commit()
    return auth(access)


def _intake(client, wid: str, headers, email: str, full_name: str, company: str | None = None):
    payload = {
        "submission_id": f"sellbird-p1-{new_id()}",
        "email": email,
        "full_name": full_name,
    }
    if company:
        payload["company"] = company
    response = client.post(BASE.format(wid=wid) + "/intake/website-form", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _events_of_type(db_session, wid: str, event_type: str) -> list[Event]:
    return list(
        db_session.execute(
            select(Event).where(
                Event.workspace_id == wid, Event.event_type == event_type
            ).order_by(Event.seq)
        ).scalars().all()
    )


def _no_network(monkeypatch) -> None:
    """Any accidental outbound connection fails the test loudly."""
    def blocked(*args, **kwargs):
        raise AssertionError("an outbound network connection was attempted")

    monkeypatch.setattr(socket.socket, "connect", blocked)


def test_sb018_personalised_draft_uses_workspace_rows_rejects_unresolved_and_stays_draft(
    client, db_session, monkeypatch
):
    _no_network(monkeypatch)
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = DRAFTS.format(wid=wid)

    intake = _intake(client, wid, headers, "ada@example.test", "Ada Lovelace", "Northwind")
    contact_id = intake["contact_id"]
    before = len(db_session.execute(select(OutreachDraft)).scalars().all())

    # A company row in the same workspace is the source of company variables.
    company = Company(
        id=new_id(), workspace_id=wid, name="Northwind", industry="Robotics",
        location="London", created_at=now(), updated_at=now(),
    )
    db_session.add(company)
    db_session.flush()
    contact = db_session.get(Contact, contact_id)
    contact.company_id = company.id
    db_session.commit()

    created = client.post(
        base,
        headers=headers,
        json={
            "contact_id": contact_id,
            "subject_template": "Hello {{first_name}} at {{company_name}}",
            "body_template": (
                "Hi {{full_name}}, we saw {{company_name}} works in {{company_industry}}."
            ),
        },
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["status"] == "draft"
    assert draft["approved_at"] is None and draft["approved_by"] is None
    assert draft["subject"] == "Hello Ada at Northwind"
    assert "Ada Lovelace" in draft["body"] and "Robotics" in draft["body"]
    assert "{{" not in draft["subject"] and "{{" not in draft["body"]
    assert DEFAULT_COMPLIANCE_FOOTER in draft["body"]

    # Unknown variables are rejected before a draft row is written.
    unknown = client.post(
        base,
        headers=headers,
        json={
            "contact_id": contact_id,
            "subject_template": "Hello {{first_name}}",
            "body_template": "Birthday: {{birthday}}",
        },
    )
    assert unknown.status_code == 422, unknown.text
    assert "birthday" in str(unknown.json()["detail"])

    # Known variables with no value in a workspace row fail closed as well.
    second = _intake(client, wid, headers, "no-company@example.test", "Grace Hopper")
    missing = client.post(
        base,
        headers=headers,
        json={
            "contact_id": second["contact_id"],
            "subject_template": "Hello {{full_name}}",
            "body_template": "At {{company_name}}, we can help.",
        },
    )
    assert missing.status_code == 422, missing.text
    assert "company_name" in str(missing.json()["detail"])
    # The second intake created its own draft; neither rejected template did.
    assert len(db_session.execute(select(OutreachDraft)).scalars().all()) == before + 2


def test_sb021_outbox_listing_is_workspace_scoped_filtered_ordered_and_review_only(
    client, db_session, monkeypatch
):
    _no_network(monkeypatch)
    first = bootstrap(client)
    wid, headers = first["workspace_id"], auth(first["access_token"])
    list_url = DRAFTS.format(wid=wid)

    first_intake = _intake(client, wid, headers, "queue1@example.test", "Queue One")
    second_intake = _intake(client, wid, headers, "queue2@example.test", "Queue Two")
    approved = client.post(
        f"{list_url}/{first_intake['draft_id']}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text

    expected_queue = list(
        db_session.execute(
            select(OutreachDraft.id)
            .where(OutreachDraft.workspace_id == wid)
            .order_by(OutreachDraft.created_at, OutreachDraft.id)
        ).scalars().all()
    )
    assert [item["id"] for item in client.get(list_url, headers=headers).json()] == expected_queue
    pending = client.get(list_url, params={"status": "pending"}, headers=headers).json()
    assert [item["id"] for item in pending] == [second_intake["draft_id"]]
    approved_only = client.get(list_url, params={"status": "approved"}, headers=headers).json()
    assert [item["id"] for item in approved_only] == [first_intake["draft_id"]]
    assert client.get(list_url, params={"status": "sent"}, headers=headers).status_code == 422

    second = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Other workspace"}
    )
    assert second.status_code == 200, second.text
    other_wid, other_headers = second.json()["workspace_id"], auth(second.json()["access_token"])
    other_intake = _intake(client, other_wid, other_headers, "queue3@example.test", "Queue Three")

    assert client.get(list_url, headers=other_headers).status_code == 403
    other_list = client.get(DRAFTS.format(wid=other_wid), headers=other_headers).json()
    assert [item["id"] for item in other_list] == [other_intake["draft_id"]]
    assert other_intake["draft_id"] not in expected_queue

    # Listing is review-only: no adapter call, no event and no network traffic.
    calls_before = len(db_session.execute(select(AdapterCall)).scalars().all())
    events_before = len(db_session.execute(select(Event)).scalars().all())
    for _ in range(3):
        assert client.get(list_url, headers=headers).status_code == 200
    assert len(db_session.execute(select(AdapterCall)).scalars().all()) == calls_before
    assert len(db_session.execute(select(Event)).scalars().all()) == events_before


def test_sb024_presend_gate_blocks_failed_conditions_and_passing_never_sends(
    client, db_session, monkeypatch
):
    _no_network(monkeypatch)
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    url = DRAFTS.format(wid=wid)
    check_url = SAFETY.format(wid=wid) + "/drafts/{draft_id}/gate-check"
    intake = _intake(client, wid, headers, "gate@example.test", "Gate Tester")
    draft_id = intake["draft_id"]

    unapproved = client.post(check_url.format(draft_id=draft_id), headers=headers)
    assert unapproved.status_code == 200, unapproved.text
    assert unapproved.json()["allowed"] is False
    assert "not approved" in " ".join(unapproved.json()["failures"])

    approved = client.post(f"{url}/{draft_id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    passed = client.post(check_url.format(draft_id=draft_id), headers=headers).json()
    assert passed["allowed"] is True and passed["failures"] == []
    assert passed["delivery"] == "blocked_no_delivery_adapter"

    # Passing the gate still does not deliver anything.
    assert db_session.execute(select(AdapterCall)).scalars().all() == []
    assert db_session.get(OutreachDraft, draft_id).status == "approved"

    contact_id = intake["contact_id"]
    blank = OutreachDraft(
        id=new_id(), workspace_id=wid, contact_id=contact_id,
        subject="  ", body=DEFAULT_COMPLIANCE_FOOTER, status="draft", created_at=now(),
    )
    no_footer = OutreachDraft(
        id=new_id(), workspace_id=wid, contact_id=contact_id,
        subject="Complete enough", body="No policy footer here", status="draft", created_at=now(),
    )
    db_session.add_all([blank, no_footer])
    db_session.commit()

    for row, expected_failure in (
        (blank, "subject is required"),
        (no_footer, "compliance footer is missing"),
    ):
        decision = client.post(check_url.format(draft_id=row.id), headers=headers).json()
        assert decision["allowed"] is False
        assert expected_failure in decision["failures"]
        blocked = client.post(f"{url}/{row.id}/approve", headers=headers)
        assert blocked.status_code == 403, blocked.text
        assert db_session.get(OutreachDraft, row.id).status == "draft"

    # Suppression is the third gate condition; a blocked draft cannot advance.
    suppression = client.post(
        SAFETY.format(wid=wid) + "/suppressions",
        headers=headers,
        json={"recipient": "gate@example.test", "scope": "email", "reason": "legal hold"},
    )
    assert suppression.status_code == 201, suppression.text
    suppressed = client.post(check_url.format(draft_id=no_footer.id), headers=headers).json()
    assert suppressed["allowed"] is False
    assert suppressed["suppression_reason"] == "legal hold"


def test_sb030_opt_out_blocks_approval_and_is_audited(client, db_session, monkeypatch):
    _no_network(monkeypatch)
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    intake = _intake(client, wid, headers, "optout@example.test", "Opt Out")
    draft_id = intake["draft_id"]

    recorded = client.post(
        SAFETY.format(wid=wid) + "/opt-outs",
        headers=headers,
        json={"email": "optout@example.test", "reason": "contact asked to stop"},
    )
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["audited"] is True
    assert db_session.get(Contact, intake["contact_id"]).do_not_contact is True
    entry = db_session.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.workspace_id == wid,
            SuppressionEntry.recipient == "optout@example.test",
        )
    ).scalar_one()
    assert entry.reason == "opt_out" and entry.revoked_at is None

    audits = _events_of_type(db_session, wid, OPTOUT_RECORDED)
    assert len(audits) == 1
    assert audits[0].payload["reason"] == "contact asked to stop"
    assert audits[0].payload["recipient"] == "optout@example.test"

    check = client.post(
        SAFETY.format(wid=wid) + f"/drafts/{draft_id}/gate-check", headers=headers
    ).json()
    assert check["allowed"] is False and check["suppression_reason"] == "opt_out"

    denied = client.post(
        DRAFTS.format(wid=wid) + f"/{draft_id}/approve", headers=headers
    )
    assert denied.status_code == 403, denied.text
    assert "opt_out" in str(denied.json()["detail"])
    assert db_session.get(OutreachDraft, draft_id).status == "draft"
    assert _events_of_type(db_session, wid, "outreach.approved") == []

    listed = client.get(SAFETY.format(wid=wid) + "/opt-outs", headers=headers).json()
    assert [row["reason"] for row in listed] == ["opt_out"]


def test_sb031_suppression_list_reason_scope_expiry_blocks_with_recorded_reason(
    client, db_session, monkeypatch
):
    _no_network(monkeypatch)
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    safety = SAFETY.format(wid=wid)
    first = _intake(client, wid, headers, "hold@example.test", "On Hold")
    second = _intake(client, wid, headers, "expired@example.test", "Expired Hold")

    response = client.post(
        safety + "/suppressions",
        headers=headers,
        json={
            "recipient": "hold@example.test",
            "scope": "email",
            "reason": "legal hold",
            "expires_at": in_hours(24).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    entry = response.json()
    assert entry["reason"] == "legal hold" and entry["scope"] == "email"
    assert entry["expires_at"] is not None and entry["active"] is True
    listed = client.get(safety + "/suppressions", headers=headers).json()
    assert [row["reason"] for row in listed] == ["legal hold"]

    added = _events_of_type(db_session, wid, SUPPRESSION_ADDED)
    assert len(added) == 1 and added[0].payload["reason"] == "legal hold"

    check = client.post(safety + f"/drafts/{first['draft_id']}/gate-check", headers=headers).json()
    assert check["allowed"] is False and check["suppression_reason"] == "legal hold"
    denied = client.post(
        DRAFTS.format(wid=wid) + f"/{first['draft_id']}/approve", headers=headers
    )
    assert denied.status_code == 403, denied.text
    rejections = _events_of_type(db_session, wid, GATE_REJECTED)
    assert rejections and "legal hold" in str(rejections[-1].payload["suppression_reason"])
    assert db_session.get(OutreachDraft, first["draft_id"]).status == "draft"

    # An expired entry is visible in the list but no longer blocks a draft.
    db_session.add(
        SuppressionEntry(
            id=new_id(), workspace_id=wid, recipient="expired@example.test",
            scope="email", reason="old hold", expires_at=now() - timedelta(hours=1),
            created_at=now(), created_by="test", revoked_at=None,
        )
    )
    db_session.commit()
    expired_check = client.post(
        safety + f"/drafts/{second['draft_id']}/gate-check", headers=headers
    ).json()
    assert expired_check["allowed"] is False  # not approved yet, but not suppressed
    assert expired_check["suppression_reason"] is None
    approved = client.post(
        DRAFTS.format(wid=wid) + f"/{second['draft_id']}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text

    # Revocation is audited and removes the block.
    revoked = client.post(safety + f"/suppressions/{entry['id']}/revoke", headers=headers)
    assert revoked.status_code == 200 and revoked.json()["active"] is False
    assert _events_of_type(db_session, wid, "outreach.suppression_revoked")
    assert client.post(
        DRAFTS.format(wid=wid) + f"/{first['draft_id']}/approve", headers=headers
    ).status_code == 200


def test_sb038_agent_configs_runs_are_audited_limited_and_human_approved(
    client, db_session, monkeypatch
):
    _no_network(monkeypatch)
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    url = AGENTS.format(wid=wid)
    owner_id = db_session.execute(
        select(User.id).where(User.email == "owner@example.com")
    ).scalar_one()

    payload = {
        "name": "Local writer",
        "purpose": "Draft customer outreach locally",
        "model_provider": "local",
        "model_name": "local-only",
        "boundary": "No network; drafts require human approval",
        "role": "writer",
        "max_steps": 2,
        "requires_approval": True,
    }
    created = client.post(url, headers=headers, json=payload)
    assert created.status_code == 201, created.text
    agent = created.json()
    assert agent["role"] == "writer"
    assert "No external AI provider" in agent["notes"]
    assert "no sender role" in agent["role_notes"].lower()
    assert "output" not in agent  # no fabricated model result

    sender = client.post(url, headers=headers, json={**payload, "name": "Sender", "role": "sender"})
    assert sender.status_code == 422, sender.text

    too_many = client.post(
        url + f"/{agent['id']}/runs",
        headers=headers,
        json={"task": "Draft a note", "steps_taken": 3},
    )
    assert too_many.status_code == 422, too_many.text

    run = client.post(
        url + f"/{agent['id']}/runs",
        headers=headers,
        json={"task": "Draft a note", "steps_taken": 1},
    )
    assert run.status_code == 201, run.text
    run_id = run.json()["id"]
    assert "output" not in run.json()
    assert client.post(
        url + f"/{agent['id']}/runs/{run_id}/progress",
        headers=headers, json={"steps_taken": 3, "status": "running"},
    ).status_code == 422

    waiting = client.post(
        url + f"/{agent['id']}/runs/{run_id}/progress",
        headers=headers, json={"steps_taken": 2, "status": "completed"},
    )
    assert waiting.json()["status"] == "awaiting_approval"

    rep_headers = _role_headers(db_session, wid, "sales_rep", "agent-rep@example.test")
    denied = client.post(url + f"/{agent['id']}/runs/{run_id}/approve", headers=rep_headers)
    assert denied.status_code == 403 and "outreach:approve" in str(denied.json()["detail"])

    completed = client.post(url + f"/{agent['id']}/runs/{run_id}/approve", headers=headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert "output" not in completed.json()
    assert db_session.get(AgentRun, run_id).steps_taken == 2
    assert db_session.get(AgentConfig, agent["id"]).role == "writer"

    types = [event.event_type for event in db_session.execute(
        select(Event).where(Event.workspace_id == wid).order_by(Event.seq)
    ).scalars()]
    for expected in (AGENT_CREATED, AGENT_RUN_REQUESTED, AGENT_STATUS_CHANGED, AGENT_RUN_APPROVED):
        assert expected in types
    approval = _events_of_type(db_session, wid, AGENT_RUN_APPROVED)[0]
    assert approval.payload["approved_by"] == owner_id
    assert approval.payload["actor_id"] == owner_id
    assert all(
        event.payload.get("actor_id") == owner_id
        for event in db_session.execute(select(Event).where(Event.workspace_id == wid)).scalars()
    )
    assert AGENT_NOTES  # documented local-only boundary


def test_sb042_no_role_or_route_can_send_in_this_build(client, db_session, monkeypatch):
    _no_network(monkeypatch)
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    paths = set(app.openapi()["paths"])
    paths.update(getattr(route, "path", "") for route in app.routes)
    segments = {
        segment.lower() for path in paths for segment in path.split("/") if segment
    }
    assert "send" not in segments
    assert "sender" not in segments
    assert "outbox" not in segments
    assert not any(path.endswith("/outreach-drafts/{draft_id}/send") for path in paths)

    assert "sender" not in AGENT_ROLE_DESCRIPTORS
    assert all(not descriptor["send"] for descriptor in AGENT_ROLE_DESCRIPTORS.values())
    # No explicit send verb exists. A wildcard role such as owner is not a
    # sender: there is no send route or adapter that would act on the verb.
    explicit_permissions = {
        permission
        for permissions in ROLE_PERMISSIONS.values()
        for permission in permissions
    }
    assert not any("send" in permission for permission in explicit_permissions)

    # Even a configured provider and an explicit "send" operation stays local.
    integration = client.put(
        INTEGRATIONS.format(wid=wid),
        headers=headers,
        json={"provider": "gmail", "status": "configured", "config": {"region": "local-test"}},
    )
    assert integration.status_code == 200, integration.text
    invoked = client.post(
        ADAPTERS.format(wid=wid) + "/gmail/invoke",
        headers=headers,
        json={"operation": "send", "request": {"to": "nobody@example.test"}},
    )
    assert invoked.status_code == 200, invoked.text
    assert invoked.json()["response"]["delivered"] is False
    assert all(
        call.response_summary.get("delivered") is False
        for call in db_session.execute(select(AdapterCall)).scalars()
    )

    # Approving a draft with a configured provider still does not send.
    intake = _intake(client, wid, headers, "never-sent@example.test", "Never Sent")
    approved = client.post(
        DRAFTS.format(wid=wid) + f"/{intake['draft_id']}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text
    assert db_session.get(OutreachDraft, intake["draft_id"]).status == "approved"
    assert all(
        call.response_summary.get("delivered") is False
        for call in db_session.execute(select(AdapterCall)).scalars()
    )


def test_sb079_drafts_carry_configured_compliance_footer_and_cannot_be_sent(
    client, db_session, monkeypatch
):
    _no_network(monkeypatch)
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    safety = SAFETY.format(wid=wid)
    intake = _intake(client, wid, headers, "footer@example.test", "Footer Test")

    assert DEFAULT_COMPLIANCE_FOOTER in db_session.get(
        OutreachDraft, intake["draft_id"]
    ).body

    owner_footer = "Owner-approved footer: reply OPTOUT to stop messages."
    updated = client.put(
        safety + "/policy", headers=headers, json={"compliance_footer": owner_footer}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["compliance_footer"] == owner_footer
    assert _events_of_type(db_session, wid, FOOTER_UPDATED)

    created = client.post(
        DRAFTS.format(wid=wid),
        headers=headers,
        json={
            "contact_id": intake["contact_id"],
            "subject_template": "A local draft for {{first_name}}",
            "body_template": "Hello {{full_name}}, this is a local draft.",
        },
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["body"].endswith(owner_footer)
    assert DEFAULT_COMPLIANCE_FOOTER not in draft["body"]
    assert draft["status"] == "draft" and draft["approved_by"] is None
    assert db_session.execute(select(AdapterCall)).scalars().all() == []
    assert all(
        "delivered" not in event.payload
        or event.payload["delivered"] is False
        for event in db_session.execute(select(Event)).scalars()
    )


@pytest.mark.parametrize("footer", ["", "   "])
def test_sb079_blank_footer_is_rejected(client, db_session, footer):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    response = client.put(
        SAFETY.format(wid=wid) + "/policy",
        headers=headers,
        json={"compliance_footer": footer},
    )
    assert response.status_code == 422, response.text
