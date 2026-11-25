"""Named acceptance tests for the clean-room advanced search cluster.

Every test drives the real FastAPI app with real persisted workspace-scoped
rows. No Meilisearch server, embedding model, external SDK or hosted demo is
used. All embeddings are deterministic local hashes.
"""

from __future__ import annotations

from .conftest import auth, bootstrap

BASE = "/api/v1/workspaces/{wid}/search-advanced"
ENGINE = "/api/v1/workspaces/{wid}/search-engine"


def _ctx(client):
    tokens = bootstrap(client, "Advanced search", "search@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return BASE.format(wid=wid)


def _index(client, wid, h, name="products"):
    response = client.post(ENGINE.format(wid=wid) + "/indexes", headers=h, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _docs(client, wid, h, name, documents):
    response = client.post(ENGINE.format(wid=wid) + f"/indexes/{name}/documents", headers=h,
                           json={"documents": documents})
    assert response.status_code == 202, response.text
    return response.json()


def _embedder(client, wid, h, name, embedder_name="text", **extra):
    body = {"name": embedder_name, "kind": "local_text", "dimensions": 32}
    body.update(extra)
    response = client.post(_base(wid) + f"/indexes/{name}/embedders", headers=h, json=body)
    assert response.status_code == 201, response.text
    return response.json()


PRODUCTS = [
    {"id": "1", "title": "Running shoes", "brand": "Acme", "price": 80},
    {"id": "2", "title": "Trail shoes", "brand": "Acme", "price": 95},
    {"id": "3", "title": "Desk lamp", "brand": "Lumen", "price": 40},
]


def test_ms001_hybrid_search_combines_local_semantic_and_lexical_scores(client):
    """Hybrid search ranks documents using an explicit semantic/lexical blend."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    _docs(client, wid, h, "products", PRODUCTS)
    _embedder(client, wid, h, "products")
    result = client.post(_base(wid) + "/indexes/products/search/hybrid", headers=h,
                         json={"q": "running shoes", "embedder_name": "text",
                               "semantic_weight": 0.7, "limit": 2})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["hybrid"] is True
    assert len(body["results"]) == 2
    for row in body["results"]:
        assert 0.0 <= row["score"] <= 1.0
        assert "semantic" in row and "lexical" in row


def test_ms022_localized_attributes_and_query_locales_are_recorded(client):
    """Locale-specific attributes and query overrides persist on an index."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    response = client.post(_base(wid) + "/indexes/products/locales", headers=h, json={
        "attribute_pattern": "title*", "locale": "fr", "query_locale": "fr",
    })
    assert response.status_code == 201, response.text
    locales = client.get(_base(wid) + "/indexes/products/locales", headers=h).json()
    assert locales[0]["locale"] == "fr" and locales[0]["query_locale"] == "fr"


def test_ms036_suggestions_return_prefix_matches_from_indexed_attributes(client):
    """Suggestions expose prefix matches from a configured attribute."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    _docs(client, wid, h, "products", PRODUCTS)
    config = client.post(_base(wid) + "/indexes/products/suggestions", headers=h,
                         json={"key": "titles", "attribute": "title"})
    assert config.status_code == 201
    assert client.post(_base(wid) + "/indexes/products/suggestions", headers=h,
                       json={"key": "titles", "attribute": "brand"}).status_code == 409
    result = client.post(_base(wid) + "/indexes/products/suggest", headers=h,
                         json={"q": "run", "limit": 5})
    assert result.json()["suggestions"] == ["Running shoes"]


def test_ms038_federated_weights_merge_results_from_multiple_indexes(client):
    """Federated search applies per-index weights to merged scores."""
    wid, h = _ctx(client)
    _index(client, wid, h, "products")
    _index(client, wid, h, "articles")
    _docs(client, wid, h, "products", PRODUCTS[:1])
    _docs(client, wid, h, "articles", [{"id": "a1", "title": "Running guide"}])
    federation = client.post(_base(wid) + "/federations", headers=h, json={
        "key": "shop-and-learn",
        "members": [{"index": "products", "weight": 2}, {"index": "articles", "weight": 1}],
    })
    assert federation.status_code == 201, federation.text
    assert client.post(_base(wid) + "/federations", headers=h,
                       json={"key": "bad", "members": []}).status_code == 422
    result = client.post(_base(wid) + f"/federations/{federation.json()['id']}/search", headers=h,
                         json={"q": "running", "limit": 10})
    rows = result.json()["results"]
    assert {r["index"] for r in rows} == {"products", "articles"}
    assert all(r["score"] > 0 for r in rows)


def test_ms042_index_swap_moves_documents_and_settings_atomically(client):
    """Index swap exchanges documents and settings between two indexes."""
    wid, h = _ctx(client)
    _index(client, wid, h, "left")
    _index(client, wid, h, "right")
    _docs(client, wid, h, "left", [{"id": "l1", "title": "Left item"}])
    _docs(client, wid, h, "right", [{"id": "r1", "title": "Right item"}])
    result = client.post(_base(wid) + "/indexes/left/swap", headers=h,
                         json={"right_index": "right"})
    assert result.status_code == 200, result.text
    assert result.json()["documents_swapped"] == 2
    assert client.post(_base(wid) + "/indexes/left/swap", headers=h,
                       json={"right_index": "left"}).status_code == 422
    swapped = client.post(ENGINE.format(wid=wid) + "/indexes/left/search", headers=h,
                          json={"q": "Right"})
    assert swapped.status_code == 200
    assert any(hit["documentId"] == "r1" for hit in swapped.json()["hits"])


def test_ms048_edit_documents_by_function_transforms_selected_fields(client):
    """A deterministic edit function transforms document attributes."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    _docs(client, wid, h, "products", PRODUCTS)
    result = client.post(_base(wid) + "/indexes/products/documents/edit-function", headers=h,
                         json={"attribute": "title", "op": "upper", "document_ids": ["1"]})
    assert result.status_code == 200, result.text
    assert result.json()["changed"] == 1
    assert client.post(_base(wid) + "/indexes/products/documents/edit-function", headers=h,
                       json={"attribute": "title", "op": "teleport"}).status_code == 422
    docs = client.get(ENGINE.format(wid=wid) + "/indexes/products/documents", headers=h).json()
    titles = {d["documentId"]: d["data"]["title"] for d in docs}
    assert titles["1"] == "RUNNING SHOES"
    assert titles["2"] == "Trail shoes"


