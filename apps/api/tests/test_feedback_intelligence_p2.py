"""Named acceptance tests for the Feedback Intelligence P2 cluster.

Every test drives the real FastAPI app against real persisted, workspace-scoped
rows. No app code is mocked, no external feedback service is contacted and no
Formbricks source is used. The ten promoted rows are FB-024, FB-025, FB-029,
FB-085, FB-096, FB-097, FB-098, FB-099, FB-100 and FB-101.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.models import Event
from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/feedback-intelligence"
SURVEYS = "/api/v1/workspaces/{wid}/surveys"
CONTACTS = "/api/v1/workspaces/{wid}/contacts"


def _ctx(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _survey(client, wid, h, name):
    r = client.post(SURVEYS.format(wid=wid), headers=h, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _dataset(client, wid, h, key="customers", name="Customer feedback"):
    r = client.post(_base(wid) + "/datasets", headers=h, json={"key": key, "name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _source(client, wid, h, dataset_id, key="web", source_type="web"):
    r = client.post(f"{_base(wid)}/datasets/{dataset_id}/sources", headers=h,
                    json={"key": key, "name": key.title(), "source_type": source_type})
    assert r.status_code == 201, r.text
    return r.json()


def _ingest(client, wid, h, dataset_id, payload=None, reserved=None, metadata=None,
            sentiment=None, external_id=None):
    body = {"payload": payload or {"text": "Great service"}, "reserved": reserved or {},
            "metadata": metadata or {}}
    if sentiment is not None:
        body["sentiment"] = sentiment
    if external_id is not None:
        body["external_id"] = external_id
    r = client.post(f"{_base(wid)}/datasets/{dataset_id}/records", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_fb101_unify_feedback_api_group_is_documented(client):
    wid, h = _ctx(client)
    contract = client.get(_base(wid) + "/api-contract", headers=h).json()
    assert contract["version"] == "1" and contract["legacy_versions"] == []
    assert contract["delivery"] == "local-only"
    for resource in ("fields", "datasets", "sources", "feedbackRecords", "segments",
                     "dashboards", "insights"):
        assert resource in contract["resources"]


def test_fb024_field_library_reused_across_surveys_changes_in_one_place(client):
    wid, h = _ctx(client)
    field = client.post(_base(wid) + "/fields", headers=h,
                        json={"key": "rating", "label": "Rate us", "type": "rating"}).json()
    assert client.post(_base(wid) + "/fields", headers=h,
                       json={"key": "rating", "label": "dup"}).status_code == 409
    assert client.post(_base(wid) + "/fields", headers=h,
                       json={"key": "bad", "label": "x", "type": "carrier-pigeon"}).status_code == 422
    s1 = _survey(client, wid, h, "Survey One")
    s2 = _survey(client, wid, h, "Survey Two")
    for survey in (s1, s2):
        bound = client.post(f"{_base(wid)}/surveys/{survey['id']}/fields", headers=h,
                            json={"field_id": field["id"], "position": 1})
        assert bound.status_code == 201, bound.text
    # One edit changes the effective field in both surveys.
    patched = client.patch(f"{_base(wid)}/fields/{field['id']}", headers=h,
                           json={"label": "Overall rating"}).json()
    assert patched["label"] == "Overall rating"
    for survey in (s1, s2):
        effective = client.get(f"{_base(wid)}/surveys/{survey['id']}/fields", headers=h).json()
        assert len(effective) == 1
        assert effective[0]["label"] == "Overall rating" and effective[0]["key"] == "rating"
    # Duplicate binding is rejected, and unbinding removes just that survey's field.
    assert client.post(f"{_base(wid)}/surveys/{s1['id']}/fields", headers=h,
                       json={"field_id": field["id"]}).status_code == 409
    assert client.delete(f"{_base(wid)}/surveys/{s1['id']}/fields/{field['id']}",
                         headers=h).json()["removed"] is True
    assert client.get(f"{_base(wid)}/surveys/{s1['id']}/fields", headers=h).json() == []
    assert len(client.get(f"{_base(wid)}/surveys/{s2['id']}/fields", headers=h).json()) == 1


def test_fb025_reserved_fields_captured_on_every_record_and_not_spoofable(client):
    wid, h = _ctx(client)
    reserved = client.get(_base(wid) + "/reserved-fields", headers=h).json()
    assert [item["name"] for item in reserved] == [
        "page", "campaign", "device", "timing", "request_context",
    ]
    ds = _dataset(client, wid, h)
    _source(client, wid, h, ds["id"])
    rec = _ingest(client, wid, h, ds["id"], reserved={
        "page": "/pricing", "campaign": "spring", "device": "mobile",
        "timing": "spoofed", "request_context": "en-IN",
    })
    for name in ("page", "campaign", "device", "timing", "request_context"):
        assert name in rec["reserved"]
    assert rec["reserved"]["page"] == "/pricing"
    assert rec["reserved"]["timing"] != "spoofed"  # server-owned
    assert rec["reserved"]["captured_at"]


def test_fb029_respondent_metadata_captured_and_grouped_per_dataset(client):
    wid, h = _ctx(client)
    ds1 = _dataset(client, wid, h, "ds-one")
    ds2 = _dataset(client, wid, h, "ds-two")
    _source(client, wid, h, ds1["id"])
    _source(client, wid, h, ds2["id"])
    _ingest(client, wid, h, ds1["id"], reserved={"source_id": _first_source(client, wid, h, ds1["id"])},
            metadata={"respondent_id": "alice", "locale": "en-IN", "device": "mobile"})
    _ingest(client, wid, h, ds1["id"], metadata={"respondent_id": "alice", "locale": "en-IN"})
    _ingest(client, wid, h, ds2["id"], metadata={"respondent_id": "bob", "locale": "fr-FR"})
    grouped = client.get(f"{_base(wid)}/datasets/{ds1['id']}/metadata", headers=h).json()
    assert len(grouped) == 1
    assert grouped[0]["record_count"] == 2
    assert grouped[0]["metadata"]["respondent_id"] == "alice"
    assert grouped[0]["respondent_hash"] != client.get(
        f"{_base(wid)}/datasets/{ds2['id']}/metadata", headers=h).json()[0]["respondent_hash"]


def _first_source(client, wid, h, dataset_id):
    return client.get(f"{_base(wid)}/datasets/{dataset_id}/sources", headers=h).json()[0]["id"]


def test_fb098_datasets_and_fb099_sources_are_workspace_scoped(client):
    wid, h = _ctx(client)
    ds = _dataset(client, wid, h)
    assert any(row["id"] == ds["id"] for row in client.get(_base(wid) + "/datasets", headers=h).json())
    src = _source(client, wid, h, ds["id"])
    assert any(row["id"] == src["id"] for row in
               client.get(f"{_base(wid)}/datasets/{ds['id']}/sources", headers=h).json())
    assert client.post(f"{_base(wid)}/datasets/{ds['id']}/sources", headers=h,
                       json={"key": "web", "name": "dup"}).status_code == 409
    assert client.post(f"{_base(wid)}/datasets/{ds['id']}/sources", headers=h,
                       json={"key": "bad", "name": "x", "source_type": "carrier-pigeon"}).status_code == 422
    # A source from another dataset cannot be attached to a record in this one.
    ds2 = _dataset(client, wid, h, "other")
    src2 = _source(client, wid, h, ds2["id"], "email", "email")
    r = client.post(f"{_base(wid)}/datasets/{ds['id']}/records", headers=h,
                    json={"payload": {"text": "hi"}, "reserved": {"source_id": src2["id"]}})
    assert r.status_code == 422


def test_fb100_records_ingest_filter_and_sentiment_override(client, db_session):
    wid, h = _ctx(client)
    ds = _dataset(client, wid, h)
    src = _source(client, wid, h, ds["id"])
    good = _ingest(client, wid, h, ds["id"], payload={"text": "I love this, excellent!"},
                   reserved={"source_id": src["id"]}, external_id="ext-1")
    bad = _ingest(client, wid, h, ds["id"], payload={"text": "terrible and broken"},
                  sentiment="negative", external_id="ext-2")
    assert good["sentiment"] == "positive"
    assert bad["sentiment"] == "negative"
    assert client.get(f"{_base(wid)}/datasets/{ds['id']}/records", headers=h,
                      params={"sentiment": "positive"}).json()[0]["id"] == good["id"]
    assert len(client.get(f"{_base(wid)}/datasets/{ds['id']}/records", headers=h,
                          params={"external_id": "ext-2"}).json()) == 1
    assert client.get(f"{_base(wid)}/records/{good['id']}", headers=h).json()["id"] == good["id"]
    patched = client.patch(f"{_base(wid)}/records/{good['id']}/sentiment", headers=h,
                           json={"sentiment": "neutral"}).json()
    assert patched["sentiment"] == "neutral"
    assert client.patch(f"{_base(wid)}/records/{bad['id']}/sentiment", headers=h,
                        json={"sentiment": "carrier-pigeon"}).status_code == 422
    event = db_session.execute(
        select(Event).where(Event.workspace_id == wid, Event.event_type == "feedback.record_ingested")
    ).scalars().first()
    assert event is not None and event.payload["reserved_capture_claimed"] is False


def test_fb085_segments_filter_real_contact_attributes(client):
    wid, h = _ctx(client)
    for email, plan, score in (
        ("pro@example.com", "pro", 8),
        ("low@example.com", "pro", 5),
        ("free@example.com", "free", 9),
    ):
        r = client.post(CONTACTS.format(wid=wid), headers=h,
                        json={"email": email, "custom_fields": {"plan": plan, "score": score}})
        assert r.status_code == 201, r.text
    seg = client.post(_base(wid) + "/segments", headers=h, json={
        "key": "pro-power", "name": "Pro power users",
        "rules": [{"field": "plan", "op": "eq", "value": "pro"},
                  {"field": "score", "op": "gte", "value": 7}],
    }).json()
    assert client.post(_base(wid) + "/segments", headers=h,
                       json={"key": "pro-power", "name": "dup"}).status_code == 409
    assert client.post(_base(wid) + "/segments", headers=h, json={
        "key": "bad", "name": "x", "rules": [{"field": "x", "op": "carrier-pigeon"}],
    }).status_code == 422
    result = client.post(f"{_base(wid)}/segments/{seg['id']}/evaluate", headers=h).json()
    assert result["evaluated"] == 3 and result["matched_count"] == 1
    assert result["contacts"][0]["email"] == "pro@example.com"


def test_fb096_dashboard_widgets_compute_live_from_stored_records(client):
    wid, h = _ctx(client)
    ds = _dataset(client, wid, h)
    s1 = _source(client, wid, h, ds["id"], "web", "web")
    s2 = _source(client, wid, h, ds["id"], "email", "email")
    for text, sentiment, sid in (
        ("Great", "positive", s1["id"]), ("Love it", "positive", s1["id"]),
        ("Awful", "negative", s2["id"]),
    ):
        _ingest(client, wid, h, ds["id"], payload={"text": text, "channel": "web"},
                sentiment=sentiment, reserved={"source_id": sid})
    dash = client.post(_base(wid) + "/dashboards", headers=h, json={
        "key": "overview", "name": "Overview",
        "widgets": [
            {"id": "sentiment", "type": "sentiment", "title": "Sentiment"},
            {"id": "sources", "type": "count_by_source", "title": "By source"},
            {"id": "volume", "type": "volume", "title": "Volume"},
            {"id": "channel", "type": "field", "field": "channel", "title": "Channel"},
        ],
    }).json()
    assert len(dash["widgets"]) == 4
    data = client.get(f"{_base(wid)}/dashboards/{dash['id']}/data", headers=h).json()
    assert data["source_record_count"] == 3
    by_type = {widget["type"]: widget["data"] for widget in data["widgets"]}
    assert by_type["sentiment"]["by_sentiment"] == {"positive": 2, "negative": 1}
    assert by_type["count_by_source"]["total"] == 3 and len(by_type["count_by_source"]["by_source"]) == 2
    assert by_type["volume"]["total"] == 3
    assert by_type["field"]["distribution"] == {"web": 3}
    # A new record changes the computed chart — this is real analytics.
    _ingest(client, wid, h, ds["id"], payload={"text": "Bad", "channel": "email"},
            sentiment="negative", reserved={"source_id": s2["id"]})
    again = client.get(f"{_base(wid)}/dashboards/{dash['id']}/data", headers=h).json()
    again_by_type = {widget["type"]: widget["data"] for widget in again["widgets"]}
    assert again_by_type["sentiment"]["by_sentiment"]["negative"] == 2
    assert again_by_type["field"]["distribution"]["email"] == 1


def test_fb097_unified_insights_aggregate_all_sources(client):
    wid, h = _ctx(client)
    ds1 = _dataset(client, wid, h, "web-feedback")
    ds2 = _dataset(client, wid, h, "email-feedback")
    w = _source(client, wid, h, ds1["id"], "web-form", "web")
    e = _source(client, wid, h, ds2["id"], "email-reply", "email")
    _ingest(client, wid, h, ds1["id"], payload={"text": "Excellent"},
            sentiment="positive", reserved={"page": "/home", "source_id": w["id"]})
    _ingest(client, wid, h, ds2["id"], payload={"text": "Slow"},
            sentiment="negative", reserved={"page": "/inbox", "source_id": e["id"]})
    insights = client.get(_base(wid) + "/unify/insights", headers=h).json()
    assert insights["total_records"] == 2
    assert insights["dataset_count"] == 2 and insights["source_count"] == 2
    assert insights["by_source_type"] == {"web": 1, "email": 1}
    assert insights["by_sentiment"] == {"positive": 1, "negative": 1}
    assert insights["reserved_field_coverage"]["page"] == 2
    assert insights["generated_at"]


def test_feedback_intelligence_workspace_isolation(client):
    wid, h = _ctx(client)
    ds = _dataset(client, wid, h)
    _source(client, wid, h, ds["id"])
    rec = _ingest(client, wid, h, ds["id"])
    field = client.post(_base(wid) + "/fields", headers=h,
                        json={"key": "shared", "label": "Shared"}).json()
    seg = client.post(_base(wid) + "/segments", headers=h,
                      json={"key": "all", "name": "All", "rules": []}).json()
    dash = client.post(_base(wid) + "/dashboards", headers=h,
                       json={"key": "dash", "name": "Dash", "widgets": [
                           {"id": "vol", "type": "volume"}]}).json()
    assert "id" in dash, dash
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh, owid = auth(other["access_token"]), other["workspace_id"]
    for path in ("/datasets", "/fields", "/segments", "/dashboards", "/unify/insights"):
        result = client.get(_base(owid) + path, headers=oh)
        assert result.status_code == 200, result.text
        payload = result.json()
        if isinstance(payload, list):
            assert payload == []
        else:
            assert payload["total_records"] == 0
    assert client.get(f"{_base(owid)}/records/{rec['id']}", headers=oh).status_code == 404
    assert client.patch(f"{_base(owid)}/fields/{field['id']}", headers=oh,
                        json={"label": "hack"}).status_code == 404
    assert client.post(f"{_base(owid)}/segments/{seg['id']}/evaluate", headers=oh).status_code == 404
    assert client.get(f"{_base(owid)}/dashboards/{dash['id']}/data", headers=oh).status_code == 404
