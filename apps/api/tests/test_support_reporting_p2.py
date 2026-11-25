"""Named acceptance tests for the clean-room support reporting cluster.

CW-096/097/098/099/101/104/114/117 are proven end to end against real
persisted support rows. Every mutation uses the real FastAPI app and every test
patches socket.connect so an accidental outbound call fails immediately.
"""

from __future__ import annotations

import csv
import io
import socket

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}"
TICKETS = API + "/tickets"
BASE = API + "/support-reporting"
PUBLIC = "/api/v1/public/support-surveys"


def _ctx(client):
    tokens = bootstrap(client, "ReportingLab", "reporting-owner@example.com")
    wid = tokens["workspace_id"]
    headers = auth(tokens["access_token"])
    me = client.get("/api/v1/auth/me", headers=headers).json()
    return wid, headers, me["user"]["id"]


def _base(wid):
    return BASE.format(wid=wid)


def _tickets(wid):
    return TICKETS.format(wid=wid)


def _no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("support reporting attempted outbound traffic")
    monkeypatch.setattr(socket.socket, "connect", blocked)


def _create(client, wid, headers, path, payload):
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _fixture_rows(client, wid, headers, owner_id):
    team_a = _create(client, wid, headers, _tickets(wid) + "/teams", {"name": "Team A"})
    team_b = _create(client, wid, headers, _tickets(wid) + "/teams", {"name": "Team B"})
    inbox_a = _create(client, wid, headers, _tickets(wid) + "/inboxes",
                      {"name": "Inbox A", "csat_enabled": True})
    inbox_b = _create(client, wid, headers, _tickets(wid) + "/inboxes",
                      {"name": "Inbox B", "csat_enabled": True})
    billing = _create(client, wid, headers, _tickets(wid) + "/labels", {"name": "billing"})
    vip = _create(client, wid, headers, _tickets(wid) + "/labels", {"name": "vip"})
    rows = []
    definitions = [
        ("Resolved A", "resolved", team_a, inbox_a, [billing, vip]),
        ("Open A", "open", team_a, inbox_a, [billing]),
        ("Open B", "open", team_b, inbox_b, []),
    ]
    for subject, ticket_status, team, inbox, labels in definitions:
        ticket = _create(client, wid, headers, _tickets(wid), {
            "subject": subject, "body": subject,
            "assignee_id": owner_id, "team_id": team["id"], "inbox_id": inbox["id"],
        })
        if ticket_status != "open":
            assert client.patch(_tickets(wid) + f"/{ticket['id']}", headers=headers,
                                json={"status": ticket_status}).status_code == 200
        for label in labels:
            added = client.post(_tickets(wid) + f"/{ticket['id']}/labels", headers=headers,
                                json={"label_id": label["id"]})
            assert added.status_code == 201, added.text
        message = client.post(_tickets(wid) + f"/{ticket['id']}/messages", headers=headers,
                              json={"body": "First local reply", "direction": "outbound"})
        assert message.status_code == 201, message.text
        rows.append(ticket)
    return {
        "teams": [team_a, team_b], "inboxes": [inbox_a, inbox_b],
        "labels": [billing, vip], "tickets": rows,
    }


def test_cw096_agent_report_matches_assigned_ticket_rows(client, monkeypatch):
    """CW-096: the agent report matches only the tickets assigned to each agent."""
    _no_network(monkeypatch)
    wid, h, owner_id = _ctx(client)
    fixture = _fixture_rows(client, wid, h, owner_id)
    report = client.get(_base(wid) + "/reports/agents", headers=h).json()
    assert report["source"] == "persisted_local_support_rows"
    assert report["tickets_count"] == 3
    assert report["rows"][0]["key"] == owner_id
    assert report["rows"][0]["tickets"] == 3
    assert report["rows"][0]["resolved"] == 1
    assert report["rows"][0]["avg_first_response_minutes"] is not None
    filtered = client.get(_base(wid) + "/reports/agents", headers=h,
                          params={"status": "open"}).json()
    assert filtered["tickets_count"] == 2
    assert client.get(_base(wid) + "/reports/agents", headers=h,
                      params={"status": "invented"}).status_code == 422


