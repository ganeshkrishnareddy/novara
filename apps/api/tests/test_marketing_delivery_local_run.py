"""Acceptance tests for the workable, approval-gated local marketing workflow.

Every assertion is backed by records in the isolated test database. The local
delivery adapter is asserted to be local-only: it never claims an external send.
"""

from __future__ import annotations

from pathlib import Path

from .conftest import auth, bootstrap

SITE_HTML = Path(__file__).resolve().parents[3] / "site" / "index.html"
APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def _ctx(client):
    token = bootstrap(client)
    return token["workspace_id"], auth(token["access_token"])


def _contact(client, wid, h, email):
    response = client.post(
        f"/api/v1/workspaces/{wid}/contacts", headers=h, json={"email": email}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _run(client, wid, h, contact_ids, correlation_id="qa-marketing-01"):
    response = client.post(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs",
        headers=h,
        json={
            "name": "Local product update",
            "subject": "A note from NOVARA",
            "body": "This is a local simulation. Nothing was sent externally.",
            "contact_ids": contact_ids,
            "channel": "email",
            "correlation_id": correlation_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_marketing_run_is_workable_from_audience_to_analytics(client):
    wid, h = _ctx(client)
    one = _contact(client, wid, h, "one@qa.test")
    two = _contact(client, wid, h, "two@qa.test")

    created = _run(client, wid, h, [one["id"], two["id"]])
    assert created["status"] == "awaiting_approval"
    assert created["steps"]["audience"] == {"status": "recorded", "count": 2}
    assert created["steps"]["campaign"]["status"] == "recorded"
    assert created["steps"]["approval"]["status"] == "awaiting_approval"
    assert created["steps"]["delivery"]["status"] == "pending"
    assert created["steps"]["delivery"]["local_only"] is True

    before = client.get(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs/{created['id']}", headers=h
    ).json()
    assert before["deliveries"] == []
    assert "marketing.run_created" in [e["event_type"] for e in before["events"]]

    approved = client.post(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs/{created['id']}/approve",
        headers=h,
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "executed"
    assert body["counts"]["delivered"] == 2
    assert body["steps"]["delivery"]["external_delivery"] is False
    assert body["steps"]["analytics"]["status"] == "recorded"
    assert body["steps"]["analytics"]["events"] == body["counts"]["events"]

    trace = client.get(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs/{created['id']}", headers=h
    ).json()
    assert len(trace["recipients"]) == 2
    assert all(r["status"] == "sent" for r in trace["recipients"])
    assert len(trace["deliveries"]) == 2
    assert all(d["detail"]["local_only"] is True for d in trace["deliveries"])
    assert all(d["detail"]["external_delivery"] is False for d in trace["deliveries"])
    events = [e["event_type"] for e in trace["events"]]
    for expected in (
        "marketing.run_created",
        "marketing.run_approved",
        "broadcast.queued",
        "broadcast.sent",
        "marketing.local_delivered",
        "marketing.analytics_recorded",
    ):
        assert expected in events
    assert len({e["seq"] for e in trace["events"]}) == len(trace["events"])


def test_marketing_run_blocks_do_not_contact_suppression_and_revoked_consent(client):
    wid, h = _ctx(client)
    eligible = _contact(client, wid, h, "eligible@qa.test")
    dnc = _contact(client, wid, h, "dnc@qa.test")
    suppressed = _contact(client, wid, h, "suppressed@qa.test")
    no_consent = _contact(client, wid, h, "noconsent@qa.test")

    links = client.get(
        f"/api/v1/workspaces/{wid}/email/consent-links", headers=h,
        params={"contact_id": dnc["id"]},
    )
    assert links.status_code == 200, links.text
    dnc_result = client.post(
        f"/api/v1/workspaces/{wid}/email/dnc",
        json={"token": links.json()["links"]["dnc"]["token"]},
    )
    assert dnc_result.status_code == 200 and dnc_result.json()["do_not_contact"] is True
    client.post(
        f"/api/v1/workspaces/{wid}/email/suppression?email=suppressed%40qa.test",
        headers=h,
    )
    client.post(
        f"/api/v1/workspaces/{wid}/email/consent",
        headers=h,
        json={"contact_id": no_consent["id"], "channel": "email", "granted": False,
              "source": "qa"},
    )

    created = _run(
        client, wid, h,
        [eligible["id"], dnc["id"], suppressed["id"], no_consent["id"]],
        correlation_id="qa-marketing-blocks",
    )
    assert created["counts"]["audience"] == 1
    assert created["counts"]["blocked"] == 3

    approved = client.post(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs/{created['id']}/approve",
        headers=h,
    ).json()
    assert approved["counts"]["delivered"] == 1
    trace = client.get(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs/{created['id']}", headers=h
    ).json()
    assert len(trace["deliveries"]) == 1
    assert trace["deliveries"][0]["contact_id"] == eligible["id"]


def test_marketing_run_rechecks_safety_at_approval(client):
    wid, h = _ctx(client)
    contact = _contact(client, wid, h, "late-optout@qa.test")
    created = _run(
        client, wid, h, [contact["id"]], correlation_id="qa-marketing-late-optout"
    )
    assert created["counts"]["audience"] == 1
    assert created["counts"]["blocked"] == 0

    suppressed = client.post(
        f"/api/v1/workspaces/{wid}/email/suppression?email=late-optout%40qa.test",
        headers=h,
    )
    assert suppressed.status_code in (200, 201), suppressed.text

    approved = client.post(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs/{created['id']}/approve",
        headers=h,
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["counts"]["delivered"] == 0
    assert body["counts"]["blocked"] == 1

    trace = client.get(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs/{created['id']}", headers=h
    ).json()
    assert trace["deliveries"] == []
    assert trace["recipients"][0]["status"] == "suppressed"
    assert trace["recipients"][0]["error"] == "suppressed"
    assert "marketing.local_delivery_blocked" in [e["event_type"] for e in trace["events"]]


def test_marketing_run_approval_is_required_idempotent_and_correlation_safe(client):
    wid, h = _ctx(client)
    contact = _contact(client, wid, h, "idempotent@qa.test")
    created = _run(client, wid, h, [contact["id"]], correlation_id="qa-marketing-idem")

    duplicate = _run(client, wid, h, [contact["id"]], correlation_id="qa-marketing-idem")
    assert duplicate["id"] == created["id"]
    listing = client.get(f"/api/v1/workspaces/{wid}/marketing-delivery/runs", headers=h).json()
    assert len(listing) == 1

    first = client.post(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs/{created['id']}/approve",
        headers=h,
    ).json()
    second = client.post(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs/{created['id']}/approve",
        headers=h,
    ).json()
    assert first == second
    trace = client.get(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs/{created['id']}", headers=h
    ).json()
    assert len(trace["deliveries"]) == 1
    assert len([e for e in trace["events"] if e["event_type"] == "marketing.local_delivered"]) == 1


def test_marketing_run_is_workspace_isolated(client):
    first = bootstrap(client, workspace_name="First", email="first@qa.test")
    wid, h = first["workspace_id"], auth(first["access_token"])
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Second"})
    assert other.status_code == 200, other.text
    other_wid, other_h = other.json()["workspace_id"], auth(other.json()["access_token"])
    contact = _contact(client, wid, h, "isolated@qa.test")
    created = _run(client, wid, h, [contact["id"]], correlation_id="qa-marketing-iso")

    assert client.get(
        f"/api/v1/workspaces/{other_wid}/marketing-delivery/runs/{created['id']}",
        headers=other_h,
    ).status_code in (403, 404)
    assert client.post(
        f"/api/v1/workspaces/{other_wid}/marketing-delivery/runs/{created['id']}/approve",
        headers=other_h,
    ).status_code in (403, 404)
    assert client.get(
        f"/api/v1/workspaces/{other_wid}/marketing-delivery/runs", headers=other_h
    ).json() == []


def test_marketing_run_rejects_blank_audience_and_unknown_channel(client):
    wid, h = _ctx(client)
    response = client.post(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs",
        headers=h,
        json={"name": "Bad", "subject": "Bad", "body": "Bad", "contact_ids": []},
    )
    assert response.status_code == 422
    contact = _contact(client, wid, h, "valid@qa.test")
    response = client.post(
        f"/api/v1/workspaces/{wid}/marketing-delivery/runs",
        headers=h,
        json={"name": "Bad", "subject": "Bad", "body": "Bad",
              "contact_ids": [contact["id"]], "channel": "carrier-pigeon"},
    )
    assert response.status_code == 422


def test_campaign_studio_wires_the_local_delivery_workflow():
    source = APP_JS.read_text(encoding="utf-8")
    for marker in (
        'data-form="marketing-local-run-create"',
        'data-action="marketing-local-run-approve"',
        'data-action="marketing-local-run-trace"',
        "api(apiW('/marketing-delivery/runs'))",
        "if (name === 'marketing-local-run-create')",
        "case 'marketing-local-run-approve':",
        "case 'marketing-local-run-trace':",
        'Approval is required before delivery records are written.',
    ):
        assert marker in source, f"missing UI marker: {marker}"


def test_public_site_describes_the_workable_local_run():
    html = SITE_HTML.read_text(encoding="utf-8")
    assert "Local workflow verified" in html
    assert "Audience</li><li>Campaign</li><li>Approval</li>" in html
    assert "local delivery records and analytics are real" in html
    assert "no email, SMS or WhatsApp message is sent" in html
    assert "Delivery not executed" not in html
