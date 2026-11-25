# NOVARA — Cycle 1, Batch 2 checkpoint

Date: 2026-11-22

## Implemented

1. **Storage & file infrastructure** (`modules/storage.py`) — local filesystem backend, upload validation (size/MIME), checksum integrity, secure filenames, soft delete + cleanup, download, presigned upload/download URLs (genuine HMAC tokens resolving to real endpoints), PDF metadata/page-count extraction (pypdf). Events: uploaded/deleted/accessed. Covers PM-002, PM-015, PM-016, PM-012.

2. **Email broadcast & unsubscribe** (`modules/email_campaigns.py`) — broadcast campaigns, recipient selection with suppression + consent enforcement, queue, local delivery adapter (no real sends), cancel, recipient status, unsubscribe tokens (HMAC), suppression list, consent records. Events registered. Covers MT-013, MT-019.

3. **Workflow builder extensions** (`modules/automation.py`) — conditional branches, delays, human-approval gates, notification-intent steps, scheduled trigger type + schedule field, retry_policy field, approve-run endpoint. Covers NV-005/NV-007 extensions.

4. **Projects completion** (`modules/projects.py`) — item tags, project comments, milestones (create/complete). Covers PL-002..PL-017 extensions.

5. **MS-039** (`modules/search.py`) — POST search route (engine-compatible) delegating to existing scoped search.

6. **Security** — all new endpoints workspace-scoped with require() permissions; presigned tokens workspace-bound and expiry-checked; HMAC verification.

## Tests
- Baseline before: 152 passed
- Added `tests/test_batch2_smoke.py` (6 tests)
- Result: 158 passed, 2 warnings in 69.76s
- `node --check apps/web/app.js` exit 0
- All modules py_compile clean

## Constraints upheld
- No commits/pushes/deployments
- No real external sends; local adapter only
- No dark theme, no fake data
- Workspace isolation on every endpoint