def test_cw097_team_report_uses_only_tickets_with_that_team(client, monkeypatch):
    """CW-097: team totals are grouped from the team id stored on each ticket."""
    _no_network(monkeypatch)
    wid, h, owner_id = _ctx(client)
    fixture = _fixture_rows(client, wid, h, owner_id)
    report = client.get(_base(wid) + "/reports/teams", headers=h).json()
    counts = {row["key"]: row["tickets"] for row in report["rows"]}
    assert counts == {fixture["teams"][0]["id"]: 2, fixture["teams"][1]["id"]: 1}
    assert client.get(_base(wid) + "/reports/teams", headers=h,
                      params={"team_id": "missing"}).status_code == 404


def test_cw098_inbox_report_counts_only_that_inbox(client, monkeypatch):
    """CW-098: inbox report counts match that inbox's persisted tickets."""
    _no_network(monkeypatch)
    wid, h, owner_id = _ctx(client)
    fixture = _fixture_rows(client, wid, h, owner_id)
    report = client.get(_base(wid) + "/reports/inboxes", headers=h).json()
    counts = {row["key"]: row["tickets"] for row in report["rows"]}
    assert counts == {fixture["inboxes"][0]["id"]: 2, fixture["inboxes"][1]["id"]: 1}
    assert client.get(_base(wid) + "/reports/inboxes", headers=h).status_code == 200


def test_cw099_label_report_equals_real_label_ticket_rows(client, monkeypatch):
    """CW-099: label counts come from real label-ticket links, never a guess."""
    _no_network(monkeypatch)
    wid, h, owner_id = _ctx(client)
    fixture = _fixture_rows(client, wid, h, owner_id)
    report = client.get(_base(wid) + "/reports/labels", headers=h).json()
    by_name = {row["name"]: row["tickets"] for row in report["rows"]}
    assert by_name == {"billing": 2, "vip": 1}
    assert report["tickets_count"] == 3
    filtered = client.get(_base(wid) + "/reports/labels", headers=h,
                          params={"label_id": fixture["labels"][1]["id"]}).json()
    assert filtered["tickets_count"] == 1


def test_cw101_csv_export_matches_the_on_screen_filtered_result(client, monkeypatch):
    """CW-101: exported CSV rows equal the same filtered report result set."""
    _no_network(monkeypatch)
    wid, h, owner_id = _ctx(client)
    fixture = _fixture_rows(client, wid, h, owner_id)
    params = {"dimension": "labels", "status": "open"}
    expected = client.get(_base(wid) + "/reports/labels", headers=h,
                          params={"status": "open"}).json()["rows"]
    response = client.get(_base(wid) + "/reports/export", headers=h, params=params)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == len(expected)
    assert {(row["key"], int(row["tickets"])) for row in rows} == {
        (row["key"], row["tickets"]) for row in expected
    }
    events = client.get(API.format(wid=wid) + "/events", headers=h).json()
    assert any(event["event_type"] == "support.report_exported" for event in events)


def test_report_runs_persist_filters_and_summary(client, monkeypatch):
    """Saved report runs remain queryable, scoped and audited."""
    _no_network(monkeypatch)
    wid, h, owner_id = _ctx(client)
    fixture = _fixture_rows(client, wid, h, owner_id)
    created = client.post(_base(wid) + "/reports/runs", headers=h,
                          json={"dimension": "teams", "status": "open"})
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["filters"]["status"] == "open"
    assert run["summary"]["tickets_count"] == 2
    listed = client.get(_base(wid) + "/reports/runs", headers=h).json()
    assert [row["id"] for row in listed] == [run["id"]]
    events = client.get(API.format(wid=wid) + "/events", headers=h).json()
    assert any(event["event_type"] == "support.report_generated" for event in events)


