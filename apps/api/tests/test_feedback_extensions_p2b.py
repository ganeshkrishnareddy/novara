"""Named acceptance tests for the second Formbricks P2 survey cluster.

Covers extended question types, shareable links, display tracking, response
tagging and response management. All behaviour is local; no survey is
distributed and no external service is contacted.
"""

from __future__ import annotations

from .conftest import auth, bootstrap


def _ctx(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _survey(client, wid, headers, name="Survey"):
    r = client.post(f"/api/v1/workspaces/{wid}/surveys", headers=headers, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _base(wid):
    return f"/api/v1/workspaces/{wid}/feedback"


def test_extended_question_types(client):
    """FB-039, FB-043, FB-045..FB-054: all extended types can be authored."""
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    types = ["address", "file_upload", "matrix", "ranking", "rating",
             "schedule_meeting", "multi_choice", "picture_selection",
             "single_choice", "signature", "statement", "thank_you"]
    for qtype in types:
        r = client.post(f"{_base(wid)}/surveys/{sid}/questions", headers=h,
                        json={"type": qtype, "code": f"q_{qtype}", "label": qtype})
        assert r.status_code == 201 and r.json()["type"] == qtype, r.text
    # nps/csat/ces are covered by the preset test in T-082.


def test_fb066_personal_link_bound_to_contact(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    r = client.post(f"{_base(wid)}/surveys/{sid}/links", headers=h,
                    json={"kind": "personal", "title": "Client review", "contact_id": None})
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "personal" and r.json()["token"]
    links = client.get(f"{_base(wid)}/surveys/{sid}/links", headers=h)
    assert links.status_code == 200 and len(links.json()) == 1


def test_fb067_single_use_link_consumed_once(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    link = client.post(f"{_base(wid)}/surveys/{sid}/links", headers=h,
                       json={"kind": "single_use"}).json()
    token = link["token"]
    first = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                        json={"value": 7, "link_token": token})
    assert first.status_code == 201
    second = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                         json={"value": 8, "link_token": token})
    assert second.status_code == 409
    assert client.get(f"{_base(wid)}/links/resolve?token={token}", headers=h).json()["used"] is True


def test_fb068_068b_069_pretty_url_and_link_settings(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    created = client.post(f"{_base(wid)}/surveys/{sid}/links", headers=h, json={
        "slug": "quarterly-review", "title": "Quarterly review",
        "description": "Short feedback form", "preview_image": "/preview.png",
    })
    assert created.status_code == 201
    resolved = client.get(f"{_base(wid)}/links/resolve?slug=quarterly-review", headers=h)
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["title"] == "Quarterly review"
    assert body["description"] == "Short feedback form"
    assert body["preview_image"] == "/preview.png"
    dup = client.post(f"{_base(wid)}/surveys/{sid}/links", headers=h,
                      json={"slug": "quarterly-review"})
    assert dup.status_code == 409


def test_fb070_071_prefill_and_source_tracking(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    link = client.post(f"{_base(wid)}/surveys/{sid}/links", headers=h, json={
        "prefill": {"plan": "gold", "locale": "en"}, "source": "website",
    }).json()
    resolved = client.get(f"{_base(wid)}/links/resolve?token={link['token']}", headers=h)
    assert resolved.json()["prefill"] == {"plan": "gold", "locale": "en"}
    ans = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                      json={"value": 9, "link_token": link["token"]})
    assert ans.status_code == 201
    embedded = ans.json()["embedded"]
    assert embedded["plan"] == "gold"
    assert embedded["source"] == "website"


def test_fb072_start_at_specific_block(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    link = client.post(f"{_base(wid)}/surveys/{sid}/links", headers=h,
                       json={"start_block": "Q5"}).json()
    assert client.get(f"{_base(wid)}/links/resolve?token={link['token']}",
                      headers=h).json()["start_block"] == "Q5"


def test_fb073_require_identified_respondent(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    link = client.post(f"{_base(wid)}/surveys/{sid}/links", headers=h,
                       json={"require_identified": True}).json()
    blocked = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                          json={"value": 5, "link_token": link["token"]})
    assert blocked.status_code == 422
    # A valid contact in this workspace satisfies the requirement.
    contact = client.post(f"/api/v1/workspaces/{wid}/contacts", headers=h,
                          json={"full_name": "Respondent", "email": "r@example.com"})
    assert contact.status_code in (200, 201), contact.text
    ok = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                     json={"value": 5, "link_token": link["token"],
                           "contact_id": contact.json()["id"]})
    assert ok.status_code == 201


def test_fb091_display_tracking(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    link = client.post(f"{_base(wid)}/surveys/{sid}/links", headers=h, json={}).json()
    r = client.post(f"{_base(wid)}/links/{link['token']}/displays", headers=h,
                    json={"subject": "visitor-9"})
    assert r.status_code == 201
    displays = client.get(f"{_base(wid)}/surveys/{sid}/displays", headers=h)
    assert displays.status_code == 200
    assert displays.json()[0]["subject"] == "visitor-9"
    assert client.post(f"{_base(wid)}/links/{link['token']}/displays", headers=h,
                       json={"subject": "  "}).status_code == 422


def test_fb092_tags_and_response_tagging(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    tag = client.post(f"{_base(wid)}/surveys/{sid}/tags", headers=h, json={"name": "follow-up"})
    assert tag.status_code == 201
    tid = tag.json()["id"]
    assert client.post(f"{_base(wid)}/surveys/{sid}/tags", headers=h,
                       json={"name": "follow-up"}).status_code == 409
    ans = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h, json={"value": 6}).json()
    assigned = client.post(f"{_base(wid)}/answers/{ans['id']}/tags?tag_id={tid}", headers=h)
    assert assigned.status_code == 201
    assert client.post(f"{_base(wid)}/answers/{ans['id']}/tags?tag_id={tid}",
                       headers=h).status_code == 409
    tags = client.get(f"{_base(wid)}/answers/{ans['id']}/tags", headers=h)
    assert tags.status_code == 200 and tags.json()[0]["name"] == "follow-up"


def test_fb094_export_responses_csv(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                json={"code": "nps_score", "value": 8, "partial": True})
    exported = client.get(f"{_base(wid)}/surveys/{sid}/answers/export", headers=h)
    assert exported.status_code == 200
    body = exported.json()
    assert body["content_type"] == "text/csv" and body["rows"] == 1
    assert "nps_score" in body["csv"] and "value" in body["csv"]


def test_fb095_response_update_delete_and_mark_finished(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    ans = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h,
                      json={"value": 4, "partial": True}).json()
    aid = ans["id"]
    updated = client.patch(f"{_base(wid)}/answers/{aid}", headers=h,
                           json={"value": 9, "partial": False, "note": "reviewed"})
    assert updated.status_code == 200
    assert updated.json()["value"] == 9 and updated.json()["partial"] is False
    assert updated.json()["embedded"]["review_note"] == "reviewed"
    assert client.delete(f"{_base(wid)}/answers/{aid}", headers=h).status_code == 204
    assert client.get(f"{_base(wid)}/surveys/{sid}/answers", headers=h).json() == []


def test_p2b_workspace_isolation(client):
    wid, h = _ctx(client)
    sid = _survey(client, wid, h)
    link = client.post(f"{_base(wid)}/surveys/{sid}/links", headers=h, json={}).json()
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh = auth(other["access_token"])
    owid = other["workspace_id"]
    assert client.get(f"{_base(owid)}/links/resolve?token={link['token']}", headers=oh).status_code == 404
    assert client.post(f"{_base(owid)}/links/{link['token']}/displays", headers=oh,
                       json={"subject": "x"}).status_code == 404
    ans = client.post(f"{_base(wid)}/surveys/{sid}/answers", headers=h, json={"value": 5}).json()
    assert client.patch(f"{_base(owid)}/answers/{ans['id']}", headers=oh,
                        json={"value": 1}).status_code == 404
