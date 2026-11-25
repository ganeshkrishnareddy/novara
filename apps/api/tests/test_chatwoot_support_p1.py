"""Named acceptance tests for the Chatwoot/Support P1 cluster.

Every test drives the real FastAPI app through the shared ``client``,
``db_session``, ``bootstrap`` and ``auth`` fixtures. All rows are local, every
mutation publishes through the shared event spine with the verified actor, and
no test makes an external call.

CW-166 drives the support module's local signed inbound webhook end to end; the
HMAC signature is computed in the test, never supplied as a placeholder.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from novara_core.database import Base
from novara_core.main import API
from novara_core.models import Contact, Event, Note, Session, now
from novara_core.modules import support

from .conftest import auth, bootstrap


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _base(wid: str) -> str:
    return f"{API}/workspaces/{wid}/tickets"


def _setup(client, name="CW P1", email="cw-owner@example.com"):
    tokens = bootstrap(client, name, email)
    wid = tokens["workspace_id"]
    return wid, auth(tokens["access_token"]), tokens


def _other(client, headers):
    response = client.post(f"{API}/workspaces", headers=headers, json={"name": "Other CW"})
    assert response.status_code == 200, response.text
    data = response.json()
    return data["workspace_id"], auth(data["access_token"])


def _member(client, wid, owner_headers, email, role="support"):
    """Invite, register and accept a real second member with an explicit role."""
    invite = client.post(
        f"{API}/workspaces/{wid}/invitations", headers=owner_headers,
        json={"email": email, "role": role},
    )
    assert invite.status_code == 200, invite.text
    registered = client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Password123!", "display_name": email.split("@")[0]},
    )
    assert registered.status_code == 200, registered.text
    accepted = client.post(
        f"{API}/invitations/accept",
        headers=auth(registered.json()["access_token"]),
        json={"token": invite.json()["invite_token"]},
    )
    assert accepted.status_code == 200, accepted.text
    headers = auth(accepted.json()["access_token"])
    me = client.get(f"{API}/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return headers, me.json()["user"]["id"]


def _me(client, headers) -> dict:
    response = client.get(f"{API}/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _contact(client, wid, headers, email, **extra):
    response = client.post(
        f"{API}/workspaces/{wid}/contacts", headers=headers,
        json={"email": email, **extra},
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def _ticket(client, wid, headers, subject="Subject", body="Body", **extra):
    response = client.post(
        _base(wid), headers=headers,
        json={"subject": subject, "body": body, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _team(client, wid, headers, name):
    response = client.post(_base(wid) + "/teams", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _label(client, wid, headers, name, color="#FF0000"):
    response = client.post(
        _base(wid) + "/labels", headers=headers, json={"name": name, "color": color}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _events(db_session, wid, *types):
    query = select(Event).where(Event.workspace_id == wid)
    if types:
        query = query.where(Event.event_type.in_(types))
    return db_session.execute(query.order_by(Event.seq)).scalars().all()


def _actor(event: Event) -> str | None:
    return (event.payload or {}).get("actor_id")


def _touch(db_session, model, row_id, **fields):
    row = db_session.execute(select(model).where(model.id == row_id)).scalar_one()
    for key, value in fields.items():
        setattr(row, key, value)
    db_session.commit()
    return row


# ---------------------------------------------------------------------------
# CW-005 — teams
# ---------------------------------------------------------------------------


def test_cw005_team_creation_membership_and_assignment(client, db_session):
    """CW-005: named teams, real memberships, ticket assignment, team filters."""
    wid, headers, _ = _setup(client, "CW005", "cw005-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    agent_headers, agent_id = _member(client, wid, headers, "cw005-agent@example.com", "support")
    other_wid, other_headers = _other(client, headers)

    created = client.post(base + "/teams", headers=headers,
                          json={"name": "Billing", "description": "Billing queue"})
    assert created.status_code == 201, created.text
    team = created.json()
    tid = team["id"]
    assert team["name"] == "Billing" and team["created_at"]

    assert client.post(base + "/teams", headers=headers, json={"name": "Billing"}).status_code == 409
    assert client.post(base + "/teams", headers=headers, json={"name": "  "}).status_code == 422
    assert client.post(base + "/teams", headers=headers,
                       json={"name": "Extra", "bogus": 1}).status_code == 422
    assert agent_id not in [m["user_id"] for m in client.get(base + f"/teams/{tid}/members",
                                                             headers=headers).json()]

    added = client.post(base + f"/teams/{tid}/members", headers=headers,
                        json={"user_id": agent_id})
    assert added.status_code == 201, added.text
    assert added.json()["user_id"] == agent_id and added.json()["email"]
    assert client.post(base + f"/teams/{tid}/members", headers=headers,
                       json={"user_id": agent_id}).status_code == 409
    assert client.post(base + f"/teams/{tid}/members", headers=headers,
                       json={"user_id": "not-a-user"}).status_code == 422
    members = client.get(base + f"/teams/{tid}/members", headers=headers)
    assert members.status_code == 200, members.text
    assert [m["user_id"] for m in members.json()] == [agent_id]

    first = _ticket(client, wid, headers, subject="A", body="Body A", team_id=tid)
    second = _ticket(client, wid, headers, subject="B", body="Body B")
    assert first["team_id"] == tid and second["team_id"] is None

    ids = lambda params: {row["id"] for row in
                          client.get(base, headers=headers, params=params).json()}
    assert ids({"team_id": tid}) == {first["id"]}
    patched = client.patch(base + f"/{second['id']}", headers=headers, json={"team_id": tid})
    assert patched.status_code == 200 and patched.json()["team_id"] == tid, patched.text
    assert ids({"team_id": tid}) == {first["id"], second["id"]}

    events = _events(db_session, wid, support.TEAM_CREATED,
                     support.TEAM_MEMBER_ADDED, support.TICKET_TEAM_ASSIGNED)
    team_events = [e for e in events if e.event_type == support.TEAM_CREATED and e.entity_id == tid]
    assert len(team_events) == 1 and _actor(team_events[0]) == owner_id
    member_events = [e for e in events if e.event_type == support.TEAM_MEMBER_ADDED]
    assert any(e.payload["team_id"] == tid and e.payload["user_id"] == agent_id
               and _actor(e) == owner_id for e in member_events)
    assigned = [e for e in events if e.event_type == support.TICKET_TEAM_ASSIGNED]
    assert len(assigned) == 1
    assert assigned[0].correlation_id == second["id"]
    assert assigned[0].payload["to"] == tid and _actor(assigned[0]) == owner_id

    teams = db_session.execute(
        select(support.SupportTeam).where(support.SupportTeam.workspace_id == wid)
    ).scalars().all()
    assert tid in {row.id for row in teams}
    memberships = db_session.execute(
        select(support.SupportTeamMember).where(
            support.SupportTeamMember.workspace_id == wid,
            support.SupportTeamMember.team_id == tid,
        )
    ).scalars().all()
    assert {row.user_id for row in memberships} == {agent_id}

    # Workspace isolation and permission gating.
    assert client.get(base + "/teams", headers=other_headers).status_code == 403
    assert client.post(base + "/teams", headers=other_headers,
                       json={"name": "Other"}).status_code == 403
    assert client.get(base, headers=other_headers, params={"team_id": tid}).status_code == 403
    assert client.get(_base(other_wid) + "/teams", headers=headers).status_code == 403
    assert client.get(_base(other_wid) + f"/teams/{tid}/members",
                      headers=other_headers).status_code == 404
    read_headers, _ = _member(client, wid, headers, "cw005-read@example.com", "read_only")
    assert client.get(base + "/teams", headers=read_headers).status_code == 200
    assert client.post(base + "/teams", headers=read_headers,
                       json={"name": "Denied"}).status_code == 403
    assert client.post(base + f"/teams/{tid}/members", headers=read_headers,
                       json={"user_id": owner_id}).status_code == 403
    assert agent_headers is not None  # the active member is the one stored above


# ---------------------------------------------------------------------------
# CW-008 — deterministic auto-assignment
# ---------------------------------------------------------------------------


def test_cw008_routing_rule_trace_and_manual_assignment_wins(client, db_session):
    """CW-008: stored routing rule assigns a new ticket, records its run, manual wins."""
    wid, headers, _ = _setup(client, "CW008", "cw008-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    _, agent_id = _member(client, wid, headers, "cw008-agent@example.com", "support")
    other_wid, other_headers = _other(client, headers)

    response = client.post(base + "/routing-rules", headers=headers, json={
        "name": "All to agent", "channel": "any", "strategy": "round_robin",
        "assignee_id": agent_id, "enabled": True, "priority": 10,
    })
    assert response.status_code == 201, response.text
    rule = response.json()
    rid = rule["id"]
    assert rule["assignee_id"] == agent_id and rule["enabled"] is True

    automatic = _ticket(client, wid, headers, subject="Auto", body="Automatically routed")
    assert automatic["assignee_id"] == agent_id
    created = [e for e in _events(db_session, wid, support.TICKET_CREATED)
               if e.correlation_id == automatic["id"]]
    assert len(created) == 1 and created[0].payload["routing_rule_id"] == rid
    auto = [e for e in _events(db_session, wid, support.TICKET_AUTO_ASSIGNED)
            if e.correlation_id == automatic["id"]]
    assert len(auto) == 1
    assert auto[0].payload["rule_id"] == rid
    assert auto[0].payload["strategy"] == "round_robin"
    assert auto[0].payload["channel"] == "local"
    assert _actor(auto[0]) == owner_id

    manual = _ticket(client, wid, headers, subject="Manual", body="Chosen by a human",
                     assignee_id=owner_id)
    assert manual["assignee_id"] == owner_id
    assert not [e for e in _events(db_session, wid, support.TICKET_AUTO_ASSIGNED)
                if e.correlation_id == manual["id"]]

    row = db_session.execute(
        select(support.Ticket).where(support.Ticket.id == automatic["id"])
    ).scalar_one()
    assert row.assignee_id == agent_id
    assert db_session.execute(
        select(support.Ticket).where(support.Ticket.id == manual["id"])
    ).scalar_one().assignee_id == owner_id
    assert db_session.execute(
        select(support.RoutingRule).where(
            support.RoutingRule.workspace_id == wid, support.RoutingRule.id == rid
        )
    ).scalar_one() is not None

    assert client.post(base + "/routing-rules", headers=headers,
                       json={"name": "Bad channel", "channel": "carrier-pigeon"}).status_code == 422
    assert client.post(base + "/routing-rules", headers=headers,
                       json={"name": "Bad strategy", "strategy": "random"}).status_code == 422
    assert client.post(base + "/routing-rules", headers=headers,
                       json={"name": "Bad assignee", "assignee_id": "ghost"}).status_code == 422

    assert client.get(base + "/routing-rules", headers=other_headers).status_code == 403
    assert client.post(base + "/routing-rules", headers=other_headers,
                       json={"name": "Foreign"}).status_code == 403
    assert client.get(_base(other_wid) + "/routing-rules", headers=headers).status_code == 403
    read_headers, _ = _member(client, wid, headers, "cw008-read@example.com", "read_only")
    assert client.get(base + "/routing-rules", headers=read_headers).status_code == 200
    assert client.post(base + "/routing-rules", headers=read_headers,
                       json={"name": "Denied"}).status_code == 403


# ---------------------------------------------------------------------------
# CW-012 — labels
# ---------------------------------------------------------------------------


def test_cw012_labels_create_apply_filter_and_report_per_workspace(client, db_session):
    """CW-012: labels are created, applied, filtered and counted in one workspace."""
    wid, headers, _ = _setup(client, "CW012", "cw012-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    other_wid, other_headers = _other(client, headers)

    label = _label(client, wid, headers, "needs-review")
    lid = label["id"]
    assert label["color"] == "#FF0000"
    assert client.post(base + "/labels", headers=headers,
                       json={"name": "needs-review"}).status_code == 409
    assert client.post(base + "/labels", headers=headers,
                       json={"name": "bad", "color": "red"}).status_code == 422
    assert client.post(base + "/labels", headers=headers,
                       json={"name": " "}).status_code == 422
    assert any(row["id"] == lid for row in client.get(base + "/labels", headers=headers).json())

    first = _ticket(client, wid, headers, subject="Labelled", body="One")
    second = _ticket(client, wid, headers, subject="Plain", body="Two")
    applied = client.post(base + f"/{first['id']}/labels", headers=headers, json={"label_id": lid})
    assert applied.status_code == 201, applied.text
    assert applied.json()["name"] == "needs-review"
    assert client.post(base + f"/{first['id']}/labels", headers=headers,
                       json={"label_id": lid}).status_code == 409
    assert client.post(base + f"/{second['id']}/labels", headers=headers,
                       json={"label_id": "not-a-label"}).status_code == 404

    listed = client.get(base + f"/{first['id']}/labels", headers=headers)
    assert listed.status_code == 200 and [r["label_id"] for r in listed.json()] == [lid]
    ids = lambda params: {row["id"] for row in
                          client.get(base, headers=headers, params=params).json()}
    assert ids({"label_id": lid}) == {first["id"]}
    assert client.get(base, headers=headers,
                      params={"label_id": "not-a-label"}).status_code == 422
    report = client.get(base + "/labels/report", headers=headers)
    assert report.status_code == 200, report.text
    assert next(row for row in report.json() if row["label_id"] == lid)["ticket_count"] == 1

    client.post(base + f"/{second['id']}/labels", headers=headers, json={"label_id": lid})
    assert ids({"label_id": lid}) == {first["id"], second["id"]}
    assert next(row for row in client.get(base + "/labels/report", headers=headers).json()
                if row["label_id"] == lid)["ticket_count"] == 2
    removed = client.delete(base + f"/{second['id']}/labels/{lid}", headers=headers)
    assert removed.status_code == 200 and removed.json()["label_id"] == lid
    assert ids({"label_id": lid}) == {first["id"]}
    assert next(row for row in client.get(base + "/labels/report", headers=headers).json()
                if row["label_id"] == lid)["ticket_count"] == 1

    labeled = [e for e in _events(db_session, wid, support.TICKET_LABELED)
               if e.correlation_id == first["id"]]
    unlabeled = [e for e in _events(db_session, wid, support.TICKET_UNLABELED)
                 if e.correlation_id == second["id"]]
    assert len(labeled) == 1 and labeled[0].payload["label_id"] == lid
    assert _actor(labeled[0]) == owner_id
    assert len(unlabeled) == 1 and _actor(unlabeled[0]) == owner_id
    assert len([e for e in _events(db_session, wid, support.LABEL_CREATED)
                if e.entity_id == lid]) == 1

    links = db_session.execute(
        select(support.TicketLabel).where(support.TicketLabel.workspace_id == wid)
    ).scalars().all()
    assert {row.ticket_id for row in links} == {first["id"]}
    assert db_session.execute(
        select(support.SupportLabel).where(
            support.SupportLabel.workspace_id == wid, support.SupportLabel.id == lid
        )
    ).scalar_one() is not None

    assert client.get(base + "/labels", headers=other_headers).status_code == 403
    assert client.post(base + "/labels", headers=other_headers,
                       json={"name": "Foreign"}).status_code == 403
    assert client.get(base + "/labels/report", headers=other_headers).status_code == 403
    assert client.get(_base(other_wid) + "/labels", headers=headers).status_code == 403
    assert client.post(base + f"/{first['id']}/labels", headers=other_headers,
                       json={"label_id": lid}).status_code == 403
    read_headers, _ = _member(client, wid, headers, "cw012-read@example.com", "read_only")
    assert client.get(base + "/labels", headers=read_headers).status_code == 200
    assert client.post(base + "/labels", headers=read_headers,
                       json={"name": "Denied"}).status_code == 403
    assert client.post(base + f"/{first['id']}/labels", headers=read_headers,
                       json={"label_id": lid}).status_code == 403


# ---------------------------------------------------------------------------
# CW-013 — typed custom attributes
# ---------------------------------------------------------------------------


def test_cw013_typed_attributes_on_contact_and_ticket_filter_and_export(client, db_session):
    """CW-013: one typed definition is set on a contact and a ticket, then filtered/exported."""
    wid, headers, _ = _setup(client, "CW013", "cw013-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    other_wid, other_headers = _other(client, headers)
    contact = _contact(client, wid, headers, "cw013@example.com", full_name="CW13")
    ticket = _ticket(client, wid, headers, subject="Attribute ticket", body="With attributes")

    created = client.post(base + "/custom-attributes", headers=headers, json={
        "key": "plan_tier", "label": "Plan tier", "value_type": "text", "target": "both",
    })
    assert created.status_code == 201, created.text
    attr = created.json()
    aid = attr["id"]
    assert attr["value_type"] == "text" and attr["target"] == "both"
    assert client.post(base + "/custom-attributes", headers=headers, json={
        "key": "plan_tier", "label": "Dup", "value_type": "text", "target": "both",
    }).status_code == 409
    assert client.post(base + "/custom-attributes", headers=headers, json={
        "key": "Bad-Key", "label": "Bad", "value_type": "text", "target": "both",
    }).status_code == 422
    assert client.post(base + "/custom-attributes", headers=headers, json={
        "key": "bad_type", "label": "Bad", "value_type": "formula", "target": "both",
    }).status_code == 422

    contact_value = client.post(base + f"/custom-attributes/{aid}/values", headers=headers,
                                json={"entity_type": "contact", "entity_id": contact["id"],
                                      "value": "gold"})
    assert contact_value.status_code == 200, contact_value.text
    assert contact_value.json()["value"] == "gold"
    ticket_value = client.post(base + f"/custom-attributes/{aid}/values", headers=headers,
                               json={"entity_type": "ticket", "entity_id": ticket["id"],
                                     "value": "gold"})
    assert ticket_value.status_code == 200, ticket_value.text
    assert client.post(base + f"/custom-attributes/{aid}/values", headers=headers,
                       json={"entity_type": "ticket", "entity_id": ticket["id"],
                             "value": 7}).status_code == 422
    assert client.post(base + f"/custom-attributes/{aid}/values", headers=headers,
                       json={"entity_type": "ticket", "entity_id": "not-a-ticket",
                             "value": "gold"}).status_code == 422

    values = client.get(base + "/custom-attributes/values", headers=headers,
                        params={"entity_type": "contact", "entity_id": contact["id"]})
    assert values.status_code == 200, values.text
    assert any(row["key"] == "plan_tier" and row["value"] == "gold" for row in values.json())
    ids = lambda params: {row["id"] for row in
                          client.get(base, headers=headers, params=params).json()}
    assert ids({"attr_key": "plan_tier", "attr_value": "gold"}) == {ticket["id"]}
    assert ids({"attr_key": "plan_tier", "attr_value": "silver"}) == set()
    assert client.get(base, headers=headers, params={"attr_key": "plan_tier"}).status_code == 422
    assert client.get(base, headers=headers,
                      params={"attr_key": "unknown", "attr_value": "x"}).status_code == 422

    exported = client.get(base + "/custom-attributes/export", headers=headers)
    assert exported.status_code == 200, exported.text
    rows = exported.json()
    assert {"entity_type": "contact", "entity_id": contact["id"],
            "key": "plan_tier", "value": "gold"} in rows
    assert {"entity_type": "ticket", "entity_id": ticket["id"],
            "key": "plan_tier", "value": "gold"} in rows

    number = client.post(base + "/custom-attributes", headers=headers, json={
        "key": "sla_score", "label": "Score", "value_type": "number", "target": "ticket",
    }).json()
    assert client.post(base + f"/custom-attributes/{number['id']}/values", headers=headers,
                       json={"entity_type": "ticket", "entity_id": ticket["id"],
                             "value": "not-a-number"}).status_code == 422
    assert client.post(base + f"/custom-attributes/{number['id']}/values", headers=headers,
                       json={"entity_type": "contact", "entity_id": contact["id"],
                             "value": 3}).status_code == 422
    assert client.post(base + f"/custom-attributes/{number['id']}/values", headers=headers,
                       json={"entity_type": "ticket", "entity_id": ticket["id"],
                             "value": 7}).status_code == 200

    created_events = [e for e in _events(db_session, wid, support.ATTRIBUTE_CREATED)
                      if e.entity_id == aid]
    assert len(created_events) == 1 and _actor(created_events[0]) == owner_id
    assert created_events[0].payload["value_type"] == "text"
    set_events = [e for e in _events(db_session, wid, support.ATTRIBUTE_SET)
                  if e.payload.get("attribute_id") == aid]
    assert len(set_events) == 2 and all(_actor(e) == owner_id for e in set_events)
    stored = db_session.execute(
        select(support.CustomAttributeValue).where(
            support.CustomAttributeValue.workspace_id == wid,
            support.CustomAttributeValue.attribute_id == aid,
        )
    ).scalars().all()
    assert {(row.entity_type, row.entity_id, row.value["value"]) for row in stored} == {
        ("contact", contact["id"], "gold"), ("ticket", ticket["id"], "gold"),
    }

    assert client.get(base + "/custom-attributes", headers=other_headers).status_code == 403
    assert client.get(base + "/custom-attributes/export", headers=other_headers).status_code == 403
    assert client.get(_base(other_wid) + "/custom-attributes/export", headers=headers).status_code == 403
    assert client.post(base + "/custom-attributes", headers=other_headers,
                       json={"key": "foreign", "label": "F", "value_type": "text",
                             "target": "both"}).status_code == 403
    read_headers, _ = _member(client, wid, headers, "cw013-read@example.com", "read_only")
    assert client.get(base + "/custom-attributes/export", headers=read_headers).status_code == 200
    assert client.post(base + "/custom-attributes", headers=read_headers,
                       json={"key": "denied", "label": "D", "value_type": "text",
                             "target": "both"}).status_code == 403


# ---------------------------------------------------------------------------
# CW-016 — contact-only notes
# ---------------------------------------------------------------------------


def test_cw016_contact_note_is_internal_only_audited_and_never_delivered(client, db_session):
    """CW-016: a CRM note is shown on the contact, never as a message, with its author audited."""
    wid, headers, _ = _setup(client, "CW016", "cw016-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    other_wid, other_headers = _other(client, headers)
    contact = _contact(client, wid, headers, "cw016@example.com", full_name="CW16")
    ticket = _ticket(client, wid, headers, subject="Note ticket", body="Hello",
                     contact_id=contact["id"])

    # Support owns the contact-note API at the tickets base path: it validates
    # the contact id from the path. The CRM /contacts/.../notes route instead
    # requires contact_id in the JSON body, so it is not the API under test.
    created = client.post(base + f"/contacts/{contact['id']}/notes",
                          headers=headers, json={"body": "Call back on Tuesday"})
    assert created.status_code == 201, created.text
    note = created.json()
    assert note["author_id"] == owner_id and note["body"] == "Call back on Tuesday"
    assert client.post(base + f"/contacts/{contact['id']}/notes",
                       headers=headers, json={"body": "   "}).status_code == 422

    support_notes = client.get(base + f"/contacts/{contact['id']}/notes", headers=headers)
    assert support_notes.status_code == 200, support_notes.text
    assert len(support_notes.json()) == 1
    shown = support_notes.json()[0]
    assert shown["id"] == note["id"]
    assert shown["internal_only"] is True and shown["author_id"] == owner_id

    messages = client.get(base + f"/{ticket['id']}/messages", headers=headers)
    assert messages.status_code == 200, messages.text
    assert messages.json() == []
    assert db_session.execute(
        select(support.TicketMessage).where(
            support.TicketMessage.workspace_id == wid,
            support.TicketMessage.body == "Call back on Tuesday",
        )
    ).scalars().all() == []

    note_events = [e for e in _events(db_session, wid) if e.entity_id == note["id"]]
    assert len(note_events) == 1
    assert note_events[0].event_type == "note.created"
    assert _actor(note_events[0]) == owner_id
    assert note_events[0].payload["contact_id"] == contact["id"]
    assert not [e for e in _events(db_session, wid, support.TICKET_MESSAGE_ADDED)
                if e.entity_id == note["id"]]

    assert db_session.execute(
        select(Note).where(Note.workspace_id == wid, Note.id == note["id"])
    ).scalar_one() is not None
    assert client.get(base + f"/contacts/{contact['id']}/notes",
                      headers=other_headers).status_code == 403
    assert client.get(_base(other_wid) + f"/contacts/{contact['id']}/notes",
                      headers=other_headers).status_code == 404
    assert client.post(base + f"/contacts/{contact['id']}/notes",
                       headers=other_headers, json={"body": "Foreign"}).status_code == 403
    read_headers, _ = _member(client, wid, headers, "cw016-read@example.com", "read_only")
    assert client.get(base + f"/contacts/{contact['id']}/notes",
                      headers=read_headers).status_code == 200
    assert client.post(base + f"/contacts/{contact['id']}/notes",
                       headers=read_headers, json={"body": "Denied"}).status_code == 403


# ---------------------------------------------------------------------------
# CW-017 — correlated contact timeline
# ---------------------------------------------------------------------------


def test_cw017_contact_timeline_correlates_tickets_and_messages_in_order(client, db_session):
    """CW-017: opening a contact shows ordered, correlated ticket events with no leakage."""
    wid, headers, _ = _setup(client, "CW017", "cw017-owner@example.com")
    base = _base(wid)
    other_wid, other_headers = _other(client, headers)
    contact = _contact(client, wid, headers, "cw017@example.com", full_name="CW17")
    ticket = _ticket(client, wid, headers, subject="Thread", body="Thread body",
                     contact_id=contact["id"])
    inbound = client.post(base + f"/{ticket['id']}/messages", headers=headers,
                          json={"body": "Question", "direction": "inbound", "channel": "email"})
    assert inbound.status_code == 201, inbound.text
    outbound = client.post(base + f"/{ticket['id']}/messages", headers=headers,
                           json={"body": "Answer", "direction": "outbound", "channel": "email"})
    assert outbound.status_code == 201, outbound.text

    timeline = client.get(base + f"/contacts/{contact['id']}/timeline", headers=headers)
    assert timeline.status_code == 200, timeline.text
    items = timeline.json()
    assert items, "a linked ticket must produce timeline events"
    assert [item["seq"] for item in items] == sorted(item["seq"] for item in items)
    assert all(item["correlation_id"] == ticket["id"] for item in items)
    types = [item["event_type"] for item in items]
    assert support.TICKET_CONTACT_LINKED in types
    assert support.TICKET_CREATED in types
    assert types.count(support.TICKET_MESSAGE_ADDED) == 2
    linked = next(item for item in items if item["event_type"] == support.TICKET_CONTACT_LINKED)
    assert linked["entity_id"] == contact["id"]
    message_events = [item for item in items if item["event_type"] == support.TICKET_MESSAGE_ADDED]
    assert {item["payload"]["direction"] for item in message_events} == {"inbound", "outbound"}
    assert {item["payload"]["channel"] for item in message_events} == {"email"}

    # A second tenant's ticket must never appear on this contact's timeline.
    other_contact = _contact(client, other_wid, other_headers, "cw017-other@example.com")
    foreign = _ticket(client, other_wid, other_headers, subject="Foreign", body="Foreign",
                      contact_id=other_contact["id"])
    client.post(_base(other_wid) + f"/{foreign['id']}/messages", headers=other_headers,
                json={"body": "Foreign reply"})
    after = client.get(base + f"/contacts/{contact['id']}/timeline", headers=headers).json()
    assert all(item["correlation_id"] != foreign["id"] for item in after)
    assert len(after) == len(items)
    assert all(e.workspace_id == wid for e in
               db_session.execute(select(Event).where(
                   Event.workspace_id == wid,
                   Event.correlation_id.in_([ticket["id"]]),
               )).scalars().all())

    assert client.get(base + f"/contacts/{contact['id']}/timeline",
                      headers=other_headers).status_code == 403
    assert client.get(_base(other_wid) + f"/contacts/{contact['id']}/timeline",
                      headers=other_headers).status_code == 404
    read_headers, _ = _member(client, wid, headers, "cw017-read@example.com", "read_only")
    assert client.get(base + f"/contacts/{contact['id']}/timeline",
                      headers=read_headers).status_code == 200
    assert client.post(base + f"/{ticket['id']}/messages", headers=other_headers,
                       json={"body": "Cross"}).status_code == 403


# ---------------------------------------------------------------------------
# CW-023 — saved replies
# ---------------------------------------------------------------------------


def test_cw023_saved_reply_expand_into_draft_without_sending(client, db_session):
    """CW-023: create, list and expand a saved reply locally; nothing is delivered."""
    wid, headers, _ = _setup(client, "CW023", "cw023-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    other_wid, other_headers = _other(client, headers)
    contact = _contact(client, wid, headers, "cw023@example.com", full_name="Ada")
    ticket = _ticket(client, wid, headers, subject="Refund question", body="Please help")

    created = client.post(base + "/saved-replies", headers=headers, json={
        "name": "greeting",
        "body": "Hi {{ contact.name }} ({{ contact.email }}), re {{ ticket.subject }} "
                "[{{ ticket.id }}] {{ contact.unknown }}",
    })
    assert created.status_code == 201, created.text
    reply = created.json()
    rid = reply["id"]
    assert reply["created_by"] == owner_id
    assert any(row["id"] == rid for row in client.get(base + "/saved-replies", headers=headers).json())
    assert client.post(base + "/saved-replies", headers=headers,
                       json={"name": "greeting", "body": "dup"}).status_code == 409
    assert client.post(base + "/saved-replies", headers=headers,
                       json={"name": "", "body": "x"}).status_code == 422

    before_messages = db_session.execute(
        select(func.count()).select_from(support.TicketMessage)
        .where(support.TicketMessage.workspace_id == wid)
    ).scalar_one()
    before_message_events = len([e for e in _events(db_session, wid,
                                                    support.TICKET_MESSAGE_ADDED)])

    expanded = client.post(base + f"/saved-replies/{rid}/expand", headers=headers,
                           json={"contact_id": contact["id"], "ticket_id": ticket["id"]})
    assert expanded.status_code == 200, expanded.text
    data = expanded.json()
    assert data["id"] == rid and data["name"] == "greeting"
    assert "Hi Ada (cw023@example.com)" in data["body"]
    assert "Refund question" in data["body"] and ticket["id"] in data["body"]
    assert data["unresolved"] == ["contact.unknown"]
    assert "{{ contact.unknown }}" in data["body"]

    assert db_session.execute(
        select(func.count()).select_from(support.TicketMessage)
        .where(support.TicketMessage.workspace_id == wid)
    ).scalar_one() == before_messages
    assert len([e for e in _events(db_session, wid, support.TICKET_MESSAGE_ADDED)]) == before_message_events
    expansion_events = [e for e in _events(db_session, wid, support.SAVED_REPLY_EXPANDED)
                        if e.entity_id == rid]
    assert len(expansion_events) == 1
    assert expansion_events[0].payload["delivered"] is False
    assert expansion_events[0].payload["contact_id"] == contact["id"]
    assert _actor(expansion_events[0]) == owner_id
    assert client.get(base + f"/{ticket['id']}/messages", headers=headers).json() == []

    assert client.get(base + "/saved-replies", headers=other_headers).status_code == 403
    assert client.post(base + f"/saved-replies/{rid}/expand", headers=other_headers,
                       json={}).status_code == 403
    assert client.post(base + f"/saved-replies/{rid}/expand", headers=headers,
                       json={"contact_id": "not-a-contact"}).status_code == 404
    assert client.post(_base(other_wid) + f"/saved-replies/{rid}/expand",
                       headers=other_headers, json={}).status_code == 404
    read_headers, _ = _member(client, wid, headers, "cw023-read@example.com", "read_only")
    assert client.get(base + "/saved-replies", headers=read_headers).status_code == 200
    assert client.post(base + f"/saved-replies/{rid}/expand", headers=read_headers,
                       json={"ticket_id": ticket["id"]}).status_code == 200
    assert client.post(base + "/saved-replies", headers=read_headers,
                       json={"name": "Denied", "body": "x"}).status_code == 403


# ---------------------------------------------------------------------------
# CW-024 — macros
# ---------------------------------------------------------------------------


def test_cw024_macro_applies_ordered_local_changes_atomically_with_audit(client, db_session):
    """CW-024: ordered local macro actions are validated then applied once; no external send."""
    wid, headers, _ = _setup(client, "CW024", "cw024-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    other_wid, other_headers = _other(client, headers)
    label = _label(client, wid, headers, "triaged")
    ticket = _ticket(client, wid, headers, subject="Macro ticket", body="Triage me")
    actions = [
        {"type": "set_status", "value": "pending"},
        {"type": "set_priority", "value": "high"},
        {"type": "assign", "value": owner_id},
        {"type": "label", "value": label["id"]},
    ]

    created = client.post(base + "/macros", headers=headers,
                          json={"name": "triage", "actions": actions})
    assert created.status_code == 201, created.text
    macro = created.json()
    mid = macro["id"]
    assert macro["created_by"] == owner_id
    assert any(row["id"] == mid for row in client.get(base + "/macros", headers=headers).json())
    assert client.post(base + "/macros", headers=headers,
                       json={"name": "external", "actions": [{"type": "send_email",
                                                              "value": "a@b.c"}]}).status_code == 422
    assert client.post(base + "/macros", headers=headers,
                       json={"name": "webhook", "actions": [{"type": "webhook",
                                                            "value": "https://x"}]}).status_code == 422
    assert client.post(base + "/macros", headers=headers,
                       json={"name": "empty", "actions": []}).status_code == 422

    dry = client.post(base + f"/macros/{mid}/dry-run", headers=headers, json={"ticket_id": ticket["id"]})
    assert dry.status_code == 200, dry.text
    plan = dry.json()
    assert plan["dry_run"] is True and plan["macro_id"] == mid
    assert [c["type"] for c in plan["changes"]] == [
        "set_status", "set_priority", "assign", "label",
    ]
    assert db_session.execute(
        select(support.Ticket).where(support.Ticket.id == ticket["id"])
    ).scalar_one().status == "open"
    dry_events = [e for e in _events(db_session, wid, support.MACRO_DRY_RUN)
                  if e.entity_id == mid]
    assert len(dry_events) == 1 and dry_events[0].payload["mutated"] is False

    applied = client.post(base + f"/macros/{mid}/apply", headers=headers,
                          json={"ticket_id": ticket["id"]})
    assert applied.status_code == 200, applied.text
    assert [c["type"] for c in applied.json()["changes"]] == [
        "set_status", "set_priority", "assign", "label",
    ]
    row = db_session.execute(
        select(support.Ticket).where(support.Ticket.id == ticket["id"])
    ).scalar_one()
    assert (row.status, row.priority, row.assignee_id) == ("pending", "high", owner_id)
    assert db_session.execute(
        select(support.TicketLabel.id).where(
            support.TicketLabel.workspace_id == wid,
            support.TicketLabel.ticket_id == ticket["id"],
            support.TicketLabel.label_id == label["id"],
        )
    ).scalar_one_or_none() is not None
    apply_events = [e for e in _events(db_session, wid, support.MACRO_APPLIED)
                    if e.entity_id == mid]
    assert len(apply_events) == 1
    assert apply_events[0].payload["external_delivery"] is False
    assert _actor(apply_events[0]) == owner_id

    # A bad last step must leave no partial changes behind.
    atomic_ticket = _ticket(client, wid, headers, subject="Atomic", body="All or nothing")
    bad = client.post(base + "/macros", headers=headers, json={
        "name": "bad-atomic",
        "actions": [{"type": "set_status", "value": "resolved"},
                    {"type": "assign", "value": "ghost-user"}],
    })
    assert bad.status_code == 201, bad.text
    failed = client.post(base + f"/macros/{bad.json()['id']}/apply", headers=headers,
                         json={"ticket_id": atomic_ticket["id"]})
    assert failed.status_code == 422, failed.text
    untouched = db_session.execute(
        select(support.Ticket).where(support.Ticket.id == atomic_ticket["id"])
    ).scalar_one()
    assert untouched.status == "open" and untouched.assignee_id is None

    # The one message-producing action is still a local row, not a delivery.
    local = client.post(base + "/macros", headers=headers, json={
        "name": "local-reply",
        "actions": [{"type": "reply", "value": "Local answer only"}],
    })
    assert local.status_code == 201, local.text
    applied_local = client.post(base + f"/macros/{local.json()['id']}/apply", headers=headers,
                                json={"ticket_id": atomic_ticket["id"]})
    assert applied_local.status_code == 200, applied_local.text
    message = db_session.execute(
        select(support.TicketMessage).where(
            support.TicketMessage.workspace_id == wid,
            support.TicketMessage.ticket_id == atomic_ticket["id"],
        )
    ).scalar_one()
    assert message.body == "Local answer only"
    assert message.channel == "local" and message.direction == "outbound" and not message.is_internal
    assert "external" not in support.MACRO_ACTION_TYPES

    assert client.get(base + "/macros", headers=other_headers).status_code == 403
    assert client.post(base + f"/macros/{mid}/apply", headers=other_headers,
                       json={"ticket_id": ticket["id"]}).status_code == 403
    assert client.post(_base(other_wid) + f"/macros/{mid}/dry-run", headers=other_headers,
                       json={"ticket_id": ticket["id"]}).status_code == 404
    read_headers, _ = _member(client, wid, headers, "cw024-read@example.com", "read_only")
    assert client.get(base + "/macros", headers=read_headers).status_code == 200
    assert client.post(base + "/macros", headers=read_headers,
                       json={"name": "Denied", "actions": actions}).status_code == 403
    assert client.post(base + f"/macros/{mid}/apply", headers=read_headers,
                       json={"ticket_id": ticket["id"]}).status_code == 403


# ---------------------------------------------------------------------------
# CW-028 — filters and SQL-injection resistance
# ---------------------------------------------------------------------------


def test_cw028_every_supported_filter_narrows_and_invalid_filters_return_422(client, db_session):
    """CW-028: allow-listed filters narrow real rows; arbitrary SQL and invalid values are rejected."""
    wid, headers, _ = _setup(client, "CW028", "cw028-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    contact_a = _contact(client, wid, headers, "cw028-a@example.com", full_name="A")
    contact_b = _contact(client, wid, headers, "cw028-b@example.com", full_name="B")
    team = _team(client, wid, headers, "Queue 28")
    label = _label(client, wid, headers, "flagged")
    inbox = client.post(base + "/inboxes", headers=headers,
                        json={"name": "Web Form", "channel": "web_form", "slug": "web-form"})
    assert inbox.status_code == 201, inbox.text
    inbox_id = inbox.json()["id"]
    attribute = client.post(base + "/custom-attributes", headers=headers, json={
        "key": "plan_code", "label": "Plan", "value_type": "text", "target": "ticket",
    }).json()

    first = _ticket(client, wid, headers, subject="Alpha", body="One",
                    contact_id=contact_a["id"], priority="urgent", origin_channel="web_form",
                    team_id=team["id"], inbox_id=inbox_id)
    second = _ticket(client, wid, headers, subject="Beta", body="Two",
                     priority="low", origin_channel="local", assignee_id=owner_id)
    third = _ticket(client, wid, headers, subject="Gamma", body="Three",
                    contact_id=contact_b["id"], priority="high", origin_channel="email")
    assert client.post(base + f"/{third['id']}/labels", headers=headers,
                       json={"label_id": label["id"]}).status_code == 201
    assert client.patch(base + f"/{third['id']}", headers=headers,
                        json={"status": "resolved"}).status_code == 200
    assert client.post(base + f"/custom-attributes/{attribute['id']}/values", headers=headers,
                       json={"entity_type": "ticket", "entity_id": third["id"],
                             "value": "pro"}).status_code == 200

    ids = lambda params: {row["id"] for row in
                          client.get(base, headers=headers, params=params).json()}
    assert ids({"status": "resolved"}) == {third["id"]}
    assert ids({"priority": "urgent"}) == {first["id"]}
    assert ids({"assignee_id": owner_id}) == {second["id"]}
    assert ids({"mine": "true"}) == {second["id"]}
    assert ids({"unassigned": "true"}) == {first["id"], third["id"]}
    assert ids({"contact_id": contact_a["id"]}) == {first["id"]}
    assert ids({"team_id": team["id"]}) == {first["id"]}
    assert ids({"label_id": label["id"]}) == {third["id"]}
    assert ids({"inbox_id": inbox_id}) == {first["id"]}
    assert ids({"channel": "web_form"}) == {first["id"]}
    assert ids({"attr_key": "plan_code", "attr_value": "pro"}) == {third["id"]}
    assert ids({"attr_key": "plan_code", "attr_value": "free"}) == set()
    assert ids({"status": "resolved", "label_id": label["id"],
                "attr_key": "plan_code", "attr_value": "pro"}) == {third["id"]}

    utc = datetime.now(timezone.utc)
    broad_from = (utc - timedelta(days=1)).isoformat()
    broad_to = (utc + timedelta(days=1)).isoformat()
    empty_from = (utc - timedelta(days=10)).isoformat()
    empty_to = (utc - timedelta(days=9)).isoformat()
    assert ids({"created_from": broad_from, "created_to": broad_to}) == {
        first["id"], second["id"], third["id"],
    }
    assert ids({"created_from": empty_from, "created_to": empty_to}) == set()

    bad_filters = [
        {"status": "open' OR '1'='1"},
        {"priority": "normal; DROP TABLE support_tickets"},
        {"channel": "local'--"},
        {"team_id": "' OR 1=1"},
        {"label_id": "x' OR 1=1"},
        {"inbox_id": "x' OR 1=1"},
        {"contact_id": "' OR 1=1"},
        {"attr_key": "plan' OR 1=1", "attr_value": "x"},
        {"created_from": "'; DROP TABLE support_tickets;--"},
        {"attr_key": "plan_code"},
        {"status": "not-a-status"},
        {"priority": "not-a-priority"},
        {"channel": "not-a-channel"},
        {"created_from": broad_to, "created_to": broad_from},
    ]
    for params in bad_filters:
        response = client.get(base, headers=headers, params=params)
        assert response.status_code == 422, (params, response.status_code, response.text)
    assert ids({}) == {first["id"], second["id"], third["id"]}

    other_wid, other_headers = _other(client, headers)
    assert client.get(base, headers=other_headers).status_code == 403
    assert client.get(_base(other_wid), headers=headers).status_code == 403
    assert client.get(base, headers=headers, params={"team_id": "00000000-0000-0000-0000-000000000000"}).status_code == 422
    assert client.get(base, headers=headers, params={"label_id": "00000000-0000-0000-0000-000000000000"}).status_code == 422
    assert client.get(base, headers=headers, params={"inbox_id": "00000000-0000-0000-0000-000000000000"}).status_code == 422
    assert client.get(base).status_code == 401
    read_headers, _ = _member(client, wid, headers, "cw028-read@example.com", "read_only")
    assert client.get(base, headers=read_headers).status_code == 200
    assert db_session.execute(
        select(func.count()).select_from(support.Ticket).where(support.Ticket.workspace_id == wid)
    ).scalar_one() == 3


# ---------------------------------------------------------------------------
# CW-051 — local conversation rules
# ---------------------------------------------------------------------------


def test_cw051_conversation_rule_reacts_locally_and_leaves_run_trace(client, db_session):
    """CW-051: a stored local rule reacts to a ticket event, applies local changes and traces the run."""
    wid, headers, _ = _setup(client, "CW051", "cw051-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    other_wid, other_headers = _other(client, headers)
    label = _label(client, wid, headers, "auto-tagged")
    ticket = _ticket(client, wid, headers, subject="Rule ticket", body="Watch me")

    created = client.post(base + "/conversation-rules", headers=headers, json={
        "name": "Escalate on resolve",
        "trigger": "ticket.status_changed",
        "actions": [{"type": "set_priority", "value": "urgent"},
                    {"type": "label", "value": label["id"]}],
        "enabled": True,
    })
    assert created.status_code == 201, created.text
    rule = created.json()
    rid = rule["id"]
    assert any(row["id"] == rid for row in
               client.get(base + "/conversation-rules", headers=headers).json())

    patched = client.patch(base + f"/{ticket['id']}", headers=headers, json={"status": "resolved"})
    assert patched.status_code == 200, patched.text
    row = db_session.execute(
        select(support.Ticket).where(support.Ticket.id == ticket["id"])
    ).scalar_one()
    assert row.status == "resolved" and row.priority == "urgent"
    assert db_session.execute(
        select(support.TicketLabel.id).where(
            support.TicketLabel.workspace_id == wid,
            support.TicketLabel.ticket_id == ticket["id"],
            support.TicketLabel.label_id == label["id"],
        )
    ).scalar_one_or_none() is not None

    runs = client.get(base + f"/conversation-rules/{rid}/runs", headers=headers)
    assert runs.status_code == 200, runs.text
    assert len(runs.json()) == 1
    run = runs.json()[0]
    assert run["rule_id"] == rid and run["ticket_id"] == ticket["id"]
    assert run["trigger"] == "ticket.status_changed" and run["actor_id"] == owner_id
    assert [change["type"] for change in run["changes"]] == ["set_priority", "label"]
    run_events = [e for e in _events(db_session, wid, support.CONVERSATION_RULE_RAN)
                  if e.payload.get("rule_id") == rid]
    assert len(run_events) == 1
    assert run_events[0].correlation_id == ticket["id"]
    assert _actor(run_events[0]) == owner_id

    dry_ticket = _ticket(client, wid, headers, subject="Dry run", body="No mutation")
    dry = client.post(base + f"/conversation-rules/{rid}/dry-run", headers=headers,
                      json={"ticket_id": dry_ticket["id"]})
    assert dry.status_code == 200, dry.text
    assert dry.json()["dry_run"] is True
    assert [c["type"] for c in dry.json()["changes"]] == ["set_priority", "label"]
    assert db_session.execute(
        select(support.Ticket).where(support.Ticket.id == dry_ticket["id"])
    ).scalar_one().priority == "normal"
    assert len(client.get(base + f"/conversation-rules/{rid}/runs", headers=headers).json()) == 1
    assert len([e for e in _events(db_session, wid, support.CONVERSATION_RULE_DRY_RUN)
                if e.entity_id == rid]) == 1

    assert client.post(base + "/conversation-rules", headers=headers, json={
        "name": "Bad trigger", "trigger": "email.sent", "actions": [{"type": "set_status", "value": "open"}],
    }).status_code == 422
    assert client.post(base + "/conversation-rules", headers=headers, json={
        "name": "External", "trigger": "ticket.created",
        "actions": [{"type": "send_email", "value": "a@b.c"}],
    }).status_code == 422
    assert client.post(base + "/conversation-rules", headers=headers, json={
        "name": "Reply", "trigger": "ticket.created",
        "actions": [{"type": "reply", "value": "Cannot send here"}],
    }).status_code == 422

    assert client.get(base + "/conversation-rules", headers=other_headers).status_code == 403
    assert client.get(base + f"/conversation-rules/{rid}/runs", headers=other_headers).status_code == 403
    assert client.get(_base(other_wid) + "/conversation-rules", headers=headers).status_code == 403
    assert client.get(_base(other_wid) + f"/conversation-rules/{rid}/runs",
                      headers=other_headers).status_code == 404
    read_headers, _ = _member(client, wid, headers, "cw051-read@example.com", "read_only")
    assert client.get(base + "/conversation-rules", headers=read_headers).status_code == 200
    assert client.post(base + "/conversation-rules", headers=read_headers, json={
        "name": "Denied", "trigger": "ticket.created",
        "actions": [{"type": "set_status", "value": "open"}],
    }).status_code == 403
    assert client.post(base + f"/conversation-rules/{rid}/dry-run", headers=read_headers,
                       json={"ticket_id": ticket["id"]}).status_code == 403


# ---------------------------------------------------------------------------
# CW-075 — saved contact segments
# ---------------------------------------------------------------------------


def test_cw075_segment_returns_exact_stored_rule_matches_and_is_reusable(client, db_session):
    """CW-075: a persisted segment definition returns exactly the matching local contacts."""
    wid, headers, _ = _setup(client, "CW075", "cw075-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    other_wid, other_headers = _other(client, headers)
    alpha = _contact(client, wid, headers, "cw075-a@example.com", full_name="Alice",
                     company_name="Alpha")
    beta = _contact(client, wid, headers, "cw075-b@example.com", full_name="Bob",
                    company_name="Beta")
    gamma = _contact(client, wid, headers, "cw075-c@example.com", full_name="Carol",
                     company_name="Alpha")
    for cid in (alpha["id"], gamma["id"]):
        patched = client.patch(f"{API}/workspaces/{wid}/contacts/{cid}", headers=headers,
                               json={"lifecycle_stage": "customer"})
        assert patched.status_code == 200, patched.text

    definition = {"match": "all", "conditions": [
        {"field": "lifecycle_stage", "op": "eq", "value": "customer"},
        {"field": "company_name", "op": "eq", "value": "Alpha"},
    ]}
    created = client.post(base + "/segments", headers=headers,
                          json={"name": "Alpha customers", "definition": definition})
    assert created.status_code == 201, created.text
    segment = created.json()
    sid = segment["id"]
    assert segment["definition"] == definition

    emails = lambda: {row["email"] for row in client.get(
        base + f"/segments/{sid}/contacts", headers=headers).json()}
    assert emails() == {alpha["email"], gamma["email"]}
    count = client.get(base + f"/segments/{sid}/count", headers=headers)
    assert count.status_code == 200 and count.json() == {"segment_id": sid, "count": 2}
    assert emails() == {alpha["email"], gamma["email"]}  # reusable, not recomputed differently
    assert any(row["id"] == sid for row in client.get(base + "/segments", headers=headers).json())

    any_segment = client.post(base + "/segments", headers=headers, json={
        "name": "Bob or Carol",
        "definition": {"match": "any", "conditions": [
            {"field": "full_name", "op": "contains", "value": "Bob"},
            {"field": "full_name", "op": "contains", "value": "Carol"},
        ]},
    }).json()
    assert {row["email"] for row in client.get(
        base + f"/segments/{any_segment['id']}/contacts", headers=headers).json()} == {
        beta["email"], gamma["email"],
    }

    attribute = client.post(base + "/custom-attributes", headers=headers, json={
        "key": "vip_level", "label": "VIP", "value_type": "text", "target": "contact",
    }).json()
    client.post(base + f"/custom-attributes/{attribute['id']}/values", headers=headers,
                json={"entity_type": "contact", "entity_id": gamma["id"], "value": "gold"})
    custom = client.post(base + "/segments", headers=headers, json={
        "name": "Gold contacts",
        "definition": {"match": "all", "conditions": [
            {"field": "custom:vip_level", "op": "eq", "value": "gold"},
        ]},
    })
    assert custom.status_code == 201, custom.text
    assert {row["email"] for row in client.get(
        base + f"/segments/{custom.json()['id']}/contacts", headers=headers).json()} == {
        gamma["email"],
    }

    invalid = [
        {"match": "none", "conditions": [{"field": "email", "op": "eq", "value": "x"}]},
        {"match": "all", "conditions": []},
        {"match": "all", "conditions": [{"field": "email; DROP TABLE contacts",
                                          "op": "eq", "value": "x"}]},
        {"match": "all", "conditions": [{"field": "email", "op": "in", "value": "x"}]},
        {"match": "all", "conditions": [{"field": "custom:BAD-KEY",
                                          "op": "eq", "value": "x"}]},
    ]
    for index, bad in enumerate(invalid):
        response = client.post(base + "/segments", headers=headers,
                               json={"name": f"bad-{index}", "definition": bad})
        assert response.status_code == 422, (bad, response.status_code, response.text)

    created_events = [e for e in _events(db_session, wid, support.SEGMENT_CREATED)
                      if e.entity_id == sid]
    assert len(created_events) == 1 and _actor(created_events[0]) == owner_id
    assert db_session.execute(
        select(support.ContactSegment).where(
            support.ContactSegment.workspace_id == wid, support.ContactSegment.id == sid
        )
    ).scalar_one().definition == definition
    foreign_contact = _contact(client, other_wid, other_headers, "cw075-foreign@example.com",
                               company_name="Alpha")
    assert client.patch(f"{API}/workspaces/{other_wid}/contacts/{foreign_contact['id']}",
                        headers=other_headers,
                        json={"lifecycle_stage": "customer"}).status_code == 200
    assert foreign_contact["email"] not in emails()

    assert client.get(base + "/segments", headers=other_headers).status_code == 403
    assert client.get(base + f"/segments/{sid}/contacts", headers=other_headers).status_code == 403
    assert client.get(_base(other_wid) + f"/segments/{sid}/contacts",
                      headers=other_headers).status_code == 404
    read_headers, _ = _member(client, wid, headers, "cw075-read@example.com", "read_only")
    assert client.get(base + f"/segments/{sid}/contacts", headers=read_headers).status_code == 200
    assert client.post(base + "/segments", headers=read_headers,
                       json={"name": "Denied", "definition": definition}).status_code == 403


# ---------------------------------------------------------------------------
# CW-086 — help centre publication
# ---------------------------------------------------------------------------


def test_cw086_published_public_article_readable_and_draft_hidden(client, db_session):
    """CW-086: public readers see only published public articles; drafts stay local to staff."""
    wid, headers, _ = _setup(client, "CW086", "cw086-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    other_wid, other_headers = _other(client, headers)

    portal = client.post(base + "/help-portals", headers=headers,
                         json={"name": "Docs", "slug": "docs"})
    assert portal.status_code == 201, portal.text
    pid = portal.json()["id"]
    assert client.post(base + "/help-portals", headers=headers,
                       json={"name": "Dup", "slug": "docs"}).status_code == 409
    assert client.post(base + "/help-portals", headers=headers,
                       json={"name": "Bad", "slug": "BAD SLUG"}).status_code == 422

    published = client.post(base + f"/help-portals/{pid}/articles", headers=headers, json={
        "title": "Public guide", "slug": "public-guide", "body": "Public body",
        "audience": "public", "status": "published",
    })
    assert published.status_code == 201, published.text
    assert published.json()["published_at"] is not None
    draft = client.post(base + f"/help-portals/{pid}/articles", headers=headers, json={
        "title": "Draft guide", "slug": "draft-guide", "body": "Draft body",
        "audience": "public", "status": "draft",
    })
    assert draft.status_code == 201 and draft.json()["published_at"] is None, draft.text
    agents = client.post(base + f"/help-portals/{pid}/articles", headers=headers, json={
        "title": "Agent guide", "slug": "agent-guide", "body": "Internal body",
        "audience": "agents", "status": "published",
    })
    assert agents.status_code == 201, agents.text

    public_list = client.get(base + "/public/help/docs/articles")
    assert public_list.status_code == 200, public_list.text
    assert [row["slug"] for row in public_list.json()] == ["public-guide"]
    assert client.get(base + "/public/help/docs/articles/public-guide").status_code == 200
    assert client.get(base + "/public/help/docs/articles/draft-guide").status_code == 404
    assert client.get(base + "/public/help/docs/articles/agent-guide").status_code == 404
    assert client.get(base + "/public/help/missing/articles").status_code == 404

    staff_list = client.get(base + f"/help-portals/{pid}/articles", headers=headers)
    assert staff_list.status_code == 200 and len(staff_list.json()) == 3, staff_list.text
    assert client.get(base + f"/help-articles/{draft.json()['id']}",
                      headers=headers).status_code == 200

    changed = client.patch(base + f"/help-articles/{draft.json()['id']}", headers=headers,
                           json={"status": "published"})
    assert changed.status_code == 200 and changed.json()["published_at"] is not None, changed.text
    assert "draft-guide" in [row["slug"] for row in
                             client.get(base + "/public/help/docs/articles").json()]
    reverted = client.patch(base + f"/help-articles/{draft.json()['id']}", headers=headers,
                            json={"status": "draft"})
    assert reverted.status_code == 200 and reverted.json()["published_at"] is None
    assert "draft-guide" not in [row["slug"] for row in
                                 client.get(base + "/public/help/docs/articles").json()]

    written = [e for e in _events(db_session, wid, support.HELP_ARTICLE_WRITTEN)
               if e.entity_id == published.json()["id"]]
    assert len(written) == 1 and _actor(written[0]) == owner_id
    assert written[0].payload["status"] == "published"

    other_portal = client.post(_base(other_wid) + "/help-portals", headers=other_headers,
                               json={"name": "Docs", "slug": "docs"})
    assert other_portal.status_code == 201, other_portal.text
    other_article = client.post(
        _base(other_wid) + f"/help-portals/{other_portal.json()['id']}/articles",
        headers=other_headers,
        json={"title": "Other", "slug": "other-guide", "body": "Other body",
              "audience": "public", "status": "published"},
    )
    assert other_article.status_code == 201, other_article.text
    other_public = client.get(_base(other_wid) + "/public/help/docs/articles").json()
    assert [row["slug"] for row in other_public] == ["other-guide"]
    assert client.get(base + f"/help-articles/{other_article.json()['id']}",
                      headers=headers).status_code == 404
    assert client.get(base + f"/help-portals/{pid}/articles", headers=other_headers).status_code == 403
    read_headers, _ = _member(client, wid, headers, "cw086-read@example.com", "read_only")
    assert client.get(base + "/public/help/docs/articles").status_code == 200
    assert client.post(base + f"/help-portals/{pid}/articles", headers=read_headers, json={
        "title": "Denied", "slug": "denied", "body": "x",
    }).status_code == 403


# ---------------------------------------------------------------------------
# CW-093 — dashboard counts
# ---------------------------------------------------------------------------


def test_cw093_dashboard_counts_equal_workspace_scoped_sql_counts(client, db_session):
    """CW-093: /counts and /reports/overview match SQL counts over the workspace's tickets."""
    wid, headers, _ = _setup(client, "CW093", "cw093-owner@example.com")
    base = _base(wid)
    other_wid, other_headers = _other(client, headers)
    sla = client.post(base + "/sla-policies", headers=headers,
                      json={"name": "Fast", "first_response_minutes": 60})
    assert sla.status_code == 201, sla.text
    for index in range(3):
        _ticket(client, wid, headers, subject=f"Open {index}", body="Body")
    _ticket(client, wid, headers, subject="Pending", body="Body", priority="urgent",
            assignee_id=_me(client, headers)["user"]["id"])
    _ticket(client, wid, headers, subject="Resolved", body="Body", sla_policy_id=sla.json()["id"])
    resolved = db_session.execute(
        select(support.Ticket).where(
            support.Ticket.workspace_id == wid, support.Ticket.subject == "Resolved"
        )
    ).scalar_one()
    assert client.patch(base + f"/{resolved.id}", headers=headers,
                        json={"status": "resolved"}).status_code == 200
    _ticket(client, other_wid, other_headers, subject="Foreign", body="Body", priority="urgent")

    def sql_counts(workspace_id):
        scope = support.Ticket.workspace_id == workspace_id
        by_status = dict(db_session.execute(
            select(support.Ticket.status, func.count(support.Ticket.id)).where(scope)
            .group_by(support.Ticket.status)
        ).all())
        one = lambda where: db_session.execute(
            select(func.count(support.Ticket.id)).where(scope, where)
        ).scalar_one()
        return {
            "total": db_session.execute(select(func.count(support.Ticket.id)).where(scope)).scalar_one(),
            "open": by_status.get("open", 0),
            "pending": by_status.get("pending", 0),
            "resolved": by_status.get("resolved", 0),
            "closed": by_status.get("closed", 0),
            "unassigned": one(support.Ticket.assignee_id.is_(None)),
            "urgent": one(support.Ticket.priority == "urgent"),
        }

    counts = client.get(base + "/counts", headers=headers)
    assert counts.status_code == 200, counts.text
    assert counts.json() == sql_counts(wid)

    # One open SLA-backed ticket is genuinely overdue in the database.
    overdue = db_session.execute(
        select(support.Ticket).where(
            support.Ticket.workspace_id == wid, support.Ticket.subject.startswith("Open")
        ).limit(1)
    ).scalar_one()
    overdue.first_response_due_at = now() - timedelta(hours=1)
    db_session.commit()
    overview = client.get(base + "/reports/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    data = overview.json()
    for key, value in sql_counts(wid).items():
        assert data[key] == value, (key, data[key], value)
    assert data["sla_breaches"] == db_session.execute(
        select(func.count(support.Ticket.id)).where(
            support.Ticket.workspace_id == wid,
            support.Ticket.status.in_(("open", "pending")),
            support.Ticket.first_response_due_at.is_not(None),
            support.Ticket.first_response_due_at < now(),
        )
    ).scalar_one() == 1
    assert data["teams"] == db_session.execute(
        select(func.count(support.SupportTeam.id)).where(support.SupportTeam.workspace_id == wid)
    ).scalar_one()
    assert data["labels"] == db_session.execute(
        select(func.count(support.SupportLabel.id)).where(support.SupportLabel.workspace_id == wid)
    ).scalar_one()
    assert data["inboxes"] == db_session.execute(
        select(func.count(support.SupportInbox.id)).where(support.SupportInbox.workspace_id == wid)
    ).scalar_one()

    assert counts.json() != client.get(_base(other_wid) + "/counts",
                                        headers=other_headers).json()
    assert client.get(base + "/counts", headers=other_headers).status_code == 403
    assert client.get(base + "/reports/overview", headers=other_headers).status_code == 403
    assert client.get(_base(other_wid) + "/reports/overview", headers=headers).status_code == 403
    read_headers, _ = _member(client, wid, headers, "cw093-read@example.com", "read_only")
    assert client.get(base + "/counts", headers=read_headers).json() == counts.json()


# ---------------------------------------------------------------------------
# CW-095 — conversation volume and response metrics
# ---------------------------------------------------------------------------


def test_cw095_conversation_metrics_come_from_rows_and_honour_date_filters(client, db_session):
    """CW-095: volume, first response and resolution averages are computed from real rows."""
    wid, headers, _ = _setup(client, "CW095", "cw095-owner@example.com")
    base = _base(wid)
    other_wid, other_headers = _other(client, headers)
    first = _ticket(client, wid, headers, subject="First", body="Older")
    second = _ticket(client, wid, headers, subject="Second", body="Newer")
    base_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)
    _touch(db_session, support.Ticket, first["id"],
           created_at=base_time, updated_at=base_time)
    _touch(db_session, support.Ticket, second["id"],
           created_at=base_time + timedelta(hours=1),
           updated_at=base_time + timedelta(hours=1))

    m1 = client.post(base + f"/{first['id']}/messages", headers=headers,
                     json={"body": "First reply", "direction": "outbound"})
    assert m1.status_code == 201, m1.text
    m1b = client.post(base + f"/{first['id']}/messages", headers=headers,
                      json={"body": "Later reply", "direction": "outbound"})
    assert m1b.status_code == 201, m1b.text
    m2 = client.post(base + f"/{second['id']}/messages", headers=headers,
                     json={"body": "Second reply", "direction": "outbound"})
    assert m2.status_code == 201, m2.text
    _touch(db_session, support.TicketMessage, m1.json()["id"],
           created_at=base_time + timedelta(minutes=30))
    _touch(db_session, support.TicketMessage, m1b.json()["id"],
           created_at=base_time + timedelta(minutes=90))
    _touch(db_session, support.TicketMessage, m2.json()["id"],
           created_at=base_time + timedelta(hours=1, minutes=15))

    resolved = client.patch(base + f"/{first['id']}", headers=headers, json={"status": "resolved"})
    assert resolved.status_code == 200, resolved.text
    resolution = [e for e in _events(db_session, wid, support.TICKET_STATUS_CHANGED)
                  if e.correlation_id == first["id"]]
    assert len(resolution) == 1
    _touch(db_session, Event, resolution[0].id,
           occurred_at=base_time + timedelta(minutes=60))
    db_session.commit()

    report = client.get(base + "/reports/conversations", headers=headers)
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["volume"] == 2
    assert data["by_status"] == {"open": 1, "resolved": 1}
    assert data["by_channel"] == {"local": 2}
    assert data["first_response_samples"] == 2
    assert data["first_response_minutes"] == 22.5
    assert data["resolution_samples"] == 1
    assert data["resolution_minutes"] == 60.0

    narrowed = client.get(base + "/reports/conversations", headers=headers, params={
        "created_from": (base_time + timedelta(minutes=30)).isoformat(),
        "created_to": (base_time + timedelta(minutes=90)).isoformat(),
    })
    assert narrowed.status_code == 200, narrowed.text
    assert narrowed.json()["volume"] == 1
    assert narrowed.json()["first_response_minutes"] == 15.0
    assert narrowed.json()["first_response_samples"] == 1
    assert narrowed.json()["resolution_samples"] == 0

    assert client.get(base + "/reports/conversations", headers=headers,
                      params={"created_from": (base_time + timedelta(hours=10)).isoformat(),
                              "created_to": (base_time + timedelta(hours=11)).isoformat()}
                      ).json()["volume"] == 0
    assert client.get(base + "/reports/conversations", headers=headers,
                      params={"created_from": "not-a-date"}).status_code == 422
    assert client.get(base + "/reports/conversations", headers=headers,
                      params={"created_from": (base_time + timedelta(hours=2)).isoformat(),
                              "created_to": base_time.isoformat()}).status_code == 422

    foreign = _ticket(client, other_wid, other_headers, subject="Foreign", body="Ignore")
    client.post(_base(other_wid) + f"/{foreign['id']}/messages", headers=other_headers,
                json={"body": "Foreign reply", "direction": "outbound"})
    assert client.get(_base(other_wid) + "/reports/conversations",
                      headers=other_headers).json()["volume"] == 1
    assert client.get(base + "/reports/conversations", headers=headers).json()["volume"] == 2
    assert client.get(base + "/reports/conversations", headers=other_headers).status_code == 403
    read_headers, _ = _member(client, wid, headers, "cw095-read@example.com", "read_only")
    assert client.get(base + "/reports/conversations", headers=read_headers).status_code == 200