def test_ms053_index_and_task_queue_compactions_are_recorded(client):
    """Compaction operations are recorded locally with counted documents."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    _docs(client, wid, h, "products", PRODUCTS)
    for kind in ("index", "task_queue"):
        result = client.post(_base(wid) + "/indexes/products/compact", headers=h,
                             json={"kind": kind})
        assert result.status_code == 201, result.text
        assert result.json()["external_service"] is False
    assert client.post(_base(wid) + "/indexes/products/compact", headers=h,
                       json={"kind": "disk"}).status_code == 422
    rows = client.get(_base(wid) + "/indexes/products/compactions", headers=h).json()
    assert {r["kind"] for r in rows} == {"index", "task_queue"}
    assert all(r["document_count"] == 3 for r in rows)


def test_ms074_similar_documents_are_ranked_by_local_vector_similarity(client):
    """Similar documents are ranked from deterministic local embeddings."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    _docs(client, wid, h, "products", [
        {"id": "a", "title": "alpha alpha alpha"},
        {"id": "b", "title": "beta beta beta"},
    ])
    _embedder(client, wid, h, "products")
    result = client.post(_base(wid) + "/indexes/products/similar", headers=h,
                         json={"document_id": "a", "embedder_name": "text", "limit": 5})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["reference"] == "a" and len(body["results"]) == 1
    assert body["results"][0]["document_id"] == "b"
    assert 0.0 <= body["results"][0]["similarity"] <= 1.0
    assert client.post(_base(wid) + "/indexes/products/similar", headers=h,
                       json={"document_id": "missing", "embedder_name": "text"}).status_code == 404


def test_ms075_embedders_store_local_vector_settings_without_external_models(client):
    """Embedder settings are local; external sources are rejected."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    response = client.post(_base(wid) + "/indexes/products/embedders", headers=h, json={
        "name": "configured", "kind": "local_image", "dimensions": 64,
        "config": {"source": "local", "model": "novara-hash-1"},
    })
    assert response.status_code == 201, response.text
    assert client.post(_base(wid) + "/indexes/products/embedders", headers=h, json={
        "name": "bad", "kind": "openai", "dimensions": 32,
    }).status_code == 422
    assert client.post(_base(wid) + "/indexes/products/embedders", headers=h, json={
        "name": "bad-source", "kind": "local_text", "config": {"source": "hosted"},
    }).status_code == 422
    rows = client.get(_base(wid) + "/indexes/products/embedders", headers=h).json()
    assert rows[0]["dimensions"] == 64 and rows[0]["kind"] == "local_image"


def test_ms076_user_provided_embeddings_accept_custom_vectors_only(client):
    """User-provided embedders accept custom vectors with strict dimensions."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    client.post(_base(wid) + "/indexes/products/embedders", headers=h, json={
        "name": "custom", "kind": "user_provided", "dimensions": 8,
    })
    assert client.post(_base(wid) + "/indexes/products/vectors", headers=h, json={
        "embedder_name": "custom", "document_id": "1", "vector": [0.1] * 7,
    }).status_code == 422
    stored = client.post(_base(wid) + "/indexes/products/vectors", headers=h, json={
        "embedder_name": "custom", "document_id": "1",
        "vector": [0.1, -0.2, 0.3, 0.0, 0.5, -0.6, 0.7, 0.8],
    })
    assert stored.status_code == 201 and stored.json()["stored_local"] is True
    _embedder(client, wid, h, "products", "text")
    assert client.post(_base(wid) + "/indexes/products/vectors", headers=h, json={
        "embedder_name": "text", "document_id": "1", "vector": [0.1] * 32,
    }).status_code == 422


