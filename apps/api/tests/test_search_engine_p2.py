"""Named acceptance tests for the clean-room local search engine cluster.

Every feature is exercised against real persisted workspace-scoped documents.
No external search service, embedding provider or SDK is contacted.
"""

from __future__ import annotations

from .conftest import auth, bootstrap


def _ctx(client):
    tokens = bootstrap(client)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid, name=None):
    path = f"/api/v1/workspaces/{wid}/search-engine"
    return path + (f"/indexes/{name}" if name else "")


def _index(client, wid, h, name="products"):
    r = client.post(_base(wid) + "/indexes", headers=h, json={"name": name})
    assert r.status_code == 201, r.text
    return name


def _docs(client, wid, h, name, docs):
    r = client.post(f"{_base(wid, name)}/documents", headers=h, json={"documents": docs})
    assert r.status_code == 202, r.text
    return r.json()


def _search(client, wid, h, name, **body):
    r = client.post(f"{_base(wid, name)}/search", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_ms041_index_creation_management_and_fields(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    assert name in [i["name"] for i in client.get(_base(wid) + "/indexes", headers=h).json()]
    assert client.post(_base(wid) + "/indexes", headers=h, json={"name": name}).status_code == 409
    _docs(client, wid, h, name, [{"id": "1", "title": "Phone", "brand": "Acme"}])
    fields = client.get(f"{_base(wid, name)}/fields", headers=h).json()
    names = {f["name"] for f in fields}
    assert {"id", "title", "brand"} <= names
    assert client.delete(_base(wid, name), headers=h).status_code == 204
    assert client.get(_base(wid, name) + "/settings", headers=h).status_code == 404


def test_ms044_047_batch_add_and_replace_documents(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    result = _docs(client, wid, h, name, [
        {"id": "1", "title": "Phone"}, {"id": "2", "title": "Laptop"},
        {"id": "3", "title": "Tablet"},
    ])
    assert result["documentCount"] == 3 and result["status"] == "enqueued"
    _docs(client, wid, h, name, [{"id": "2", "title": "Gaming Laptop"}])
    docs = client.get(f"{_base(wid, name)}/documents", headers=h).json()
    assert len(docs) == 3
    assert next(d for d in docs if d["documentId"] == "2")["data"]["title"] == "Gaming Laptop"
    assert client.post(f"{_base(wid, name)}/documents", headers=h,
                       json={"documents": [{"title": "no key"}]}).status_code == 422


def test_ms045_046_partial_update_and_delete(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [{"id": "1", "title": "Phone", "brand": "Acme"}])
    patched = client.patch(f"{_base(wid, name)}/documents/1", headers=h,
                           json={"data": {"brand": "NewCo"}})
    assert patched.status_code == 202
    assert patched.json()["data"] == {"id": "1", "title": "Phone", "brand": "NewCo"}
    assert client.delete(f"{_base(wid, name)}/documents/1", headers=h).status_code == 202
    assert client.get(f"{_base(wid, name)}/documents", headers=h).json() == []
    assert client.patch(f"{_base(wid, name)}/documents/missing", headers=h,
                        json={"data": {"x": 1}}).status_code == 404


def test_ms004_typo_tolerance(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [
        {"id": "1", "title": "Apple iPhone"}, {"id": "2", "title": "Samsung Galaxy"},
    ])
    tolerant = _search(client, wid, h, name, q="ipone")
    assert [x["documentId"] for x in tolerant["hits"]] == ["1"]
    client.patch(f"{_base(wid, name)}/settings", headers=h,
                 json={"typo_tolerance": {"enabled": False, "max_distance": 0, "min_word_length": 4}})
    assert _search(client, wid, h, name, q="ipone")["hits"] == []
    assert _search(client, wid, h, name, q="iphone")["hits"]


def test_ms016_synonyms(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [{"id": "1", "title": "A glad customer"}])
    client.patch(f"{_base(wid, name)}/settings", headers=h,
                 json={"synonyms": {"happy": ["glad", "joyful"]}})
    assert _search(client, wid, h, name, q="happy")["hits"][0]["documentId"] == "1"


def test_ms017_stop_words(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [{"id": "1", "title": "The quick brown fox"}])
    assert _search(client, wid, h, name, q="quick brown")["hits"]
    client.patch(f"{_base(wid, name)}/settings", headers=h, json={"stop_words": ["the", "quick"]})
    assert _search(client, wid, h, name, q="the quick")["hits"] == []
    assert _search(client, wid, h, name, q="brown")["hits"]


def test_ms018_019_separators_and_non_separators(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [{"id": "1", "title": "foo-bar baz"}])
    # With '-' as a separator the two parts are separate tokens.
    client.patch(f"{_base(wid, name)}/settings", headers=h, json={"separators": ["-"]})
    assert _search(client, wid, h, name, q="bar")["hits"]
    # With '-' as a non-separator the compound stays one token.
    client.patch(f"{_base(wid, name)}/settings", headers=h,
                 json={"separators": [], "non_separators": ["-"]})
    assert _search(client, wid, h, name, q="foobar")["hits"]


def test_ms020_dictionary(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [{"id": "1", "title": "J.P. Morgan joined today"}])
    client.patch(f"{_base(wid, name)}/settings", headers=h, json={"dictionary": ["J.P. Morgan"]})
    assert _search(client, wid, h, name, q="J.P. Morgan")["hits"]


def test_ms021_locale_and_tokenization(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    client.patch(f"{_base(wid, name)}/settings", headers=h, json={"locale": "fr"})
    settings = client.get(f"{_base(wid, name)}/settings", headers=h).json()
    assert settings["locale"] == "fr"
    _docs(client, wid, h, name, [{"id": "1", "title": "cafe libre"}])
    assert _search(client, wid, h, name, q="cafe")["hits"]


def test_ms025_026_027_highlight_crop_and_positions(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [{"id": "1", "title": "The quick brown fox jumps"}])
    hit = _search(client, wid, h, name, q="brown")["hits"][0]
    assert "<em>brown</em>" in hit["formatted"]["title"]
    assert hit["matchesPosition"]["title"]
    assert hit["matchesPosition"]["title"][0]["start"] == 10
    client.patch(f"{_base(wid, name)}/settings", headers=h, json={"crop_length": 10})
    cropped = _search(client, wid, h, name, q="brown")["hits"][0]["formatted"]["title"]
    assert "..." in cropped and len(cropped) < len("The quick brown fox jumps")


def test_ms029_phrase_search_and_term_exclusion(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [
        {"id": "1", "title": "quick brown fox"}, {"id": "2", "title": "brown quick fox"},
    ])
    assert [x["documentId"] for x in _search(client, wid, h, name, q='"quick brown"')["hits"]] == ["1"]
    assert [x["documentId"] for x in _search(client, wid, h, name, q="fox -quick")["hits"]] == []


def test_ms031_placeholder_search(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [
        {"id": "1", "title": "iPhone"}, {"id": "2", "title": "Galaxy"},
    ])
    assert [x["documentId"] for x in _search(client, wid, h, name, q="ip*")["hits"]] == ["1"]


def test_ms030_matching_strategy(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [
        {"id": "1", "title": "red apple", "brand": "fresh"},
        {"id": "2", "title": "green apple", "brand": "fresh"},
    ])
    client.patch(f"{_base(wid, name)}/settings", headers=h, json={"matching_strategy": "last"})
    assert len(_search(client, wid, h, name, q="apple fresh")["hits"]) == 2
    client.patch(f"{_base(wid, name)}/settings", headers=h, json={"matching_strategy": "any"})
    assert len(_search(client, wid, h, name, q="apple fresh")["hits"]) == 2
    assert _search(client, wid, h, name, q="apple missing")["hits"]


def test_ms012_013_ranking_rules_and_score_details(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [
        {"id": "1", "title": "Phone", "rank": 1}, {"id": "2", "title": "Phone case", "rank": 9},
    ])
    hit = _search(client, wid, h, name, q="Phone")["hits"][0]
    assert hit["documentId"] == "1"  # exact match wins
    assert "rankingScore" in hit["scoreDetails"]
    assert "exactness" in hit["scoreDetails"]
    client.patch(f"{_base(wid, name)}/settings", headers=h,
                 json={"ranking_rules": ["exactness", "typo"]})
    details = _search(client, wid, h, name, q="Phone")["hits"][0]["scoreDetails"]
    assert "exactness" in details and "typo" in details and "words" not in details


def test_ms007_008_facets_and_facet_search(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [
        {"id": "1", "title": "Phone", "brand": "Acme", "color": ["red", "blue"]},
        {"id": "2", "title": "Phone case", "brand": "Acme", "color": ["green"]},
        {"id": "3", "title": "Laptop", "brand": "Globex", "color": ["blue"]},
    ])
    client.patch(f"{_base(wid, name)}/settings", headers=h,
                 json={"filterable_attributes": ["brand", "color"]})
    result = _search(client, wid, h, name, q="Phone")
    assert result["facets"]["brand"]["Acme"] == 2
    assert result["facets"]["color"]["blue"] == 1
    exact = _search(client, wid, h, name, q="Phone", facet_query={"color": "re"})
    assert exact["facetSearch"]["color"] == ["red"]
    none = _search(client, wid, h, name, q="Phone", facet_query={"color": "yellow"})
    assert none["facetSearch"]["color"] == []


def test_ms023_024_geo_search_and_distance_sort(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [
        {"id": "1", "title": "Near", "_geo": {"lat": 17.38, "lng": 78.48}},
        {"id": "2", "title": "Far", "_geo": {"lat": 28.61, "lng": 77.20}},
    ])
    near = _search(client, wid, h, name, q="*", geo_lat=17.38, geo_lng=78.48, geo_radius=5000)
    assert [x["documentId"] for x in near["hits"]] == ["1"]
    assert near["hits"][0]["data"]["_geoDistance"] <= 5000
    allhits = _search(client, wid, h, name, q="*",
                      sort_by="_geoDistance(17.38,78.48):asc")
    assert [x["documentId"] for x in allhits["hits"]] == ["1", "2"]


def test_ms032_distinct_attribute(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [
        {"id": "1", "title": "Phone one", "brand": "Acme"},
        {"id": "2", "title": "Phone two", "brand": "Acme"},
        {"id": "3", "title": "Phone three", "brand": "Globex"},
    ])
    client.patch(f"{_base(wid, name)}/settings", headers=h, json={"distinct_attribute": "brand"})
    hits = _search(client, wid, h, name, q="Phone")["hits"]
    assert len(hits) == 2
    assert {x["data"]["brand"] for x in hits} == {"Acme", "Globex"}


def test_ms033_proximity_precision(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [
        {"id": "1", "title": "brown fox jumps"}, {"id": "2", "title": "brown quick clever fox"},
    ])
    hits = _search(client, wid, h, name, q="brown fox")["hits"]
    assert hits[0]["documentId"] == "1"  # closer words score higher
    assert "proximity" in hits[0]["scoreDetails"]


def test_ms034_search_cutoff(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    docs = [{"id": str(i), "title": f"widget {i}"} for i in range(120)]
    _docs(client, wid, h, name, docs)
    allhits = _search(client, wid, h, name, q="widget")
    assert allhits["totalHits"] == 120
    client.patch(f"{_base(wid, name)}/settings", headers=h, json={"search_cutoff_ms": 1})
    limited = _search(client, wid, h, name, q="widget")
    assert 0 < limited["totalHits"] <= 120
    assert limited["processingTimeMs"] >= 0


def test_ms035_per_query_searchable_attributes(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [
        {"id": "1", "title": "Phone", "description": "acme gadget"},
    ])
    assert _search(client, wid, h, name, q="acme")["hits"]
    only_title = _search(client, wid, h, name, q="acme", searchable_attributes=["title"])
    assert only_title["hits"] == []
    assert _search(client, wid, h, name, q="Phone",
                   searchable_attributes=["title"])["hits"][0]["documentId"] == "1"


def test_ms040_settings_api(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    settings = client.get(f"{_base(wid, name)}/settings", headers=h).json()
    assert settings["ranking_rules"] and settings["matching_strategy"] == "last"
    patched = client.patch(f"{_base(wid, name)}/settings", headers=h,
                           json={"sortable_attributes": ["rank"], "crop_length": 50})
    assert patched.status_code == 200
    body = patched.json()
    assert body["sortable_attributes"] == ["rank"] and body["crop_length"] == 50
    assert client.patch(f"{_base(wid, name)}/settings", headers=h,
                        json={"matching_strategy": "bogus"}).status_code == 422


def test_ms057_061_version_and_feature_flags(client):
    wid, h = _ctx(client)
    version = client.get(_base(wid) + "/version", headers=h).json()
    assert version["version"].startswith("novara-search/")
    features = client.get(_base(wid) + "/features", headers=h).json()
    assert "facet_search" in features["features"] and features["enabled"]["geo_search"] is True


def test_search_engine_workspace_isolation(client):
    wid, h = _ctx(client)
    name = _index(client, wid, h)
    _docs(client, wid, h, name, [{"id": "1", "title": "Secret product"}])
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh, owid = auth(other["access_token"]), other["workspace_id"]
    assert client.get(_base(owid) + "/indexes", headers=oh).json() == []
    assert client.get(f"{_base(owid, name)}/settings", headers=oh).status_code == 404
    assert client.post(f"{_base(owid, name)}/search", headers=oh,
                       json={"q": "Secret"}).status_code == 404