# ---------------------------------------------------------------------------
# CW-100 — CSAT average and response rate
# ---------------------------------------------------------------------------


def test_cw100_csat_average_and_response_rate_use_stored_responses_and_filters(client, db_session):
    """CW-100: CSAT figures are computed from stored scores with date and inbox filters."""
    wid, headers, _ = _setup(client, "CW100", "cw100-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    other_wid, other_headers = _other(client, headers)
    inbox_a = client.post(base + "/inboxes", headers=headers,
                          json={"name": "Chat", "channel": "web_form", "slug": "chat"})
    assert inbox_a.status_code == 201, inbox_a.text
    inbox_a_id = inbox_a.json()["id"]
    inbox_b = client.post(base + "/inboxes", headers=headers,
                          json={"name": "Mail", "channel": "email", "slug": "mail"})
    assert inbox_b.status_code == 201, inbox_b.text
    inbox_b_id = inbox_b.json()["id"]

    t1 = _ticket(client, wid, headers, subject="A", body="One", inbox_id=inbox_a_id)
    t2 = _ticket(client, wid, headers, subject="B", body="Two", inbox_id=inbox_b_id)
    t3 = _ticket(client, wid, headers, subject="C", body="Three", inbox_id=inbox_a_id)
    for ticket in (t1, t2, t3):
        assert client.patch(base + f"/{ticket['id']}", headers=headers,
                            json={"status": "resolved"}).status_code == 200
    score1 = client.post(base + "/csat", headers=headers,
                         json={"ticket_id": t1["id"], "score": 5, "comment": "Great"})
    assert score1.status_code == 201, score1.text
    assert client.post(base + "/csat", headers=headers,
                       json={"ticket_id": t2["id"], "score": 3}).status_code == 201
    assert client.post(base + "/csat", headers=headers,
                       json={"ticket_id": t3["id"], "score": 9}).status_code == 422

    report = client.get(base + "/reports/csat", headers=headers)
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["responses"] == 2 and data["eligible_tickets"] == 3
    assert data["average_score"] == 4.0 and data["response_rate"] == 0.6667
    assert any(c["ticket_id"] == t1["id"] and c["comment"] == "Great"
               for c in data["comments"])

    sql_scores = db_session.execute(
        select(func.count(), func.avg(support.Csatscore.score)).where(
            support.Csatscore.workspace_id == wid
        )
    ).one()
    assert sql_scores[0] == 2 and sql_scores[1] == 4.0
    assert db_session.execute(
        select(func.count()).select_from(support.Ticket).where(
            support.Ticket.workspace_id == wid,
            support.Ticket.status.in_(("resolved", "closed")),
        )
    ).scalar_one() == 3

    by_inbox = client.get(base + "/reports/csat", headers=headers,
                          params={"inbox_id": inbox_a_id})
    assert by_inbox.status_code == 200, by_inbox.text
    assert (by_inbox.json()["responses"], by_inbox.json()["eligible_tickets"],
            by_inbox.json()["average_score"]) == (1, 2, 5.0)
    assert client.get(base + "/reports/csat", headers=headers,
                      params={"inbox_id": "not-an-inbox"}).status_code == 404
    member_headers, _ = _member(client, wid, headers, "cw100-agent@example.com", "support")
    assert client.get(base + "/reports/csat", headers=member_headers,
                      params={"inbox_id": inbox_a_id}).status_code == 403

    # Date filters apply to both score rows and their tickets.
    old_ticket = db_session.execute(
        select(support.Ticket).where(support.Ticket.id == t1["id"])
    ).scalar_one()
    old_score = db_session.execute(
        select(support.Csatscore).where(support.Csatscore.ticket_id == t1["id"])
    ).scalar_one()
    older = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
    _touch(db_session, support.Ticket, old_ticket.id, created_at=older, updated_at=older)
    _touch(db_session, support.Csatscore, old_score.id, created_at=older)
    db_session.commit()
    filtered = client.get(base + "/reports/csat", headers=headers, params={
        "created_from": (older - timedelta(hours=1)).isoformat(),
        "created_to": (older + timedelta(hours=1)).isoformat(),
    })
    assert filtered.status_code == 200, filtered.text
    assert (filtered.json()["responses"], filtered.json()["eligible_tickets"],
            filtered.json()["average_score"], filtered.json()["response_rate"]) == (1, 1, 5.0, 1.0)
    assert client.get(base + "/reports/csat", headers=headers,
                      params={"created_from": "bad-date"}).status_code == 422

    assert client.get(base + "/reports/csat", headers=other_headers).status_code == 403
    assert client.get(_base(other_wid) + "/reports/csat",
                      headers=other_headers).json()["responses"] == 0
    assert db_session.execute(
        select(func.count()).select_from(support.Csatscore).where(
            support.Csatscore.workspace_id == other_wid
        )
    ).scalar_one() == 0
    assert owner_id == _me(client, headers)["user"]["id"]
    read_headers, _ = _member(client, wid, headers, "cw100-read@example.com", "read_only")
    assert client.get(base + "/reports/csat", headers=read_headers).status_code == 200


# ---------------------------------------------------------------------------
# CW-102 — local survey on resolution
# ---------------------------------------------------------------------------


def test_cw102_resolution_creates_one_local_survey_and_no_message(client, db_session):
    """CW-102: resolving a ticket creates exactly one local survey, never an outbound message."""
    wid, headers, _ = _setup(client, "CW102", "cw102-owner@example.com")
    base = _base(wid)
    owner_id = _me(client, headers)["user"]["id"]
    other_wid, other_headers = _other(client, headers)
    inbox = client.post(base + "/inboxes", headers=headers,
                        json={"name": "Survey inbox", "channel": "local", "slug": "survey-inbox"})
    assert inbox.status_code == 201, inbox.text
    ticket = _ticket(client, wid, headers, subject="Resolve me", body="Body",
                     inbox_id=inbox.json()["id"])
    assert client.get(base + "/csat-surveys", headers=headers).json() == []

    resolved = client.patch(base + f"/{ticket['id']}", headers=headers, json={"status": "resolved"})
    assert resolved.status_code == 200 and resolved.json()["status"] == "resolved", resolved.text
    surveys = client.get(base + "/csat-surveys", headers=headers)
    assert surveys.status_code == 200 and len(surveys.json()) == 1, surveys.text
    survey = surveys.json()[0]
    assert survey["ticket_id"] == ticket["id"] and survey["status"] == "pending"

    for payload in ({"status": "resolved"}, {"status": "closed"}, {"status": "resolved"}):
        assert client.patch(base + f"/{ticket['id']}", headers=headers,
                            json=payload).status_code == 200
    assert len(client.get(base + "/csat-surveys", headers=headers).json()) == 1

    events = [e for e in _events(db_session, wid, support.CSAT_SURVEY_CREATED)
              if e.entity_id == survey["id"]]
    assert len(events) == 1
    assert events[0].correlation_id == ticket["id"]
    assert events[0].payload["external_delivery"] is False
    assert _actor(events[0]) == owner_id
    assert db_session.execute(
        select(func.count()).select_from(support.CsatSurvey).where(
            support.CsatSurvey.workspace_id == wid, support.CsatSurvey.ticket_id == ticket["id"]
        )
    ).scalar_one() == 1
    assert client.get(base + f"/{ticket['id']}/messages", headers=headers).json() == []
    assert db_session.execute(
        select(func.count()).select_from(support.TicketMessage).where(
            support.TicketMessage.workspace_id == wid
        )
    ).scalar_one() == 0

    foreign = _ticket(client, other_wid, other_headers, subject="Foreign", body="Body")
    assert client.patch(_base(other_wid) + f"/{foreign['id']}", headers=other_headers,
                        json={"status": "resolved"}).status_code == 200
    assert len(client.get(_base(other_wid) + "/csat-surveys",
                          headers=other_headers).json()) == 1
    assert len(client.get(base + "/csat-surveys", headers=headers).json()) == 1
    assert client.get(base + "/csat-surveys", headers=other_headers).status_code == 403
    assert client.patch(base + f"/{ticket['id']}", headers=other_headers,
                        json={"status": "resolved"}).status_code == 403
    read_headers, _ = _member(client, wid, headers, "cw102-read@example.com", "read_only")
    assert client.get(base + "/csat-surveys", headers=read_headers).status_code == 200
    assert client.patch(base + f"/{ticket['id']}", headers=read_headers,
                        json={"status": "closed"}).status_code == 403


# ---------------------------------------------------------------------------
# CW-118 — token scope, rotation and revocation
# ---------------------------------------------------------------------------


def test_cw118_token_scope_rotation_and_revocation_take_effect_immediately(client, db_session):
    """CW-118: server-side session scope is enforced; rotation and revocation are immediate.

    Native NOVARA bearer sessions carry their workspace and role on the server.
    This verifies those two scopes on the real support API, plus rotation and
    revocation. It does not claim separate agent-bot/platform token types exist.
    """
    wid, headers, tokens = _setup(client, "CW118", "cw118-owner@example.com")
    base = _base(wid)
    access = tokens["access_token"]
    owner_id = _me(client, headers)["user"]["id"]
    assert db_session.execute(
        select(Session).where(Session.access_token_hash.is_not(None))
    ).scalars().all()

    ticket = _ticket(client, wid, headers, subject="Scoped", body="Server-side scope")
    read_headers, read_id = _member(client, wid, headers, "cw118-read@example.com", "read_only")
    assert read_id != owner_id
    assert client.get(base, headers=read_headers).status_code == 200
    denied = client.post(base, headers=read_headers,
                         json={"subject": "Denied", "body": "No note:write"})
    assert denied.status_code == 403, denied.text
    assert client.get(f"{API}/auth/me", headers=read_headers).json()["role"] == "read_only"

    other_wid, other_headers = _other(client, headers)
    assert client.get(base, headers=other_headers).status_code == 403
    assert client.get(_base(other_wid), headers=headers).status_code == 403
    assert client.get(base + f"/{ticket['id']}", headers=other_headers).status_code == 403

    rotated = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert rotated.status_code == 200, rotated.text
    new_access = rotated.json()["access_token"]
    assert new_access != access
    assert client.get(f"{API}/auth/me", headers=auth(access)).status_code == 401
    assert client.get(base, headers=auth(access)).status_code == 401
    assert client.get(base, headers=auth(new_access)).status_code == 200
    assert client.post(f"{API}/auth/refresh",
                       json={"refresh_token": tokens["refresh_token"]}).status_code == 401

    new_headers = auth(new_access)
    revoked = client.post(f"{API}/auth/logout", headers=new_headers)
    assert revoked.status_code == 200 and revoked.json()["revoked"] is True, revoked.text
    assert client.get(f"{API}/auth/me", headers=new_headers).status_code == 401
    assert client.get(base, headers=new_headers).status_code == 401
    assert client.post(f"{API}/auth/refresh",
                       json={"refresh_token": rotated.json()["refresh_token"]}).status_code == 401
    # The read-only member's independent session remains valid: revocation is per token.
    assert client.get(base, headers=read_headers).status_code == 200
    assert db_session.execute(
        select(Session).where(Session.access_token_hash.is_not(None),
                              Session.revoked_at.is_not(None))
    ).scalars().all()


# ---------------------------------------------------------------------------
# CW-158 — fresh schema
# ---------------------------------------------------------------------------


def test_cw158_fresh_schema_creates_every_support_table_and_workspace_fk():
    """CW-158: a fresh database is created from metadata with every named support table/FK."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    try:
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected_columns = {
            "support_tickets": {"id", "workspace_id", "contact_id", "subject", "body",
                                "status", "priority", "assignee_id", "team_id", "inbox_id"},
            "ticket_messages": {"id", "workspace_id", "ticket_id", "author_id", "body",
                                "direction", "channel", "is_internal"},
            "ticket_internal_notes": {"id", "workspace_id", "ticket_id", "author_id", "body"},
            "saved_replies": {"id", "workspace_id", "name", "body", "created_by"},
            "macros": {"id", "workspace_id", "name", "actions", "created_by"},
            "sla_policies": {"id", "workspace_id", "name", "first_response_minutes",
                             "resolution_minutes", "business_hours_only"},
            "business_hours": {"id", "workspace_id", "name", "timezone", "start_hour",
                               "end_hour", "days"},
            "escalation_rules": {"id", "workspace_id", "name", "condition", "action", "enabled"},
            "csat_scores": {"id", "workspace_id", "ticket_id", "score", "comment"},
            "support_teams": {"id", "workspace_id", "name", "description", "created_by"},
            "support_team_members": {"id", "workspace_id", "team_id", "user_id"},
            "support_labels": {"id", "workspace_id", "name", "color", "created_by"},
            "ticket_labels": {"id", "workspace_id", "ticket_id", "label_id"},
            "support_custom_attributes": {"id", "workspace_id", "key", "label",
                                          "value_type", "target"},
            "support_custom_attribute_values": {"id", "workspace_id", "attribute_id",
                                                "entity_type", "entity_id", "value"},
            "support_inboxes": {"id", "workspace_id", "name", "channel", "slug",
                                "csat_enabled"},
            "support_inbox_agents": {"id", "workspace_id", "inbox_id", "user_id"},
            "support_routing_rules": {"id", "workspace_id", "name", "channel", "strategy",
                                      "team_id", "assignee_id", "enabled", "priority"},
            "support_conversation_rules": {"id", "workspace_id", "name", "trigger",
                                           "actions", "enabled"},
            "support_conversation_rule_runs": {"id", "workspace_id", "rule_id", "ticket_id",
                                               "trigger", "changes", "actor_id"},
            "support_contact_segments": {"id", "workspace_id", "name", "definition"},
            "support_help_portals": {"id", "workspace_id", "name", "slug"},
            "support_help_articles": {"id", "workspace_id", "portal_id", "title", "slug",
                                      "body", "audience", "status", "published_at"},
            "support_csat_surveys": {"id", "workspace_id", "ticket_id", "status"},
        }
        missing = sorted(set(expected_columns) - tables)
        assert not missing, f"support tables missing from fresh schema: {missing}"

        for name, columns in expected_columns.items():
            actual = {column["name"] for column in inspector.get_columns(name)}
            assert columns <= actual, f"{name} missing columns: {sorted(columns - actual)}"
            assert "workspace_id" in actual, f"{name} has no workspace_id"
            fks = inspector.get_foreign_keys(name)
            assert any(
                fk["referred_table"] == "workspaces"
                and "workspace_id" in fk["constrained_columns"]
                for fk in fks
            ), f"{name} has no workspace foreign key"

        # The shared workspaces table itself exists, so those FKs are satisfiable.
        assert "workspaces" in tables
        assert support.Ticket.__tablename__ == "support_tickets"
        assert support.SupportTeam.__tablename__ == "support_teams"
        assert support.CsatSurvey.__tablename__ == "support_csat_surveys"
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as db:
            assert db.execute(select(func.count()).select_from(support.Ticket)).scalar_one() == 0
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# CW-166 — signed local inbound webhook
# ---------------------------------------------------------------------------


def test_cw166_unsigned_or_replayed_webhook_rejected_and_valid_event_creates_one_ticket(
    client, db_session
):
    """CW-166: signed local webhooks reject bad/stale/replayed events and create one ticket.

    Local contract: POST {base}/webhooks/inbound with headers ``X-Timestamp``
    (unix seconds) and ``X-Signature: sha256=<hex>``, where the hex is
    HMAC-SHA256 over ``"<timestamp>.<raw JSON body>"`` using the support module's
    documented local secret ``support.WEBHOOK_SECRET``. All checks are local;
    no provider is called.
    """
    wid, headers, _ = _setup(client, "CW166", "cw166-owner@example.com")
    base = _base(wid)
    url = base + "/webhooks/inbound"
    payload = {"event": "ticket.created", "external_id": "cw166-1",
               "subject": "Inbound", "body": "From a signed source"}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = int(time.time())

    def signed_headers(ts, body=raw):
        digest = hmac.new(
            support.WEBHOOK_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256
        ).hexdigest()
        return {"Content-Type": "application/json", "X-Timestamp": str(ts),
                "X-Signature": f"sha256={digest}"}

    def ticket_count(workspace_id):
        return db_session.execute(
            select(func.count()).select_from(support.Ticket).where(
                support.Ticket.workspace_id == workspace_id
            )
        ).scalar_one()

    # Unsigned, forged, tampered and stale events never reach the write path.
    assert client.post(url, content=raw,
                       headers={"Content-Type": "application/json"}).status_code == 401
    bad = signed_headers(timestamp)
    bad["X-Signature"] = "sha256=bad"
    assert client.post(url, content=raw, headers=bad).status_code == 401
    tampered = raw.replace(b"From a signed source", b"Tampered source")
    assert client.post(url, content=tampered, headers=signed_headers(timestamp)).status_code == 401
    stale = timestamp - support.WEBHOOK_TOLERANCE_SECONDS - 60
    assert client.post(url, content=raw, headers=signed_headers(stale)).status_code == 401
    assert ticket_count(wid) == 0

    accepted = client.post(url, content=raw, headers=signed_headers(timestamp))
    assert accepted.status_code == 201, accepted.text
    result = accepted.json()
    ticket_id = result["ticket_id"]
    assert result["external_id"] == payload["external_id"] and result["created"] is True
    assert ticket_count(wid) == 1
    row = db_session.execute(
        select(support.Ticket).where(support.Ticket.id == ticket_id)
    ).scalar_one()
    assert row.workspace_id == wid and row.subject == payload["subject"]
    assert row.body == payload["body"] and row.origin_channel == "import"

    created_events = _events(db_session, wid, support.TICKET_CREATED)
    assert len(created_events) == 1
    assert created_events[0].entity_id == ticket_id
    assert created_events[0].correlation_id == ticket_id
    assert created_events[0].idempotency_key == (
        f"webhook:ticket.created:{wid}:{payload['external_id']}"
    )
    assert created_events[0].payload["source"] == "webhook"
    assert created_events[0].payload["external_delivery"] is False

    # A replayed external id is rejected even with a fresh valid signature.
    replay = client.post(url, content=raw, headers=signed_headers(timestamp + 1))
    assert replay.status_code == 409, replay.text
    assert ticket_count(wid) == 1
    assert len(_events(db_session, wid, support.TICKET_CREATED)) == 1

    # The same external id in another workspace is a distinct local event.
    other_wid, _ = _other(client, headers)
    other = client.post(_base(other_wid) + "/webhooks/inbound",
                        content=raw, headers=signed_headers(timestamp))
    assert other.status_code == 201, other.text
    assert ticket_count(other_wid) == 1 and ticket_count(wid) == 1
    assert client.get(_base(wid) + f"/{other.json()['ticket_id']}",
                      headers=headers).status_code == 404
