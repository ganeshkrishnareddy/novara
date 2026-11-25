"""Named acceptance tests for the clean-room document engagement cluster.

Every test drives the real FastAPI app with real persisted workspace-scoped
rows. No Papermark source, hosted viewer, outbound email, geolocation service
or external analytics provider is used.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/document-engagement"
DOCS = "/api/v1/workspaces/{wid}/documents"


def _ctx(client):
    tokens = bootstrap(client, "Engagement", "engagement@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _doc(client, wid, h, title="Quarterly report", doc_type="pdf"):
    response = client.post(DOCS.format(wid=wid), headers=h, json={
        "title": title, "doc_type": doc_type, "storage_path": "metadata://eng/doc.pdf",
    })
    assert response.status_code == 201, response.text
    return response.json()


def _version(client, wid, h, document_id, storage_path="metadata://eng/v2.pdf"):
    response = client.post(DOCS.format(wid=wid) + f"/{document_id}/versions", headers=h,
                           json={"storage_path": storage_path})
    assert response.status_code == 201, response.text
    return response.json()


def _folder(client, wid, h, name="Archive"):
    response = client.post(DOCS.format(wid=wid) + "/folders", headers=h, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_pm007_document_metadata_rename_and_folder_move(client):
    """A document can be renamed and moved into a team-library folder."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    folder = _folder(client, wid, h)
    result = client.patch(_base(wid) + f"/documents/{doc['id']}/metadata", headers=h,
                          json={"title": "Renamed report", "folder_id": folder["id"]})
    assert result.status_code == 200, result.text
    assert result.json()["title"] == "Renamed report"
    assert result.json()["folder_id"] == folder["id"]
    assert client.patch(_base(wid) + f"/documents/{doc['id']}/metadata", headers=h,
                        json={"folder_id": "missing-folder"}).status_code == 404
    assert client.patch(_base(wid) + f"/documents/{doc['id']}/metadata", headers=h,
                        json={}).status_code == 422
    cleared = client.patch(_base(wid) + f"/documents/{doc['id']}/metadata", headers=h,
                           json={"clear_folder": True})
    assert cleared.json()["folder_id"] is None


def test_pm010_version_promotion_and_link_repoint(client):
    """Promoting a version makes it primary and can repoint an external URL."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    first = _version(client, wid, h, doc["id"], "metadata://eng/v1.pdf")
    second = _version(client, wid, h, doc["id"], "metadata://eng/v2.pdf")
    result = client.post(_base(wid) + f"/documents/{doc['id']}/versions/{first['id']}/promote",
                         headers=h, json={"external_url": "https://notion.local/page"})
    assert result.status_code == 200, result.text
    assert result.json()["is_primary"] is True
    assert result.json()["external_url"] == "https://notion.local/page"
    versions = client.get(DOCS.format(wid=wid) + f"/{doc['id']}/versions", headers=h).json()
    primary = [v for v in versions if v["is_primary"]]
    assert len(primary) == 1 and primary[0]["id"] == first["id"]
    assert client.post(_base(wid) + f"/documents/{doc['id']}/versions/missing/promote",
                       headers=h, json={}).status_code == 404


def test_pm018_document_name_search_is_case_insensitive(client):
    """Name search matches a case-insensitive substring within the workspace."""
    wid, h = _ctx(client)
    _doc(client, wid, h, "Alpha Proposal")
    _doc(client, wid, h, "Beta proposal draft")
    _doc(client, wid, h, "Budget sheet")
    result = client.get(_base(wid) + "/documents/search", headers=h, params={"q": "PROPOSAL"})
    assert result.status_code == 200, result.text
    titles = {d["title"] for d in result.json()}
    assert titles == {"Alpha Proposal", "Beta proposal draft"}
    assert client.get(_base(wid) + "/documents/search", headers=h,
                      params={"q": ""}).status_code == 422


def test_pm024_reactions_are_deduplicated_and_removable(client):
    """Page reactions persist, deduplicate per user and can be removed."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    reaction = client.post(_base(wid) + f"/documents/{doc['id']}/reactions", headers=h,
                           json={"key": "like", "page_number": 2})
    assert reaction.status_code == 201, reaction.text
    assert client.post(_base(wid) + f"/documents/{doc['id']}/reactions", headers=h,
                       json={"key": "like", "page_number": 2}).status_code == 409
    assert client.post(_base(wid) + f"/documents/{doc['id']}/reactions", headers=h,
                       json={"key": "shrug"}).status_code == 422
    rows = client.get(_base(wid) + f"/documents/{doc['id']}/reactions", headers=h).json()
    assert len(rows) == 1 and rows[0]["page_number"] == 2
    removed = client.delete(_base(wid) + f"/documents/{doc['id']}/reactions/{reaction.json()['id']}",
                            headers=h)
    assert removed.status_code == 200
    assert client.get(_base(wid) + f"/documents/{doc['id']}/reactions", headers=h).json() == []