def test_ms077_composite_and_multiple_embedders_coexist_on_one_index(client):
    """Multiple and composite embedders can be configured on the same index."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    _docs(client, wid, h, "products", PRODUCTS)
    _embedder(client, wid, h, "products", "text")
    composite = client.post(_base(wid) + "/indexes/products/embedders", headers=h, json={
        "name": "blend", "kind": "composite", "dimensions": 48,
        "config": {"components": ["text", "local_image"], "source": "document"},
    })
    assert composite.status_code == 201, composite.text
    rows = client.get(_base(wid) + "/indexes/products/embedders", headers=h).json()
    assert {r["name"] for r in rows} == {"text", "blend"}
    result = client.post(_base(wid) + "/indexes/products/search/hybrid", headers=h,
                         json={"q": "shoes", "embedder_name": "blend"})
    assert result.status_code == 200 and result.json()["embedder"] == "blend"


def test_ms078_binary_quantization_uses_one_bit_per_dimension(client):
    """Binary quantization stores one bit per dimension and changes ranking."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    _docs(client, wid, h, "products", PRODUCTS)
    embedder = _embedder(client, wid, h, "products", "binary", dimensions=16,
                         binary_quantized=True)
    assert embedder["binary_quantized"] is True
    result = client.post(_base(wid) + "/indexes/products/search/hybrid", headers=h,
                         json={"q": "shoes", "embedder_name": "binary"})
    assert result.json()["binary_quantized"] is True
    assert result.json()["results"]


def test_ms095_local_search_preview_runs_without_a_hosted_demo(client):
    """A local search preview reruns a saved query against an index."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    _docs(client, wid, h, "products", PRODUCTS)
    preview = client.post(_base(wid) + "/indexes/products/previews", headers=h,
                          json={"key": "demo", "query": "shoes", "config": {"limit": 5}})
    assert preview.status_code == 201, preview.text
    result = client.post(_base(wid) + f"/previews/{preview.json()['id']}/run", headers=h)
    assert result.status_code == 200 and result.json()["local_only"] is True
    assert len(result.json()["results"]) == 2


def test_ms103_render_templates_substitute_document_and_query_values(client):
    """Embedder/chat/fragment templates render locally with supplied values."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    template = client.post(_base(wid) + "/indexes/products/templates", headers=h, json={
        "key": "chat", "kind": "chat",
        "body": "Searching {{query}} at {{brand}} gives {{missing}}",
    })
    assert template.status_code == 201, template.text
    assert client.post(_base(wid) + "/indexes/products/templates", headers=h, json={
        "key": "bad", "kind": "external", "body": "x",
    }).status_code == 422
    rendered = client.post(_base(wid) + f"/indexes/products/templates/{template.json()['id']}/render",
                           headers=h, json={"document": {"brand": "Acme"}, "query": "shoes"})
    body = rendered.json()
    assert body["rendered"] == "Searching shoes at Acme gives "
    assert body["external_service"] is False


def test_search_advanced_workspace_isolation(client):
    """A second workspace cannot address this workspace's advanced search rows."""
    wid, h = _ctx(client)
    _index(client, wid, h)
    embedder = _embedder(client, wid, h, "products")
    federation = client.post(_base(wid) + "/federations", headers=h, json={
        "key": "only-here", "members": [{"index": "products", "weight": 1}],
    }).json()
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other search"})
    assert other.status_code == 200
    other_wid, other_h = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(other_wid) + "/indexes/products/embedders", headers=h).status_code == 403
    assert client.get(_base(other_wid) + "/federations", headers=other_h).json() == []
    assert client.post(_base(other_wid) + "/federations/" + federation["id"] + "/search",
                       headers=other_h, json={"q": "x"}).status_code == 404
    assert client.post(_base(other_wid) + "/indexes/products/search/hybrid", headers=other_h,
                       json={"q": "x", "embedder_name": embedder["name"]}).status_code == 404
