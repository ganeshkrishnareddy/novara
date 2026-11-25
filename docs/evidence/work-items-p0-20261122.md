# Work Items P0 — implementation evidence (2026-11-22)

Feature IDs: **PL-004, PL-006, PL-008, PL-017, PL-038** (all P0, Plane source
family). Status: **VERIFIED_COMPLETE against each row's recorded acceptance
criteria.** All work is local and uncommitted.

## What changed

| Area | File | Change |
| --- | --- | --- |
| Data | `apps/api/novara_core/modules/projects.py` | New workspace-scoped `project_states` table (`name`, `group`, `position`, `is_active`) with a unique `(workspace_id, name)` constraint. |
| API | same file | `GET/POST /projects/states`, `PATCH /projects/states/{id}`, `GET /projects/assignees`. Item create/patch validates against the workspace's state set, rejects inactive states, and returns a derived `state_group`. Completion and progress summaries roll up by configured group instead of hard-coded names. `GET /projects/{id}/items?overdue=true` filters open overdue work. |
| Search | `apps/api/novara_core/modules/search.py` | Added typed `project` and `project_item` results, facets counts, and item/state titles in suggestions. Every query remains workspace-scoped and joins the parent project with the same workspace filter. |
| Migration | `apps/api/migrations/versions/e7a4c9d21b60_project_work_item_states.py` | Idempotent creation of `project_states`; upgrade/downgrade/upgrade verified. |
| UI | `apps/web/app.js` | Real project detail route (`#/projects/{id}`), working New project / View / New work item / state activation controls, state set table, per-item state and assignee selectors, due dates with overdue badges, progress bar, and project/work-item search types. |
| Tests | `apps/api/tests/test_work_items.py`, `apps/api/tests/test_ui_wiring.py` | 6 named acceptance tests and 4 named static wiring tests. |

## Named tests

`apps/api/tests/test_work_items.py`:

1. `test_work_item_lifecycle_is_user_facing_and_workspace_isolated` — PL-004:
   create/read/update/complete, event trail, second workspace cannot read or
   patch the first workspace's items.
2. `test_assignee_set_changed_and_invalid_values_rejected` — PL-006: active
   member list, set/clear/change assignee, unknown member rejected with 422.
3. `test_configurable_states_are_validated_grouped_and_drive_progress` — PL-008:
   invalid group 422, duplicate name 409, ordering, rename, item validation,
   `state_group` in list responses, group-based progress, inactive states
   rejected for new items while existing items keep their group.
4. `test_due_dates_are_stored_validated_and_visible` — PL-017: project and item
   due dates persist, malformed dates 422, overdue filter returns only open
   overdue items.
5. `test_search_returns_typed_project_results_without_cross_workspace_leak` —
   PL-038: typed `project` and `project_item` results, correct `url_hint`,
   foreign workspace rows absent, facets counts, cross-workspace access 403.
6. `test_static_project_routes_resolve_before_dynamic_project_id` — regression:
   `/projects/states` and `/projects/assignees` resolve to their own handlers.

`apps/api/tests/test_ui_wiring.py` reads the real SPA source and asserts that
the detail view is routed and that every new action, change and form has a
dispatcher declared exactly once. This catches dead buttons without needing a
browser session.

Commands and results:

```
cd D:\NOVARA\apps\api
& ..\..\.venv\Scripts\python.exe -m pytest tests/test_work_items.py -q
6 passed, 1 warning in 2.12s

& ..\..\.venv\Scripts\python.exe -m pytest tests/test_ui_wiring.py -q
4 passed, 1 warning in 0.04s

& ..\..\.venv\Scripts\python.exe -m pytest -q -rs
203 passed, 1 warning in 67.35s
```

Baseline before this cycle was 193 passed. The ten new tests are additive and
no existing assertion was weakened. The warning is Starlette's `httpx`
TestClient deprecation notice.

## Real server

`docs/evidence/runtime-smoke-20261122.txt` gained a Work items section and was
re-run against a real uvicorn process on a throwaway database:

```
[7] Work items and delivery states (P0)
  PASS configurable state created (HTTP 201)
  PASS configurable done state created (HTTP 201)
  PASS project created with due date (HTTP 201)
  PASS work item uses configured state (HTTP 201)
  PASS work item completion tracks state group (HTTP 200)
  PASS progress reflects the completed item (HTTP 200)
  PASS search returns typed work item (HTTP 200)
```

The first smoke run failed with HTTP 422 when it tried to patch an item to the
literal `done` after defining custom states. That is correct behaviour — a
workspace-defined state set replaces the built-ins — so the smoke now creates
an explicit done state. No product code was loosened to make it pass.

## Migration safety

Development database moved `d5e9b3c2f841` -> `e7a4c9d21b60` in place with data
preserved. A disposable database completed upgrade -> downgrade -> upgrade and
ended with `project_states` present at revision `e7a4c9d21b60`.

## Honest scope notes

- `ProjectItem` and the separate `Task` entity are **not** unified. PL-004's
  recorded criterion asks for a work item that can be created, read, updated,
  completed and found in a dedicated user-facing view with workspace
  isolation; all of that now exists. Cross-linking the two entities is not
  claimed.
- Multi-assignee support is not implemented; PL-006's criterion requires one
  validated active member, which is implemented and tested.
- State transition guards (which state may follow which) are not implemented;
  PL-008's criterion requires configurable, validated, grouped states reflected
  in list and progress views, which is implemented.
- Search matches literal substrings. Ranking, fuzzy matching and external
  indexes are not claimed.