def test_pm025_feedback_records_rating_and_author(client):
    """Document feedback stores a validated rating and author."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    response = client.post(_base(wid) + f"/documents/{doc['id']}/feedback", headers=h,
                           json={"body": "Very clear", "rating": 5, "author": "viewer@local"})
    assert response.status_code == 201, response.text
    assert client.post(_base(wid) + f"/documents/{doc['id']}/feedback", headers=h,
                       json={"body": "bad", "rating": 9}).status_code == 422
    rows = client.get(_base(wid) + f"/documents/{doc['id']}/feedback", headers=h).json()
    assert rows[0]["rating"] == 5 and rows[0]["author"] == "viewer@local"
    assert rows[0]["status"] == "open"


def test_pm027_annotations_attach_to_pages_and_versions(client):
    """Annotations persist with kind, page, position and an optional version."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    version = _version(client, wid, h, doc["id"])
    response = client.post(_base(wid) + f"/documents/{doc['id']}/annotations", headers=h,
                           json={"page_number": 3, "kind": "highlight", "content": "Key clause",
                                 "position": {"x": 10, "y": 20}, "version_id": version["id"]})
    assert response.status_code == 201, response.text
    assert client.post(_base(wid) + f"/documents/{doc['id']}/annotations", headers=h,
                       json={"page_number": 1, "kind": "teleport", "content": "x"}).status_code == 422
    assert client.post(_base(wid) + f"/documents/{doc['id']}/annotations", headers=h,
                       json={"page_number": 1, "kind": "note", "content": "x",
                             "version_id": "missing"}).status_code == 404
    rows = client.get(_base(wid) + f"/documents/{doc['id']}/annotations", headers=h).json()
    assert rows[0]["kind"] == "highlight" and rows[0]["position"]["x"] == 10


def test_pm076_scroll_depth_and_completion_are_aggregated(client):
    """Analytics compute average scroll depth and completion rate."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    for depth, completed in ((40, False), (80, True), (100, True)):
        response = client.post(_base(wid) + f"/documents/{doc['id']}/events", headers=h,
                               json={"event_type": "scroll", "visitor": "v1",
                                     "scroll_depth": depth, "completed": completed})
        assert response.status_code == 201, response.text
    assert client.post(_base(wid) + f"/documents/{doc['id']}/events", headers=h,
                       json={"event_type": "scroll", "scroll_depth": 150}).status_code == 422
    analytics = client.get(_base(wid) + f"/documents/{doc['id']}/analytics", headers=h).json()
    assert analytics["avg_scroll_depth"] == 73.33
    assert analytics["completion_rate"] == 0.6667


def test_pm077_video_view_analytics_are_recorded(client):
    """Video engagement events contribute position analytics."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    for position in (10.0, 30.0):
        client.post(_base(wid) + f"/documents/{doc['id']}/events", headers=h,
                    json={"event_type": "video", "visitor": "v1",
                          "video_position_s": position, "video_duration_s": 120.0})
    analytics = client.get(_base(wid) + f"/documents/{doc['id']}/analytics", headers=h).json()
    assert analytics["video"]["views"] == 2
    assert analytics["video"]["avg_position_s"] == 20.0


