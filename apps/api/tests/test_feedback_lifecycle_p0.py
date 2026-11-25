"""Named acceptance tests for P0 FB-001 — the clean-room survey lifecycle.

The existing list/detail/response API and Feedback Studio UI are extended here
with an enforced draft -> active -> closed lifecycle, audited status changes and
contact validation. Nothing is distributed externally: responses are recorded
locally only.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.models import Event
from novara_core.modules import feedback

from .conftest import auth, bootstrap


def _survey(client, wid, headers, name="Post demo"):
    response = client.post(
        f"/api/v1/workspaces/{wid}/surveys", headers=headers,
        json={"name": name, "description": "Local feedback"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _events(db_session, wid):
    return db_session.execute(
        select(Event).where(Event.workspace_id == wid).order_by(Event.seq)
    ).scalars().all()


def test_survey_lifecycle_controls_responses_and_is_audited(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    survey = _survey(client, wid, headers)
    sid = survey["id"]
    assert survey["status"] == "draft"
    path = f"/api/v1/workspaces/{wid}/surveys/{sid}"

    published = client.patch(path, headers=headers, json={"status": "active"})
    assert published.status_code == 200 and published.json()["status"] == "active"
    closed = client.patch(path, headers=headers, json={"status": "closed"})
    assert closed.status_code == 200 and closed.json()["status"] == "closed"

    blocked = client.post(path + "/responses", headers=headers,
                          json={"score": 9, "comment": "Too late"})
    assert blocked.status_code == 409, blocked.text

    reopened = client.patch(path, headers=headers, json={"status": "active"})
    assert reopened.status_code == 200
    accepted = client.post(path + "/responses", headers=headers,
                           json={"score": 8, "comment": "Fine"})
    assert accepted.status_code == 201, accepted.text
    detail = client.get(path, headers=headers)
    assert detail.status_code == 200
    assert detail.json()["response_count"] == 1
    assert detail.json()["average_score"] == 8.0

    types = [event.event_type for event in _events(db_session, wid)]
    assert types.count(feedback.SURVEY_CREATED) == 1
    assert types.count(feedback.SURVEY_STATUS_CHANGED) == 3
    assert types.count(feedback.SURVEY_RESPONSE_CREATED) == 1


def test_survey_updates_validate_metadata_and_identities(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/surveys"
    first = _survey(client, wid, headers, "First")
    second = _survey(client, wid, headers, "Second")
    path = base + "/" + first["id"]

    assert client.patch(path, headers=headers, json={}).status_code == 422
    assert client.patch(path, headers=headers, json={"status": "archived"}).status_code == 422
    assert client.patch(path, headers=headers, json={"name": "  "}).status_code == 422
    assert client.patch(path, headers=headers, json={"name": "Second"}).status_code == 409
    renamed = client.patch(path, headers=headers,
                           json={"name": "Renamed", "description": "Updated"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed"
    assert renamed.json()["description"] == "Updated"
    assert client.get(base, headers=headers).json()[1]["name"] == "Renamed"

    bad_contact = client.post(path + "/responses", headers=headers,
                              json={"contact_id": "missing", "score": 7})
    assert bad_contact.status_code == 422, bad_contact.text
    bad_score = client.post(path + "/responses", headers=headers, json={"score": 11})
    assert bad_score.status_code == 422, bad_score.text

    other = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other"}).json()
    other_headers = auth(other["access_token"])
    assert client.get(f"/api/v1/workspaces/{other['workspace_id']}/surveys/{first['id']}",
                      headers=other_headers).status_code == 404
    assert client.patch(f"/api/v1/workspaces/{other['workspace_id']}/surveys/{first['id']}",
                        headers=other_headers, json={"status": "closed"}).status_code == 404