def test_cw104_csat_rules_gate_survey_creation_on_resolution(client, monkeypatch):
    """CW-104: include labels permit a survey and exclude labels prevent one."""
    _no_network(monkeypatch)
    wid, h, owner_id = _ctx(client)
    inbox = _create(client, wid, h, _tickets(wid) + "/inboxes",
                    {"name": "CSAT inbox", "csat_enabled": True})
    included = _create(client, wid, h, _tickets(wid) + "/labels", {"name": "eligible"})
    excluded = _create(client, wid, h, _tickets(wid) + "/labels", {"name": "do-not-survey"})
    baseline = _create(client, wid, h, _tickets(wid), {
        "subject": "Baseline", "body": "Baseline", "inbox_id": inbox["id"],
    })
    assert client.patch(_tickets(wid) + f"/{baseline['id']}", headers=h,
                        json={"status": "resolved"}).status_code == 200
    surveys = client.get(_tickets(wid) + "/csat-surveys", headers=h).json()
    assert len(surveys) == 1, "no rules must preserve existing local CSAT behaviour"

    rule = client.post(_base(wid) + "/csat-rules", headers=h, json={
        "name": "Eligible resolutions", "include_labels": ["eligible"],
        "exclude_labels": ["do-not-survey"], "enabled": True,
    })
    assert rule.status_code == 201, rule.text
    assert client.post(_base(wid) + "/csat-rules", headers=h, json={
        "name": "Eligible resolutions", "include_labels": ["eligible"],
    }).status_code == 409
    assert client.post(_base(wid) + "/csat-rules", headers=h, json={
        "name": "Invalid", "include_labels": ["unknown"],
    }).status_code == 422

    allowed = _create(client, wid, h, _tickets(wid), {
        "subject": "Allowed", "body": "Allowed", "inbox_id": inbox["id"],
    })
    blocked = _create(client, wid, h, _tickets(wid), {
        "subject": "Blocked", "body": "Blocked", "inbox_id": inbox["id"],
    })
    for ticket, label in ((allowed, included), (blocked, included), (blocked, excluded)):
        assert client.post(_tickets(wid) + f"/{ticket['id']}/labels", headers=h,
                           json={"label_id": label["id"]}).status_code == 201
    for ticket in (allowed, blocked):
        assert client.patch(_tickets(wid) + f"/{ticket['id']}", headers=h,
                            json={"status": "resolved"}).status_code == 200
    surveys = client.get(_tickets(wid) + "/csat-surveys", headers=h).json()
    assert {row["ticket_id"] for row in surveys} == {baseline["id"], allowed["id"]}
    assert client.get(_base(wid) + "/csat-rules", headers=h).json()[0]["name"] == "Eligible resolutions"


def test_cw114_one_time_survey_token_records_one_response(client, monkeypatch):
    """CW-114: a valid opaque token stores one response; replay is rejected."""
    _no_network(monkeypatch)
    wid, h, _owner = _ctx(client)
    inbox = _create(client, wid, h, _tickets(wid) + "/inboxes",
                    {"name": "Token inbox", "csat_enabled": True})
    ticket = _create(client, wid, h, _tickets(wid), {
        "subject": "Token ticket", "body": "Token ticket", "inbox_id": inbox["id"],
    })
    assert client.patch(_tickets(wid) + f"/{ticket['id']}", headers=h,
                        json={"status": "resolved"}).status_code == 200
    survey = client.get(_tickets(wid) + "/csat-surveys", headers=h).json()[0]
    issued = client.post(_base(wid) + f"/csat-surveys/{survey['id']}/response-token", headers=h)
    assert issued.status_code == 201, issued.text
    token = issued.json()["token"]
    assert token and issued.json()["external_calls"] is False
    url = PUBLIC + f"/workspaces/{wid}/responses/{token}"
    submitted = client.post(url, json={"score": 4, "comment": "Good local service"})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["external_delivery"] is False
    assert client.post(url, json={"score": 5}).status_code == 409
    assert client.post(PUBLIC + f"/workspaces/{wid}/responses/not-a-real-token",
                       json={"score": 5}).status_code == 404
    responses = client.get(_base(wid) + "/csat-responses", headers=h).json()
    assert len(responses) == 1 and responses[0]["score"] == 4
    events = client.get(API.format(wid=wid) + "/events", headers=h).json()
    assert any(event["event_type"] == "support.csat_response_recorded" for event in events)


