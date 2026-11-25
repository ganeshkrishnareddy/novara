# P0 notification centre — implementation evidence (2026-11-22)

Feature IDs: **NV-023, NV-030, NV-035, NV-068** (all P0, Novu source family).
Status: **VERIFIED_COMPLETE against each row's documented final acceptance criteria.**
All work is local and uncommitted. No external message was sent.

## What changed

| Area | File | Change |
| --- | --- | --- |
| Data | `apps/api/novara_core/models.py` | `Notification` gains `title`, `category`, `link`, `read_at`, `seen`, `seen_at` plus scoped indexes. New `WorkspaceNotificationSettings` table (one row per workspace). |
| Events | `apps/api/novara_core/events.py` | Registered `notification.seen`, `notification.read`, `notification.read_all`, `notification.settings_updated`. |
| Contracts | `apps/api/novara_core/schemas.py` | `NotificationOut` extended and made ORM-aware; added counts and validated workspace-settings schemas. |
| API | `apps/api/novara_core/main.py` | Scoped feed with category/unread/unseen/since/paging filters; counts; SSE stream; single + bulk seen/read; workspace settings GET/PUT. All workspace- and user-scoped. |
| Migration | `apps/api/migrations/versions/b4d8c2f1a730_notification_rich_state.py` | Idempotent upgrade/downgrade; safe for local installs where `init_db()` already created the table. |
| UI | `apps/web/app.js` | Feed shows title, category badge, deep link and read/seen state; opening the feed marks seen; bulk read is one request; real-time count updates via streaming fetch. |

## Evidence

### Named tests

`apps/api/tests/test_notifications_advanced.py` — 9 named tests, all passing:

1. `test_notification_persists_rich_content_per_workspace_and_user` — NV-023 rich content round trip.
2. `test_seen_and_read_are_independent_states` — NV-035 seen/read separation and idempotent event write.
3. `test_single_mark_read_is_user_and_workspace_scoped` — NV-030/035 cross-user and cross-workspace denial.
4. `test_bulk_read_all_only_touches_callers_rows` — NV-035 bulk isolation and aggregate audit event.
5. `test_bulk_seen_all_and_counts_by_category` — NV-023/035 real category aggregates; seeing ≠ reading.
6. `test_feed_filters_and_pagination` — NV-023 filters and bounded paging.
7. `test_one_identity_is_one_recipient_with_no_second_login` — NV-030 recipient mapping and no subscriber table.
8. `test_notification_settings_persist_and_deny_cross_workspace_access` — NV-068 persistence, null clearing, 403 isolation.
9. `test_notification_settings_reject_invalid_windows` — NV-068 input validation.

Command and result:

```
cd D:\NOVARA\apps\api
& ..\..\.venv\Scripts\python.exe -m pytest tests/test_notifications_advanced.py -q
9 passed, 1 warning in 3.39s
```

Warning is Starlette's `httpx` TestClient deprecation notice, not a product failure.

### Full regression

```
& ..\..\.venv\Scripts\python.exe -m pytest -q -rs
184 passed, 1 warning in 64.00s
```

Baseline before this cycle was 175 tests (174 passed + 1 skipped before pypdf). The nine
additional tests are the new named tests above; no assertion was weakened.

### Migration safety

Validated on a disposable database (`NOVARA_DATABASE_PATH` pointed at a temp file):

```
alembic upgrade head                 -> 6d610706f4ff -> 9951aadc14c8 -> b4d8c2f1a730
alembic downgrade -1                 -> b4d8c2f1a730 -> 9951aadc14c8
alembic upgrade head                 -> 9951aadc14c8 -> b4d8c2f1a730
```

Fresh schema after re-upgrade contains all six new notification columns and
`workspace_notification_settings`. The development database was also upgraded in place
to revision `b4d8c2f1a730`; its existing data was preserved.

The first run exposed a real conflict: local startup (`init_db()` / `create_all`) had
already created the settings table, so a plain Alembic `create_table` failed. The
revision was rewritten to create each index, column and table only when missing and the
upgrade/downgrade round trip was re-run successfully.

### Real server

`docs/evidence/runtime-smoke-20261122.txt` was extended with a notification section and
re-run against a real uvicorn process on a throwaway database:

```
[5] Notification center (P0)
  PASS website intake creates a real notification (HTTP 201)
  PASS notification counts (HTTP 200)
  PASS workspace notification settings (HTTP 200)
  PASS settings persist (HTTP 200)
  PASS bulk mark read (HTTP 200)
  PASS real-time stream route registered
RUNTIME SMOKE: PASS
```

OpenAPI path count rose from 160 to 166. Response bodies containing tokens are never
logged by the smoke script.

## Defect found and fixed

`NOTIFICATION_READ` exists both as a permission string (`notification:read`) and as a
new event constant (`notification.read`). In `main.py` the permission import came after
the event import, so mark-read was publishing the permission string as an event type.
The event imports are now aliased (`NOTIF_READ_EVENT`, `NOTIF_SEEN_EVENT`,
`NOTIF_READ_ALL_EVENT`, `NOTIF_SETTINGS_EVENT`), and a named test asserts the audit
events are recorded with the correct types and are not duplicated by retries.

## Scope note

NV-068 is verified against its recorded acceptance criterion — workspace-scoped
notification settings that persist and deny cross-workspace access. General organisation
metadata such as verified domains is outside that row's stated criterion; billing is
tracked separately under NV-077 and NV-084. No broader organisation claim is made here.
