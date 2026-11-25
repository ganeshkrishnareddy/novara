# GrowthBook clean-room REST v2 / document store P1 evidence (2026-11-23)

This closes the last two unimplemented GrowthBook P1 rows without vendoring
GrowthBook source, installing MongoDB or exposing a second API host.

```
D:\NOVARA\.venv\Scripts\python.exe -m pytest apps/api/tests/test_growthbook_cleanroom_p1.py -q --disable-warnings
# 2 passed, 1 warning in 4.01s
```

| Master ID | Row disposition | Named test | Proved locally |
|---|---|---|---|
| GB-060 | `VERIFIED_COMPLETE` | `test_gb060_rest_v2_validation_permissions_and_workspace_isolation` | A genuinely versioned `/api/v2/workspaces/{workspace_id}` surface is advertised in the OpenAPI schema; it returns a stable `data` + `meta` envelope with real totals and page links; strict schemas reject unknown fields and invalid resource types; duplicate keys return 409; `If-Match` optimistic concurrency returns 428 when missing and 409 when stale, and a valid version increments the persisted row; every write emits a named event; unauthenticated calls return 401; a foreign workspace is denied 403 on the first workspace's route and 404 on its own route addressing the other workspace's record. |
| GB-087 | `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION` | `test_gb087_document_store_validation_permissions_and_workspace_isolation` | A clean-room document store supplies named workspace collections, declarative indexes (including *enforced* unique indexes), schema-free JSON documents with a stable `_id`, MongoDB-style operator queries (`$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$exists`), `$set`/`$unset` updates with version checks and named events. Real rows persist and a second workspace sees none of them. No MongoDB server, driver, licence or network call is used, so this row is deliberately *not* claimed as literal MongoDB. |

## Implementation

- `apps/api/novara_core/modules/api_v2.py` — REST v2 surface: `V2Record`
  table, strict Pydantic schemas, envelope pagination, `If-Match` concurrency,
  `CONTACT_READ`/`CONTACT_WRITE` checks, `verify_workspace` on every route and
  `api_v2.record.*` audit events.
- `apps/api/novara_core/modules/document_store.py` — document-store slice:
  `DocumentStore` service, `DocCollection`/`DocIndex`/`DocDocument` tables,
  operator query engine, optimistic updates and `docstore.*` audit events.
- Both routers are wired through `apps/api/novara_core/modules/__init__.py`,
  the same registration path every other capability uses. Tests use the real
  FastAPI app through the `client` fixture and assert persisted rows/events.

## Boundaries (not claimed)

- No MongoDB server, replica set, driver package or hosted database is present.
- No GrowthBook code, plugin, CDN or enterprise feature was copied.
- The v2 surface is additive on NOVARA's single application and database; it is
  not a second host or a separate deployment target.
