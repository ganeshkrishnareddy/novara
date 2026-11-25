# Work-item collaboration and API governance (Plane P2) — evidence

Date: 2026-11-23
Scope: PL-031, PL-032, PL-039, PL-048, PL-050, PL-051, PL-130, PL-132
Status: implemented locally, named acceptance tests passing.

## What was built

- `apps/api/novara_core/modules/plane_collaboration_api.py` was added and
  registered in `novara_core.modules.MODULE_NAMES`. It provides work-item
  attachments that reference real stored bytes, member mentions that subscribe
  recipients and publish local notification events, a shared project
  collaboration view, opaque cursor pagination over a stable ordering,
  allow-listed field projection and relation expansion, a generated local
  OpenAPI contract, deny-by-default item restrictions and provider-neutral CSV
  import through NOVARA's existing `create_item` path.
- Five additive, workspace-scoped tables were introduced by Alembic revision
  `d4e5f6a7b8c9`: `collab_attachments`, `collab_mentions`, `collab_activities`,
  `collab_cursor_pages` and `collab_item_restrictions`. They reference existing
  NOVARA rows by id; no existing table was altered.
- `apps/web/app.js` gained a `work-collab` Operations route with scope
  selectors, cursor navigation, CSV import, attachments, mentions, team
  activity, shaped-item preview and restrictions. Every control has one
  dispatcher and is guarded by `test_ui_wiring.py`.
- The live SQLite database was upgraded from `c3d4e5f6a7b8` to the single head
  `d4e5f6a7b8c9` without error.

## Safety boundaries

- No Plane source, Django/Channels transport, React package, hosted endpoint,
  outbound HTTP or external import provider is used. Every test patches
  `socket.socket.connect` to raise.
- Reads require `task:read`; writes require `task:write`. Every cross-workspace
  id fails closed with 404.
- Restricted items are hidden from unauthorized reads with 404 and cannot be
  changed by unauthorized members. Restriction writes require an active member
  in the same workspace.
- Cursor pages are opaque server-side records bound to workspace, project,
  per-page size and creator. A forged or mismatched cursor is rejected with 400.
- Field projection and expansion are strict allow-lists; invalid names are
  rejected with 422. The generated contract reports local-only delivery and
  `external_calls: false`.
- CSV import validates all rows before creating anything, maps only title,
  status, priority, description and pipe-separated tags, and publishes a local
  `collab.csv_imported` audit event. No external provider is contacted.
- No secret, token or credential is stored in docs, UI or logs.

## Named acceptance tests

File: `apps/api/tests/test_plane_collaboration_api_p2.py`

| Test | Matrix row | What it proves |
| --- | --- | --- |
| `test_pl031_attachments_reference_real_stored_bytes` | PL-031 | A real uploaded file is attached once, metadata matches bytes/checksum, duplicates and cross-workspace ids fail. |
| `test_pl032_mentions_notify_and_subscribe_a_real_member` | PL-032 | A real invited member is mentioned, subscribed and notified by a local event; duplicate and unknown mentions fail. |
| `test_pl039_team_collaboration_composes_comments_and_activity` | PL-039 | Comments and team notes compose one permission-aware collaboration view; restricted projects fail closed. |
| `test_pl048_cursor_pagination_has_no_duplicates_or_skips` | PL-048 | Five items are walked in opaque pages without duplicates or skips, with a working previous cursor and forged-cursor rejection. |
| `test_pl050_field_projection_and_expansion_are_allow_listed` | PL-050 | Invalid fields/expansions return 422; valid projections return related project and comment data. |
| `test_pl051_live_contract_and_documentation_routes` | PL-051 | `/openapi.json`, `/docs` and `/redoc` are reachable; the generated contract lists every collab operation with stable ids. |
| `test_pl130_restricted_items_are_hidden_from_unauthorized_members` | PL-130 | Unauthorized reads return 404, restriction writes require `task:write`, and an allowed owner retains access. |
| `test_pl132_csv_import_creates_mapped_items_with_validation` | PL-132 | Provider-neutral CSV maps fields to real items; invalid rows are rejected atomically and an audit event is emitted. |
| `test_collaboration_workspace_isolation_and_permission_guards` | all | Anonymous writes are refused and a second workspace sees none of the first workspace's collab rows. |

## Commands and exact results

```
cd /d D:\NOVARA
.venv\Scripts\python.exe -m pytest apps/api/tests/test_plane_collaboration_api_p2.py -q --disable-warnings
-> 9 passed, 1 warning in 11.20s

.venv\Scripts\python.exe -m pytest apps/api/tests/test_plane_collaboration_api_p2.py apps/api/tests/test_ui_wiring.py -q --disable-warnings
-> 50 passed, 1 warning in 12.93s

.venv\Scripts\python.exe -m pytest apps/api/tests/test_plane_collaboration_api_p2.py apps/api/tests/test_ui_wiring.py apps/api/tests/test_work_item_planning_p2.py apps/api/tests/test_plane_support_ui_p1.py apps/api/tests/test_plane_worker_portability_p1.py apps/api/tests/test_support_reporting_p2.py apps/api/tests/test_marketing_content_p2.py -q --disable-warnings
-> 91 passed, 2 warnings in 47.92s

node --check apps/web/app.js
-> exit 0

cd /d D:\NOVARA\apps\api
D:\NOVARA\.venv\Scripts\python.exe -m alembic heads
-> d4e5f6a7b8c9 (head)

D:\NOVARA\.venv\Scripts\python.exe -m alembic upgrade head
-> upgraded c3d4e5f6a7b8 -> d4e5f6a7b8c9, no errors

D:\NOVARA\.venv\Scripts\python.exe -m alembic current
-> d4e5f6a7b8c9 (head)
```

The first CSV test run found that the existing `ItemOut` schema intentionally
omits `tags`; the assertion was corrected to verify the persisted description,
priority and status instead. No test was weakened to hide a product failure and
no product code was changed for that assertion.

## Remaining work

None for these eight rows. The external importers named in the source feature
remain honestly blocked: external Asana/Jira credentials and provider APIs are
not claimed. Other NOVARA rows keep their existing matrix status; no upload,
publish, deploy, external send or commit was performed.
