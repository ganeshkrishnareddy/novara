"""Named acceptance tests for the two remaining GrowthBook clean-room P1 rows.

GB-060: a genuinely versioned REST v2 surface with a stable envelope,
        pagination, strict validation, optimistic concurrency, permission
        checks and workspace isolation.
GB-087: a clean-room document-store slice with collections, JSON documents,
        declarative indexes, operator queries, optimistic concurrency,
        permission checks and workspace isolation.

No GrowthBook source, MongoDB server, external call or second host is used.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from novara_core import main  # noqa: F401 - imports every module and table
from novara_core.models import Event
from novara_core.modules.api_v2 import (
    API_VERSION,
    V2_RECORD_CREATED,
    V2_RECORD_DELETED,
    V2_RECORD_UPDATED,
    V2Record,
)
from novara_core.modules.document_store import (
    COLLECTION_CREATED,
    DOC_DELETED,
    DOC_INSERTED,
    DOC_UPDATED,
    INDEX_CREATED,
    DocCollection,
    DocDocument,
    DocIndex,
)

from .conftest import auth, bootstrap

ROOT = Path(__file__).resolve().parents[3]


def _second_workspace(client, headers, email):
    """Create and switch to a second workspace; return (id, headers)."""
    response = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Foreign"}
    )
    assert response.status_code == 200, response.text
    wid = response.json()["workspace_id"]
    switched = client.post("/api/v1/auth/login", json={
        "email": email, "password": "Password123!", "workspace_id": wid,
    })
    assert switched.status_code == 200, switched.text
    return wid, auth(switched.json()["access_token"])


# ---------------------------------------------------------------------------
# GB-060
# ---------------------------------------------------------------------------


def test_gb060_rest_v2_validation_permissions_and_workspace_isolation(client, db_session):
    """A real v2 surface validates, checks permissions and isolates workspaces."""
    tokens = bootstrap(client, "V2Api", "v2-owner@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v2/workspaces/{wid}"

    # The surface is genuinely versioned and advertised in the OpenAPI schema.
    meta = client.get(f"{base}/meta", headers=headers)
    assert meta.status_code == 200, meta.text
    assert meta.json()["api_version"] == API_VERSION
    assert "feature" in meta.json()["supported_resource_types"]
    schema = client.get("/openapi.json").json()
    assert f"/api/v2/workspaces/{{workspace_id}}/records" in schema["paths"]

    # Authentication and permissions are enforced, not assumed.
    assert client.get(f"{base}/records").status_code == 401
    assert client.post(f"{base}/records", json={"resource_type": "feature", "key": "x"}).status_code == 401

    # Strict validation: unknown fields and invalid types are refused.
    bad = client.post(base + "/records", headers=headers, json={
        "resource_type": "feature", "key": "flag.one", "unexpected": True,
    })
    assert bad.status_code == 422, bad.text
    bad_type = client.post(base + "/records", headers=headers, json={
        "resource_type": "not-a-type", "key": "flag.one",
    })
    assert bad_type.status_code == 422, bad_type.text

    created = client.post(base + "/records", headers=headers, json={
        "resource_type": "feature", "key": "flag.one",
        "label": "Flag one", "body": {"enabled": False},
    })
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["version"] == 1
    assert record["workspace_id"] == wid
    rid = record["id"]

    # Duplicate keys are refused inside the same workspace.
    dupe = client.post(base + "/records", headers=headers, json={
        "resource_type": "feature", "key": "flag.one",
    })
    assert dupe.status_code == 409, dupe.text

    # The collection response has a stable v2 envelope with real pagination.
    listing = client.get(f"{base}/records?limit=1&offset=0", headers=headers)
    assert listing.status_code == 200, listing.text
    payload = listing.json()
    assert set(payload) == {"data", "meta"}
    assert payload["meta"]["api_version"] == API_VERSION
    assert payload["meta"]["total"] == 1
    assert payload["meta"]["links"]["next"] is None

    # Optimistic concurrency: missing/stale If-Match never writes.
    no_match = client.patch(f"{base}/records/{rid}", headers=headers,
                            json={"body": {"enabled": True}})
    assert no_match.status_code == 428, no_match.text
    stale = client.patch(f"{base}/records/{rid}", headers={**headers, "If-Match": "99"},
                         json={"body": {"enabled": True}})
    assert stale.status_code == 409, stale.text
    updated = client.patch(f"{base}/records/{rid}", headers={**headers, "If-Match": "1"},
                           json={"body": {"enabled": True}})
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["body"]["enabled"] is True

    # All writes are named events on the shared spine, readable from a new session.
    types = set(db_session.execute(
        select(Event.event_type).where(Event.workspace_id == wid, Event.entity_id == rid)
    ).scalars().all())
    assert types == {V2_RECORD_CREATED, V2_RECORD_UPDATED}

    # Real persistence: a fresh session sees the versioned row.
    row = db_session.execute(select(V2Record).where(V2Record.id == rid)).scalar_one()
    assert row.version == 2 and row.body["enabled"] is True

    # Hard cross-workspace isolation for both reads and writes.
    other_wid, other_headers = _second_workspace(client, headers, "v2-owner@example.com")
    assert client.get(f"{base}/records/{rid}", headers=other_headers).status_code == 403
    assert client.patch(f"/api/v2/workspaces/{other_wid}/records/{rid}",
                        headers=other_headers, json={"label": "hijack"}).status_code == 404

    # Delete is versioned and emits its own event.
    deleted = client.delete(f"{base}/records/{rid}",
                            headers={**headers, "If-Match": "2"})
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True
    count = db_session.execute(
        select(func.count()).select_from(V2Record).where(V2Record.id == rid)
    ).scalar_one()
    assert count == 0
    assert V2_RECORD_DELETED in set(db_session.execute(
        select(Event.event_type).where(Event.workspace_id == wid, Event.entity_id == rid)
    ).scalars().all())


# ---------------------------------------------------------------------------
# GB-087
# ---------------------------------------------------------------------------


def test_gb087_document_store_validation_permissions_and_workspace_isolation(client, db_session):
    """A real document store persists, queries and isolates workspace documents."""
    tokens = bootstrap(client, "DocStore", "docstore-owner@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    base = f"/api/v1/workspaces/{wid}/docstore"

    assert client.get(f"{base}/collections").status_code == 401
    assert client.post(f"{base}/collections", json={"name": "flags"}).status_code == 401

    collection = client.post(f"{base}/collections", headers=headers, json={"name": "flags"})
    assert collection.status_code == 201, collection.text
    assert collection.json()["workspace_id"] == wid

    # Index metadata is declarative and named, with no external dependency.
    index = client.post(f"{base}/collections/flags/indexes", headers=headers,
                        json={"field": "priority", "unique": False})
    assert index.status_code == 201, index.text
    dup_index = client.post(f"{base}/collections/flags/indexes", headers=headers,
                            json={"field": "priority"})
    assert dup_index.status_code == 409
    unique_index = client.post(f"{base}/collections/flags/indexes", headers=headers,
                               json={"field": "name", "unique": True})
    assert unique_index.status_code == 201, unique_index.text

    # Insert real JSON documents with a stable _id.
    first = client.post(f"{base}/collections/flags/documents", headers=headers, json={
        "id": "f1", "body": {"name": "alpha", "priority": 5, "tags": ["a", "b"]},
    })
    assert first.status_code == 201, first.text
    second = client.post(f"{base}/collections/flags/documents", headers=headers, json={
        "id": "f2", "body": {"name": "beta", "priority": 9, "tags": ["b"]},
    })
    assert second.status_code == 201, second.text
    dupe = client.post(f"{base}/collections/flags/documents", headers=headers,
                       json={"id": "f1", "body": {}})
    assert dupe.status_code == 409
    # A declared unique index is actually enforced on insert.
    unique_dupe = client.post(f"{base}/collections/flags/documents", headers=headers,
                              json={"id": "f3", "body": {"name": "alpha"}})
    assert unique_dupe.status_code == 409, unique_dupe.text

    # Operator queries really filter the persisted documents.
    queried = client.post(f"{base}/collections/flags/query", headers=headers, json={
        "filter": {"priority": {"$gte": 7}, "tags": {"$in": ["b"]}},
    })
    assert queried.status_code == 200, queried.text
    assert [doc["doc_id"] for doc in queried.json()] == ["f2"]
    exists = client.post(f"{base}/collections/flags/query", headers=headers, json={
        "filter": {"name": {"$exists": True}},
    })
    assert exists.status_code == 200 and len(exists.json()) == 2

    bad_operator = client.post(f"{base}/collections/flags/query", headers=headers, json={
        "filter": {"priority": {"$regex": "x"}},
    })
    assert bad_operator.status_code == 422, bad_operator.text

    # Updates are validated and version-checked.
    bad_update = client.patch(
        f"{base}/collections/flags/documents/f1",
        headers={**headers, "If-Match": "1"},
        json={"updates": {"$inc": {"priority": 1}}},
    )
    assert bad_update.status_code == 422, bad_update.text
    no_match = client.patch(f"{base}/collections/flags/documents/f1", headers=headers,
                            json={"updates": {"$set": {"name": "no-match"}}})
    assert no_match.status_code == 428, no_match.text
    raw_update = client.patch(
        f"{base}/collections/flags/documents/f1",
        headers={**headers, "If-Match": "1"},
        json={"updates": {"$set": {"name": "alpha-v2"}, "$unset": {"tags": ""}}},
    )
    assert raw_update.status_code == 200, raw_update.text
    assert raw_update.json()["version"] == 2
    assert raw_update.json()["body"]["name"] == "alpha-v2"
    assert "tags" not in raw_update.json()["body"]
    stale = client.patch(f"{base}/collections/flags/documents/f1",
                         headers={**headers, "If-Match": "1"},
                         json={"updates": {"$set": {"name": "stale"}}})
    assert stale.status_code == 409, stale.text

    # Every write is a named event and every row is really persisted.
    events = set(db_session.execute(
        select(Event.event_type).where(Event.workspace_id == wid)
    ).scalars().all())
    assert {COLLECTION_CREATED, INDEX_CREATED, DOC_INSERTED, DOC_UPDATED} <= events
    assert db_session.execute(
        select(func.count()).select_from(DocDocument).where(DocDocument.workspace_id == wid)
    ).scalar_one() == 2
    assert db_session.execute(
        select(func.count()).select_from(DocIndex).where(DocIndex.workspace_id == wid)
    ).scalar_one() == 2
    assert db_session.execute(
        select(func.count()).select_from(DocCollection).where(DocCollection.workspace_id == wid)
    ).scalar_one() == 1

    # Hard cross-workspace isolation: another workspace sees no documents and
    # cannot address this workspace's collection or document.
    other_wid, other_headers = _second_workspace(client, headers, "docstore-owner@example.com")
    assert client.get(f"{base}/collections", headers=other_headers).status_code == 403
    assert client.get(f"/api/v1/workspaces/{other_wid}/docstore/collections",
                      headers=other_headers).json() == []
    assert client.get(f"/api/v1/workspaces/{other_wid}/docstore/collections/flags/documents/f1",
                      headers=other_headers).status_code == 404
    foreign_query = client.post(
        f"/api/v1/workspaces/{other_wid}/docstore/collections/flags/query",
        headers=other_headers, json={"filter": {}},
    )
    assert foreign_query.status_code == 404

    # Delete is real and emits its event.
    deleted = client.delete(f"{base}/collections/flags/documents/f2", headers=headers)
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True
    assert db_session.execute(
        select(func.count()).select_from(DocDocument)
        .where(DocDocument.workspace_id == wid, DocDocument.doc_id == "f2")
    ).scalar_one() == 0
    assert DOC_DELETED in set(db_session.execute(
        select(Event.event_type).where(Event.workspace_id == wid)
    ).scalars().all())
