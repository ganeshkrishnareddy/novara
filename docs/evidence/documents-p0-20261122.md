# T-054 evidence — P0 Documents cluster (2026-11-22)

## Scope

Closed four P0 partial rows in the authoritative matrix:

| ID | Source feature | Acceptance evidence |
| --- | --- | --- |
| PM-001 | Open-source DocSend alternative (clean-room document sharing) | `test_documents_p0.py::test_document_journey_has_enforced_sharing_controls_and_isolation` |
| PM-073 | View/download events on the shared event spine | `::test_document_view_notifies_salesperson_and_reaches_customer_timeline`, `::test_download_is_policy_controlled_and_publishes_a_shared_event` |
| PM-095 | Fine-grained permission verbs | `::test_document_verbs_are_precise_and_role_scoped`, `::test_document_endpoints_enforce_read_write_and_admin_verbs` |
| PM-137 | Self-hosting / open-source deployment flow | `::test_install_guide_document_walkthrough_runs_end_to_end` plus the real uvicorn smoke |

No source code was copied from AGPL projects. The implementation is a clean-room
metadata boundary: NOVARA stores titles, types, opaque storage references, share
policy and engagement events. It never uploads, stores, opens or serves file
bytes, and sends no email, SMS or other external message.

## What was built

- `novara_core/permissions.py`: `document:read`, `document:write`,
  `document:admin` verbs with explicit role grants. Reps may read and write but
  not revoke/delete; support and read-only may read only.
- `modules/documents.py`: rooms and document metadata CRUD now use document
  verbs; registers and emits `document.viewed` and `document.downloaded`.
- `modules/document_links.py`: link creation with password, expiry, max views,
  view-only and download policy; visits, page views, analytics, revocation;
  visitors reuse one CRM `Contact` by email; views/downloads publish shared
  events with a correlation id, an in-app notification for the sharer and a
  projection on the customer timeline. Download is rejected with 403 when the
  link policy disallows it.
- `migrations/versions/f2b7c1a9d403_document_view_contact.py`: adds nullable
  `document_link_visits.contact_id` and its index; idempotent for local-first
  startup.
- `apps/web/app.js`: a real Documents list and detail view with data rooms,
  document records, share-link creation/token reveal, revocation, policy
  display and page engagement. All controls are permission-gated and wired.
- `docs/INSTALL.md`: a beginner "Document metadata quickstart" whose steps are
  mirrored by the named PM-137 test.
- `scripts/runtime_smoke.py`: section [8] drives the documented journey over
  HTTP against a real uvicorn process and a throwaway SQLite database.

## Commands and results

From `D:\NOVARA\apps\api` (Python at `D:\NOVARA\.venv\Scripts\python.exe`):

```
python -m pytest tests/test_documents_p0.py -q -rs
  6 passed, 1 warning in 2.95s

python -m pytest tests/test_ui_wiring.py tests/test_documents_p0.py tests/test_documents.py -q -rs
  17 passed, 1 warning in 4.60s

python -m pytest -q -rs
  211 passed, 1 warning in 70.10s
```

From `D:\NOVARA`:

```
node --check apps\web\app.js    -> syntax-ok
python -m compileall -q apps\api\novara_core apps\api\migrations apps\api\tests
python scripts\runtime_smoke.py -> RUNTIME SMOKE: PASS (174 OpenAPI paths)
```

The only warning is the known Starlette/httpx TestClient deprecation notice.
No response bodies, tokens or credentials were printed at any point.

## Migration verification

- Dev database `D:\NOVARA\novara_dev.sqlite3` upgraded in place from
  `e7a4c9d21b60` to `f2b7c1a9d403`; pre-existing rows retained.
- Disposable SQLite fixture seeded with the pre-T-054 `document_link_visits`
  shape and one legacy row:
  - upgrade head → version `f2b7c1a9d403`, `contact_id` column and
    `ix_document_link_visits_contact_id` present, legacy row preserved with a
    null contact;
  - downgrade -1 → version `e7a4c9d21b60`, column and index removed, row
    preserved;
  - upgrade head → column and index restored, row preserved.
- An earlier disposable check that appeared to show a missing column was an
  invalid fixture: module tables are created by `Base.metadata.create_all` at
  app startup, not by Alembic, so an Alembic-only database has no
  `document_link_visits` table. The corrected fixture above exercises the real
  upgrade path.

## Matrix accounting

`MASTER_FEATURE_MATRIX.csv` was changed only for PM-001, PM-073, PM-095 and
PM-137. All seven FEATURE_PARITY narrative deliverables were regenerated from
the CSV:

- 1,488 permanent IDs, zero omissions
- VERIFIED_COMPLETE 63 (was 59)
- complete-like 148 / 1,488 = 9.95% (was 144 / 9.68%)
- PARTIALLY_IMPLEMENTED 149 (was 153)
- P0: 111 rows — 56 verified, 14 partial, 32 replacement, 9 restricted

## Not claimed

- No file storage, signed URLs or document rendering: the acceptance boundary
  is metadata, policy and engagement only.
- No Docker image, signed desktop/mobile installer or physical-device build.
- No real campaign, cold email or WhatsApp send; notifications are local only.
- No commit, push, tag, deployment or public publishing. Git HEAD is unchanged
  at `73e9f76`.

## Next

T-055: select the next grouped cluster from the 14 remaining P0 partial rows
(Formbricks 1, Plane 4, Mautic 6, Chatwoot 2, Novu 1).
