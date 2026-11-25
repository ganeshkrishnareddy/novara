# Papermark documents — P1 evidence (2026-11-23)

## Status
11 named acceptance tests back 22 Master IDs. Clean-room implementation; no
Papermark source was used and no external service was contacted.

## Command
```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_papermark_documents_p1.py -q
```
Result: **11 passed** (Starlette/httpx deprecation warning only).

## IDs closed
PM-009, PM-011, PM-019, PM-022, PM-026, PM-031, PM-034, PM-041, PM-047,
PM-055, PM-063, PM-075, PM-078, PM-079, PM-081, PM-082, PM-087, PM-089,
PM-090, PM-121, PM-142, PM-150.

## What is proven
- Version creation atomically demotes the previous primary; links serve the
  primary version. Pages carry immutable ids and per-page view records.
- Folder CRUD/placement with collision handling; one-workspace collections.
- Agreements are immutable after acceptance and gate content bytes.
- Email verification and domain allowlisting (including subdomains) gate view.
- Rooms attach/detach documents without losing the library record; ACL rows
  are workspace-scoped.
- Analytics (time per page, counts, duration, room rollups, aggregates) come
  from real view events; visits stamp real timestamps and downloads.
- A real view notifies the assigned owner in-app.
- Document preferences/member settings persist per workspace.
- A documented API creates, shares and reads views for a real document.
- Conversion output is produced locally without AGPL source in the repository.

## Fixes made during the cycle
- Explicit FastAPI response models removed an import-time crash.
- Link defaults are present in create responses; the timed-page event carries
  a scoped `document_id`.
- Visit duration uses the shared tz-normalising helper (SQLite drops tzinfo).

## Deliberate non-claims
PM-040 (encryption/.env deployment), PM-045 (browser watermark evidence),
PM-117 (external HTTP webhooks), PM-123 (jobs runner), PM-141 (main.py API
stability), PM-146 (middleware rate limiting) and PM-156 (TLS/legal review)
remain outside these named tests and are not claimed here.