def test_pm083_visitor_location_is_caller_supplied_metadata(client):
    """Country/city analytics aggregate caller-supplied location, no external lookup."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    for country, city in (("IN", "Bengaluru"), ("IN", "Bengaluru"), ("US", "Austin")):
        client.post(_base(wid) + f"/documents/{doc['id']}/events", headers=h,
                    json={"event_type": "view", "visitor": "v1", "country": country, "city": city})
    analytics = client.get(_base(wid) + f"/documents/{doc['id']}/analytics", headers=h).json()
    assert analytics["external_geolocation"] is False
    assert analytics["views"] == 3
    locations = {(l["country"], l["city"]): l["count"] for l in analytics["locations"]}
    assert locations[("IN", "Bengaluru")] == 2 and locations[("US", "Austin")] == 1


def test_pm084_device_os_and_platform_analytics(client):
    """Client information per view is aggregated by device and platform."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    for device, os_name, platform in (("desktop", "windows", "web"),
                                      ("mobile", "ios", "web"),
                                      ("desktop", "windows", "web")):
        client.post(_base(wid) + f"/documents/{doc['id']}/events", headers=h,
                    json={"event_type": "view", "visitor": "v1",
                          "device": device, "os": os_name, "platform": platform})
    analytics = client.get(_base(wid) + f"/documents/{doc['id']}/analytics", headers=h).json()
    devices = {d["value"]: d["count"] for d in analytics["devices"]}
    assert devices["desktop"] == 2 and devices["mobile"] == 1
    assert analytics["platforms"][0]["value"] == "web"


def test_pm085_internal_visits_are_excluded_from_analytics(client):
    """Registering internal visitors keeps their events out of analytics."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    added = client.post(_base(wid) + "/internal-visitors", headers=h,
                        json={"match_type": "email_domain", "value": "novara.local"})
    assert added.status_code == 201, added.text
    assert client.post(_base(wid) + "/internal-visitors", headers=h,
                       json={"match_type": "email_domain", "value": "novara.local"}).status_code == 409
    assert client.post(_base(wid) + "/internal-visitors", headers=h,
                       json={"match_type": "ip", "value": "1.2.3.4"}).status_code == 422
    internal = client.post(_base(wid) + f"/documents/{doc['id']}/events", headers=h,
                           json={"event_type": "view", "visitor": "team@novara.local"})
    assert internal.json()["is_internal"] is True
    client.post(_base(wid) + f"/documents/{doc['id']}/events", headers=h,
                json={"event_type": "view", "visitor": "guest@external.com"})
    analytics = client.get(_base(wid) + f"/documents/{doc['id']}/analytics", headers=h).json()
    assert analytics["views"] == 1 and analytics["excluded_internal"] == 1
    removed = client.delete(_base(wid) + f"/internal-visitors/{added.json()['id']}", headers=h)
    assert removed.status_code == 200


def test_pm091_click_route_records_target_and_counts(client):
    """The dedicated click route records a target and feeds click analytics."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    response = client.post(_base(wid) + f"/documents/{doc['id']}/click", headers=h,
                           json={"visitor": "v1", "target": "https://cta.local/signup"})
    assert response.status_code == 201, response.text
    assert response.json()["event_type"] == "click"
    assert client.post(_base(wid) + f"/documents/{doc['id']}/click", headers=h,
                       json={"visitor": "v1", "target": ""}).status_code == 422
    analytics = client.get(_base(wid) + f"/documents/{doc['id']}/analytics", headers=h).json()
    assert analytics["clicks"] == 1


def test_document_engagement_workspace_isolation(client):
    """A second workspace cannot address this workspace's engagement rows."""
    wid, h = _ctx(client)
    doc = _doc(client, wid, h)
    reaction = client.post(_base(wid) + f"/documents/{doc['id']}/reactions", headers=h,
                           json={"key": "love"}).json()
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other engagement"})
    assert other.status_code == 200
    other_wid, other_h = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(other_wid) + f"/documents/{doc['id']}/analytics", headers=h).status_code == 403
    assert client.get(_base(other_wid) + f"/documents/{doc['id']}/reactions", headers=other_h).status_code == 404
    assert client.post(_base(other_wid) + f"/documents/{doc['id']}/events", headers=other_h,
                       json={"event_type": "view"}).status_code == 404
    assert client.delete(_base(other_wid) + f"/documents/{doc['id']}/reactions/{reaction['id']}",
                         headers=other_h).status_code == 404
    assert client.get(_base(other_wid) + "/internal-visitors", headers=other_h).json() == []