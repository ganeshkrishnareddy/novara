"""Contract guards for the Phase 4 web views.

These tests pin the exact response shapes consumed by the Universal Search and
Customer Inbox screens in apps/web/app.js. If an API field is renamed, these
fail before a browser user sees a blank screen.
"""

from __future__ import annotations

from novara_core.main import app  # noqa: F401 - importing registers every module router
from novara_core.models import Contact, new_id

from .conftest import auth, bootstrap


def test_universal_search_contract_matches_web_app(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = Contact(
        id=new_id(), workspace_id=wid,
        email="ui@example.com", full_name="UI Contract",
    )
    db_session.add(contact)
    db_session.commit()

    response = client.get(
        f"/api/v1/workspaces/{wid}/search",
        headers=headers,
        params={"q": "UI Contract", "limit": 50},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"results", "counts", "total"}
    assert payload["total"] == len(payload["results"]) == 1

    item = payload["results"][0]
    assert set(item) == {"type", "id", "title", "subtitle", "url_hint"}
    assert item["type"] == "contact"
    assert item["id"] == contact.id
    assert item["title"] == "UI Contract"
    assert item["subtitle"] == "ui@example.com"
    assert item["url_hint"] == f"/contacts/{contact.id}"


def test_ticket_contract_matches_web_app(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = Contact(
        id=new_id(), workspace_id=wid,
        email="customer@example.com", full_name="Customer One",
    )
    db_session.add(contact)
    db_session.commit()

    created = client.post(
        f"/api/v1/workspaces/{wid}/tickets",
        headers=headers,
        json={
            "subject": "Login issue",
            "body": "Cannot sign in",
            "contact_id": contact.id,
            "priority": "high",
        },
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]

    message = client.post(
        f"/api/v1/workspaces/{wid}/tickets/{ticket_id}/messages",
        headers=headers,
        json={"body": "Investigating now"},
    )
    assert message.status_code == 201, message.text

    detail = client.get(
        f"/api/v1/workspaces/{wid}/tickets/{ticket_id}", headers=headers
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert set(payload) == {"ticket", "messages"}

    ticket = payload["ticket"]
    assert set(ticket) == {
        "id", "contact_id", "subject", "body", "status", "priority",
        "origin_channel", "conversation_type",
        "assignee_id", "team_id", "inbox_id", "sla_policy_id", "first_response_due_at",
        "resolution_due_at", "created_at", "updated_at",
    }
    assert ticket["id"] == ticket_id
    assert ticket["contact_id"] == contact.id
    assert ticket["status"] == "open"

    first_message = payload["messages"][0]
    assert set(first_message) == {
        "id", "ticket_id", "author_id", "body", "direction", "channel", "is_internal", "created_at"
    }
    assert first_message["ticket_id"] == ticket_id
    assert first_message["body"] == "Investigating now"

    patched = client.patch(
        f"/api/v1/workspaces/{wid}/tickets/{ticket_id}",
        headers=headers,
        json={"status": "pending"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "pending"


def test_campaign_studio_contract_matches_web_app(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    created = client.post(
        f"/api/v1/workspaces/{wid}/campaigns",
        headers=headers,
        json={"name": "Launch", "channel": "email", "goal": "200 leads"},
    )
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]

    detail = client.get(
        f"/api/v1/workspaces/{wid}/campaigns/{campaign_id}", headers=headers
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert set(payload) == {
        "campaign", "metric_days", "total_impressions", "total_clicks",
        "total_leads", "total_spend",
    }
    assert payload["campaign"]["name"] == "Launch"
    assert payload["metric_days"] == 0

    metric = client.post(
        f"/api/v1/workspaces/{wid}/campaigns/{campaign_id}/metrics",
        headers=headers,
        json={"date": "2026-11-22", "impressions": 100, "clicks": 10,
              "leads": 2, "spend": 12.5},
    )
    assert metric.status_code == 201, metric.text
    assert set(metric.json()) == {
        "id", "workspace_id", "campaign_id", "date", "impressions",
        "clicks", "leads", "spend", "created_at",
    }

    performance = client.get(
        f"/api/v1/workspaces/{wid}/campaigns/performance", headers=headers
    )
    assert performance.status_code == 200, performance.text
    assert performance.json()[0]["total_leads"] == 2

    patched = client.patch(
        f"/api/v1/workspaces/{wid}/campaigns/{campaign_id}",
        headers=headers, json={"status": "active"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "active"


def test_sales_pipeline_contract_matches_web_app(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = Contact(
        id=new_id(), workspace_id=wid,
        email="buyer@example.com", full_name="Buyer One",
    )
    db_session.add(contact)
    db_session.commit()

    created = client.post(
        f"/api/v1/workspaces/{wid}/deals",
        headers=headers,
        json={"title": "Annual licence", "contact_id": contact.id,
              "value": 1500, "stage": "new", "probability": 25},
    )
    assert created.status_code == 201, created.text
    deal_id = created.json()["id"]
    assert set(created.json()) == {
        "id", "workspace_id", "contact_id", "company", "title", "value",
        "stage", "probability", "owner_id", "expected_close_at",
        "created_at", "updated_at",
    }

    summary = client.get(f"/api/v1/workspaces/{wid}/deals/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert set(summary.json()) == {"by_stage", "total_deals", "total_value"}
    assert summary.json()["total_deals"] == 1

    activity = client.post(
        f"/api/v1/workspaces/{wid}/deals/{deal_id}/activities",
        headers=headers, json={"activity_type": "Call", "note": "Intro call"},
    )
    assert activity.status_code == 201, activity.text
    assert set(activity.json()) == {
        "id", "workspace_id", "deal_id", "activity_type", "note",
        "actor_id", "created_at",
    }

    patched = client.patch(
        f"/api/v1/workspaces/{wid}/deals/{deal_id}",
        headers=headers, json={"stage": "qualified"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["stage"] == "qualified"


def test_feedback_studio_contract_matches_web_app(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = Contact(
        id=new_id(), workspace_id=wid,
        email="respondent@example.com", full_name="Respondent One",
    )
    db_session.add(contact)
    db_session.commit()

    created = client.post(
        f"/api/v1/workspaces/{wid}/surveys",
        headers=headers, json={"name": "Post demo", "description": "Quick check"},
    )
    assert created.status_code == 201, created.text
    survey_id = created.json()["id"]

    response = client.post(
        f"/api/v1/workspaces/{wid}/surveys/{survey_id}/responses",
        headers=headers,
        json={"contact_id": contact.id, "score": 9, "comment": "Great"},
    )
    assert response.status_code == 201, response.text
    assert set(response.json()) == {
        "id", "survey_id", "contact_id", "score", "comment", "created_at",
    }

    detail = client.get(
        f"/api/v1/workspaces/{wid}/surveys/{survey_id}", headers=headers
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert set(payload) == {"survey", "response_count", "average_score"}
    assert payload["response_count"] == 1
    assert payload["average_score"] == 9.0

    responses = client.get(
        f"/api/v1/workspaces/{wid}/surveys/{survey_id}/responses", headers=headers
    )
    assert responses.status_code == 200, responses.text
    assert responses.json()[0]["score"] == 9
