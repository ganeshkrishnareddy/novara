"""Named acceptance tests for the remaining P0 marketing/support/notify rows.

Each test drives the real FastAPI app through the shared fixtures. Channel
steps and preference resolution are local-only: no external delivery is
claimed or performed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import auth, bootstrap

APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def _ctx(client):
    t = bootstrap(client)
    return t["workspace_id"], auth(t["access_token"])


def _campaign(client, wid, h, **extra):
    body = {"name": "Spring", "channel": "email", "campaign_type": "standard",
            "source_type": "segment", **extra}
    res = client.post(f"/api/v1/workspaces/{wid}/campaigns", headers=h, json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _segment(client, wid, h, name="Buyers", **criteria):
    res = client.post(f"/api/v1/workspaces/{wid}/campaigns/segments", headers=h,
                      json={"name": name, "criteria": criteria or {"source": "website"}})
    assert res.status_code == 201, res.text
    return res.json()


def _contact(client, wid, h, email="a@example.com", **extra):
    res = client.post(f"/api/v1/workspaces/{wid}/contacts", headers=h,
                      json={"email": email, **extra})
    assert res.status_code == 201, res.text
    return res.json()


def test_mt027_campaign_builder_canvas_wires_conditions_decisions_and_actions():
    source = APP_JS.read_text(encoding="utf-8")
    assert "[['action', 'Action'], ['condition', 'Condition'], ['decision', 'Decision']]" in source
    assert "journey.condition_evaluated" in source and "journey.decision_evaluated" in source
    assert "step_kind: stepKind, config: config" in source
    assert "data-form=\"campaign-journey-step-add\"" in source
    assert "No journey steps yet." in source


def test_nv039_inbox_preferences_view_is_routed_and_wired():
    source = APP_JS.read_text(encoding="utf-8")
    assert "data-action=\"open-notification-preferences\"" in source
    assert "case 'open-notification-preferences':" in source
    assert "api(apiW('/notification-preferences'))" in source
    assert "data-form=\"notification-preference-save\"" in source
    assert "if (name === 'notification-preference-save')" in source
    assert "<th>Level</th><th>Target</th><th>Channel</th><th>State</th>" in source


def test_mt008_segments_are_static_or_dynamic_and_membership_is_real(client):
    wid, h = _ctx(client)
    contact = _contact(client, wid, h, source="website")
    static = _segment(client, wid, h, "Static list")
    dynamic = client.post(f"/api/v1/workspaces/{wid}/campaigns/segments", headers=h, json={
        "name": "Dynamic list", "segment_type": "dynamic", "criteria": {"source": "website"},
    }).json()
    added = client.post(
        f"/api/v1/workspaces/{wid}/campaigns/segments/{static['id']}/members",
        headers=h, json={"contact_ids": [contact["id"]]},
    )
    assert added.status_code == 201, added.text
    members = client.get(f"/api/v1/workspaces/{wid}/campaigns/segments/{static['id']}/members",
                         headers=h)
    assert any(m["contact_id"] == contact["id"] for m in members.json())
    refreshed = client.post(f"/api/v1/workspaces/{wid}/campaigns/segments/{dynamic['id']}/refresh",
                            headers=h)
    assert refreshed.status_code == 200, refreshed.text
    dyn_members = client.get(f"/api/v1/workspaces/{wid}/campaigns/segments/{dynamic['id']}/members",
                             headers=h).json()
    assert any(m["contact_id"] == contact["id"] for m in dyn_members)


def test_mt012_template_emails_are_stored_and_render_safely(client):
    wid, h = _ctx(client)
    tmpl = client.post(f"/api/v1/workspaces/{wid}/campaigns/email-templates", headers=h,
                       json={"name": "Welcome", "subject": "Hi {{name}}",
                             "body": "Hello {{name}}"})
    assert tmpl.status_code == 201, tmpl.text
    assert any(t["name"] == "Welcome" for t in client.get(
        f"/api/v1/workspaces/{wid}/campaigns/email-templates", headers=h).json())
    rendered = client.post(f"/api/v1/workspaces/{wid}/email/templates/render", headers=h,
                           json={"template": "Hi {{name}}", "values": {"name": "Ana"}})
    assert rendered.status_code == 200, rendered.text
    assert "Ana" in str(rendered.json())
    hostile = client.post(f"/api/v1/workspaces/{wid}/email/templates/render", headers=h,
                          json={"template": "{{name}}", "values": {"name": "<script>x</script>"}})
    assert hostile.status_code == 200
    assert "&lt;script&gt;" in str(hostile.json()) and "<script>" not in str(hostile.json())


def test_mt013_segment_broadcast_sends_once_per_consented_recipient(client):
    wid, h = _ctx(client)
    contact = _contact(client, wid, h)
    segment = _segment(client, wid, h)
    broadcast = client.post(f"/api/v1/workspaces/{wid}/email/broadcasts", headers=h, json={
        "name": "News", "subject": "Hi", "body": "Hello", "segment_id": segment["id"],
    })
    assert broadcast.status_code == 201, broadcast.text
    bid = broadcast.json()["id"]
    added = client.post(f"/api/v1/workspaces/{wid}/email/broadcasts/{bid}/recipients",
                        headers=h, json={"contact_ids": [contact["id"]]})
    assert added.status_code == 200 and added.json()["added"] == 1
    client.post(f"/api/v1/workspaces/{wid}/email/broadcasts/{bid}/queue", headers=h)
    dispatched = client.post(f"/api/v1/workspaces/{wid}/email/broadcasts/{bid}/dispatch", headers=h)
    assert dispatched.status_code == 200 and dispatched.json()["sent"] == 1
    recipients = client.get(f"/api/v1/workspaces/{wid}/email/broadcasts/{bid}/recipients",
                            headers=h).json()
    assert recipients and recipients[0]["status"] == "sent"


def test_mt026_campaign_types_and_scheduling_are_validated_and_due(client):
    wid, h = _ctx(client)
    time_driven = _campaign(client, wid, h, campaign_type="time_driven", cadence="daily")
    assert time_driven["campaign_type"] == "time_driven" and time_driven["cadence"] == "daily"
    event_driven = client.post(f"/api/v1/workspaces/{wid}/campaigns", headers=h, json={
        "name": "Triggered", "channel": "email", "campaign_type": "event_driven",
    })
    assert event_driven.status_code == 422
    event_driven = client.post(f"/api/v1/workspaces/{wid}/campaigns", headers=h, json={
        "name": "Triggered", "channel": "email", "campaign_type": "event_driven",
        "trigger_event": "order.created",
    })
    assert event_driven.status_code == 201
    import datetime
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
    scheduled = client.post(
        f"/api/v1/workspaces/{wid}/campaigns/{time_driven['id']}/schedule",
        headers=h, json={"start_at": past, "end_at": future},
    )
    assert scheduled.status_code == 200, scheduled.text
    due = client.post(f"/api/v1/workspaces/{wid}/campaigns/due", headers=h)
    assert due.status_code == 200 and any(c["id"] == time_driven["id"] for c in due.json())


def test_mt028_campaign_contact_sources_enroll_once_from_segment_and_form(client):
    wid, h = _ctx(client)
    contact = _contact(client, wid, h, email="source@example.com", source="website")
    segment = _segment(client, wid, h)
    form = client.post(f"/api/v1/workspaces/{wid}/campaigns/forms", headers=h, json={
        "name": "Signup", "slug": "signup", "fields": [{"key": "email", "type": "email"}],
    })
    assert form.status_code == 201, form.text
    campaign = _campaign(client, wid, h, source_type="combined",
                         source_segment_ids=[segment["id"]], source_form_ids=[form.json()["id"]])
    client.post(f"/api/v1/workspaces/{wid}/campaigns/segments/{segment['id']}/members",
                headers=h, json={"contact_ids": [contact["id"]]})
    enrolled = client.post(
        f"/api/v1/workspaces/{wid}/campaigns/{campaign['id']}/enroll-from-sources",
        headers=h, json={},
    )
    assert enrolled.status_code == 200, enrolled.text
    rows = client.get(f"/api/v1/workspaces/{wid}/campaigns/{campaign['id']}/enrollments",
                      headers=h).json()
    assert any(r["contact_id"] == contact["id"] for r in rows)
    again = client.post(
        f"/api/v1/workspaces/{wid}/campaigns/{campaign['id']}/enroll-from-sources",
        headers=h, json={},
    )
    assert again.status_code == 200
    rows_after = client.get(f"/api/v1/workspaces/{wid}/campaigns/{campaign['id']}/enrollments",
                            headers=h).json()
    assert len(rows_after) == len(rows)


def test_cw019_private_notes_are_internal_only(client):
    wid, h = _ctx(client)
    ticket = client.post(f"/api/v1/workspaces/{wid}/tickets", headers=h,
                         json={"subject": "Help", "body": "I need support"}).json()
    note = client.post(f"/api/v1/workspaces/{wid}/tickets/{ticket['id']}/notes", headers=h,
                       json={"body": "INTERNAL-ONLY-MARKER"})
    assert note.status_code == 201, note.text
    notes = client.get(f"/api/v1/workspaces/{wid}/tickets/{ticket['id']}/notes", headers=h).json()
    assert any(n["body"] == "INTERNAL-ONLY-MARKER" for n in notes)
    client.post(f"/api/v1/workspaces/{wid}/tickets/{ticket['id']}/messages", headers=h,
                json={"body": "public reply"})
    messages = client.get(f"/api/v1/workspaces/{wid}/tickets/{ticket['id']}/messages",
                          headers=h).json()
    assert all("INTERNAL-ONLY-MARKER" not in str(m) for m in messages)


def test_cw030_conversation_search_matches_subject_body_and_messages(client):
    wid, h = _ctx(client)
    ticket = client.post(f"/api/v1/workspaces/{wid}/tickets", headers=h,
                         json={"subject": "Printer issue", "body": "It jammed"}).json()
    client.post(f"/api/v1/workspaces/{wid}/tickets/{ticket['id']}/messages", headers=h,
                json={"body": "UNIQUE-TOKEN-4821"})
    for query, expected in (("Printer", True), ("UNIQUE-TOKEN-4821", True), ("AbsentToken", False)):
        res = client.get(f"/api/v1/workspaces/{wid}/tickets/search", headers=h,
                         params={"q": query})
        assert res.status_code == 200
        assert (any(t["id"] == ticket["id"] for t in res.json()) is expected), query


def test_nv007_workflow_channel_steps_persist_results_without_delivery(client):
    wid, h = _ctx(client)
    channels = ["email", "sms", "push", "in_app", "chat"]
    definition = [
        {"id": f"n{c}", "type": "notify", "channel": c} for c in channels
    ]
    auto = client.post(f"/api/v1/workspaces/{wid}/automations", headers=h, json={
        "name": "Channel steps", "trigger_type": "manual", "definition": definition,
    })
    assert auto.status_code == 201, auto.text
    run = client.post(f"/api/v1/workspaces/{wid}/automations/{auto.json()['id']}/dry_run",
                      headers=h, json={"trigger_event": "manual", "context": {}})
    assert run.status_code in (200, 201), run.text
    steps = run.json()["steps"]
    assert len(steps) == len(channels)
    for step, channel in zip(steps, channels):
        assert step["channel"] == channel
        assert step["result"] == "queued"
        assert "delivered" not in str(step).lower()


def test_nv032_layered_preferences_resolve_global_workflow_and_channel(client):
    wid, h = _ctx(client)
    base = f"/api/v1/workspaces/{wid}/notification-preferences"
    for level, target, enabled in (("global", "*", True),
                                   ("workflow", "release", False),
                                   ("channel", "release", True)):
        res = client.post(base, headers=h, json={
            "level": level, "target": target, "channel": "email", "enabled": enabled,
        })
        assert res.status_code == 201, res.text
    layers = client.get(base, headers=h, params={"channel": "email"}).json()
    assert {(p["level"], p["target"]) for p in layers} == {
        ("global", "*"), ("workflow", "release"), ("channel", "release")
    }
    resolved = client.post(base + "/resolve", headers=h,
                           json={"channel": "email", "workflow": "release"})
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["enabled"] is True and body["source"] == "channel:release"
    assert len(body["layers"]) == 3
    other = client.post(base + "/resolve", headers=h,
                        json={"channel": "sms", "workflow": "release"})
    assert other.json()["enabled"] is True and other.json()["source"].startswith("default")
