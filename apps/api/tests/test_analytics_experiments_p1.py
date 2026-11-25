"""Named acceptance tests for P1 cluster GB-110..GB-116.

The analytics backend already existed; this cluster closes the recorded gap:
a real experiment management UI driven by the real API, with named proof for
CRUD, status transitions, result validation, funnel and event-volume aggregates,
append-only audit events and workspace isolation.

Browser walkthrough evidence: docs/evidence/analytics-experiments-p1-20261123.md
No external analytics service receives data; every figure comes from local rows.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from novara_core.main import API
from novara_core.models import Contact, Event, Lead, Task, new_id, now
from novara_core.modules import analytics

from .conftest import auth, bootstrap


def _base(wid: str) -> str:
    return f"{API}/workspaces/{wid}/analytics"


def _other(client, headers):
    response = client.post(f"{API}/workspaces", headers=headers, json={"name": "Other"})
    assert response.status_code == 200, response.text
    data = response.json()
    return data["workspace_id"], auth(data["access_token"])


def test_experiment_crud_status_and_audit_are_ui_reachable(client, db_session):
    """GB-110, GB-111, GB-115, GB-116."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)

    created = client.post(base, headers=headers, json={
        "name": "Onboarding variant", "metric_name": "activation_rate",
        "hypothesis": "Shorter subject lines raise activation.", "target": 0.35,
    })
    assert created.status_code == 201, created.text
    exp = created.json()
    eid = exp["id"]
    assert exp["status"] == "draft" and exp["owner_id"]

    # GB-110 — list, edit and delete use real API rows.
    assert eid in [row["id"] for row in client.get(base, headers=headers).json()]
    edited = client.patch(f"{base}/{eid}", headers=headers, json={"target": 0.42})
    assert edited.status_code == 200 and edited.json()["target"] == 0.42

    # GB-111 — every declared transition is accepted and is workspace-scoped.
    for status in ("running", "stopped", "completed", "draft"):
        changed = client.post(f"{base}/{eid}/status", headers=headers, json={"status": status})
        assert changed.status_code == 200, changed.text
        assert changed.json()["status"] == status

    other_wid, other_headers = _other(client, headers)
    assert client.get(f"{base}/{eid}", headers=other_headers).status_code == 403
    assert client.patch(f"{base}/{eid}", headers=other_headers,
                        json={"name": "Hijack"}).status_code == 403
    assert client.post(f"{base}/{eid}/status", headers=other_headers,
                       json={"status": "running"}).status_code == 403
    assert client.get(_base(other_wid), headers=headers).status_code == 403

    # GB-115 — audited, append-only, correctly typed and workspace-tagged.
    events = db_session.execute(
        select(Event).where(Event.workspace_id == wid)
    ).scalars().all()
    exp_events = [e for e in events if e.event_type.startswith("experiment.")]
    types = {e.event_type for e in exp_events}
    assert {
        analytics.EXPERIMENT_CREATED, analytics.EXPERIMENT_UPDATED,
        analytics.EXPERIMENT_STATUS_CHANGED,
    } <= types
    assert all(e.workspace_id == wid for e in exp_events)
    statuses = [e for e in exp_events if e.event_type == analytics.EXPERIMENT_STATUS_CHANGED]
    assert len(statuses) == 4
    assert all(e.payload["from"] != e.payload["to"] for e in statuses)

    # GB-116 — invalid writes are rejected with no partial mutation.
    assert client.post(base, headers=headers, json={"name": "  ", "metric_name": "m"}).status_code == 422
    assert client.post(base, headers=headers, json={"name": "x"}).status_code == 422
    assert client.post(f"{base}/{eid}/status", headers=headers,
                       json={"status": "launched"}).status_code == 422
    assert client.get(f"{base}/{eid}", headers=headers).json()["target"] == 0.42

    deleted = client.delete(f"{base}/{eid}", headers=headers)
    assert deleted.status_code == 200 and deleted.json() == {"deleted": True, "experiment_id": eid}
    assert client.get(f"{base}/{eid}", headers=headers).status_code == 404
    final_events = db_session.execute(
        select(Event).where(Event.workspace_id == wid)
    ).scalars().all()
    assert any(e.event_type == analytics.EXPERIMENT_DELETED for e in final_events)
    assert len([e for e in final_events if e.event_type.startswith("experiment.")]) >= len(exp_events)