def test_csat_rate_limit_counts_failed_attempts(client, monkeypatch):
    """Rate limiting applies to failed redemption attempts, not just success."""
    _no_network(monkeypatch)
    wid, h, _owner = _ctx(client)
    inbox = _create(client, wid, h, _tickets(wid) + "/inboxes",
                    {"name": "Rate inbox", "csat_enabled": True})
    ticket = _create(client, wid, h, _tickets(wid), {
        "subject": "Rate ticket", "body": "Rate ticket", "inbox_id": inbox["id"],
    })
    assert client.patch(_tickets(wid) + f"/{ticket['id']}", headers=h,
                        json={"status": "resolved"}).status_code == 200
    survey = client.get(_tickets(wid) + "/csat-surveys", headers=h).json()[0]
    token = client.post(_base(wid) + f"/csat-surveys/{survey['id']}/response-token",
                        headers=h).json()["token"]
    url = PUBLIC + f"/workspaces/{wid}/responses/{token}"
    for _ in range(3):
        assert client.post(url, json={"score": 0}).status_code == 422
    assert client.post(url, json={"score": 5}).status_code == 429


def test_cw117_openapi_contract_is_generated_from_live_support_routes(client, monkeypatch):
    """CW-117: the 3.1 contract is generated from the real app, not a snapshot."""
    _no_network(monkeypatch)
    wid, h, _owner = _ctx(client)
    contract = client.get(_base(wid) + "/api-contract", headers=h).json()
    assert contract["openapi"].startswith("3.1")
    assert contract["generated_from"] == "live FastAPI application"
    assert contract["external_calls"] is False and contract["external_delivery"] is False
    paths = {route["path"] for route in contract["support_routes"]}
    assert TICKETS.format(wid="{workspace_id}") + "/reports/overview" in paths
    assert BASE.format(wid="{workspace_id}") + "/reports/agents" in paths
    assert PUBLIC + "/workspaces/{workspace_id}/responses/{token}" in paths
    assert contract["route_count"] == len(paths)
    for route in contract["support_routes"]:
        assert route["methods"] and route["operations"]


def test_reporting_rows_are_workspace_isolated_and_writes_protected(client, monkeypatch):
    """A second workspace sees no reporting rows and cannot redeem another token."""
    _no_network(monkeypatch)
    wid, h, owner_id = _ctx(client)
    fixture = _fixture_rows(client, wid, h, owner_id)
    survey_inbox = _create(client, wid, h, _tickets(wid) + "/inboxes",
                           {"name": "Isolation inbox", "csat_enabled": True})
    ticket = _create(client, wid, h, _tickets(wid), {
        "subject": "Isolation", "body": "Isolation", "inbox_id": survey_inbox["id"],
    })
    assert client.patch(_tickets(wid) + f"/{ticket['id']}", headers=h,
                        json={"status": "resolved"}).status_code == 200
    survey = client.get(_tickets(wid) + "/csat-surveys", headers=h).json()[0]
    token = client.post(_base(wid) + f"/csat-surveys/{survey['id']}/response-token",
                        headers=h).json()["token"]

    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other reporting"})
    assert other.status_code == 200, other.text
    owid, oh = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(owid) + "/reports/agents", headers=oh).json()["rows"] == []
    assert client.get(_base(owid) + "/reports/runs", headers=oh).json() == []
    assert client.get(_base(owid) + "/csat-rules", headers=oh).json() == []
    assert client.get(_base(owid) + "/csat-responses", headers=oh).json() == []
    assert client.post(PUBLIC + f"/workspaces/{owid}/responses/{token}",
                       json={"score": 5}).status_code == 404
    assert client.post(_base(wid) + "/csat-rules", headers={},
                       json={"name": "x"}).status_code in (401, 403)
    assert client.post(_base(wid) + "/reports/runs", headers={},
                       json={"dimension": "agents"}).status_code in (401, 403)