def test_experiment_results_and_aggregates_use_real_local_rows(client, db_session):
    """GB-112, GB-113, GB-114, GB-116."""
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)

    exp = client.post(base, headers=headers, json={
        "name": "Pricing page", "metric_name": "signup_rate",
    }).json()
    eid = exp["id"]
    results_url = f"{base}/{eid}/results"

    # GB-112 — valid results persist, invalid ones are rejected, an identical
    # (variant, recorded_at) pair is an upsert rather than a duplicate.
    good = client.post(results_url, headers=headers, json={
        "variant": "control", "impressions": 200, "conversions": 20,
    })
    assert good.status_code == 200, good.text
    assert client.post(results_url, headers=headers, json={
        "variant": "variant-b", "impressions": 100, "conversions": 12,
    }).status_code == 200
    assert client.post(results_url, headers=headers, json={
        "variant": "bad", "impressions": 5, "conversions": 9,
    }).status_code == 422
    assert client.post(results_url, headers=headers, json={
        "variant": "bad", "impressions": -1, "conversions": 0,
    }).status_code == 422
    assert client.post(results_url, headers=headers, json={
        "variant": "control", "impressions": 210, "conversions": 21,
        "recorded_at": good.json()["recorded_at"],
    }).status_code == 200
    rows = client.get(results_url, headers=headers).json()
    assert len(rows) == 2
    assert next(r for r in rows if r["variant"] == "control")["impressions"] == 210

    # GB-113 — funnel counts come from real rows in this workspace only.
    contact = Contact(id=new_id(), workspace_id=wid, email="gb113@example.com", full_name="Funnel")
    db_session.add(contact)
    db_session.flush()
    db_session.add_all([
        Lead(id=new_id(), workspace_id=wid, contact_id=contact.id, status="converted"),
        Task(id=new_id(), workspace_id=wid, title="Funnel task"),
    ])
    db_session.commit()
    funnel = client.get(f"{base}/funnel", headers=headers)
    assert funnel.status_code == 200, funnel.text
    assert funnel.json() == {"contacts": 1, "leads": 1, "converted_leads": 1, "tasks": 1}
    other_wid, other_headers = _other(client, headers)
    assert client.get(f"{base}/funnel", headers=other_headers).status_code == 403
    assert client.get(f"{_base(other_wid)}/funnel", headers=other_headers).json() == {
        "contacts": 0, "leads": 0, "converted_leads": 0, "tasks": 0,
    }

    # GB-114 — event volume is date-filtered and workspace-isolated.
    all_volume = client.get(f"{base}/events/volume", headers=headers).json()
    assert any(row["event_type"] == analytics.EXPERIMENT_RESULT_RECORDED for row in all_volume)
    past = (now() - timedelta(days=30)).isoformat()
    future = (now() + timedelta(days=30)).isoformat()
    filtered = client.get(f"{base}/events/volume", headers=headers,
                          params={"date_from": past, "date_to": future}).json()
    assert filtered == all_volume
    assert client.get(f"{base}/events/volume", headers=headers,
                      params={"date_from": future, "date_to": past}).status_code == 422
    assert client.get(f"{base}/events/volume", headers=headers,
                      params={"date_from": "not-a-date"}).status_code == 422
    assert client.get(f"{base}/events/volume", headers=other_headers).status_code == 403
    other_volume = client.get(f"{_base(other_wid)}/events/volume", headers=other_headers).json()
    assert other_volume == []
    assert client.get(f"{base}/events/volume").status_code == 401

    # GB-110/GB-116 — the page consumes exactly these routes, and every
    # experiment control has one dispatcher in the SPA source.
    from pathlib import Path

    js = (Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js").read_text(encoding="utf-8")
    for marker in (
        "api(apiW('/analytics'))",
        "encodeURIComponent(text('id')) + '/status'",
        "encodeURIComponent(text('id')) + '/results'",
        'data-action="experiment-create"', 'data-action="experiment-delete"',
        "method: isEdit ? 'PATCH' : 'POST'",
    ):
        assert marker in js, f"missing experiment UI wiring: {marker}"
