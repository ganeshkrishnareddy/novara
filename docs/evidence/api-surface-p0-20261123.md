# T-060 evidence — P0 workspace admin, API contexts and OpenAPI (2026-11-23)

## Scope

| ID | Source feature | Acceptance evidence |
| --- | --- | --- |
| PL-001 | Plane workspaces | `test_api_surface_p0.py::test_workspace_can_be_created_switched_and_administered`; `test_ui_wiring.py::test_workspace_admin_surface_is_routed_and_wired` |
| PL-043 | Plane public REST API adapter | `test_api_surface_p0.py::test_plane_adapter_records_crud_calls_only_when_configured` |
| MT-072 | Mautic REST API contexts and CRUD | `test_api_surface_p0.py::test_api_contexts_expose_full_crud_with_validation_and_permissions` |
| NV-057 | Novu REST API / OpenAPI document | `test_api_surface_p0.py::test_notification_and_workflow_routes_are_documented_and_workspace_scoped` |

All four rows were `PARTIALLY_IMPLEMENTED`; all four are now `VERIFIED_COMPLETE`.
No source project was embedded and no outbound network call was made.

## What was built

- `modules/workspace_admin.py`: a persistent, workspace-unique settings row with
  a non-sensitive-only validator, `GET`/`PATCH /admin/settings`, a live
  `GET /admin/summary` (members, enabled flags, integrations, adapter calls) and
  a real `workspace.settings_updated` event.
- `modules/adapters.py` + `modules/integrations.py`: an opt-in `plane` provider
  (`project_management` kind) with the Mautic/Plane context verbs
  `get`, `getlist`, `create`, `edit`, `delete`. It is mock-only: without an
  explicit non-sensitive configuration the call is rejected; with one it is
  recorded with `delivered: false`, `external: false` and an audit event.
- `modules/api_resources.py`: native NOVARA API contexts for contacts, forms and
  pages under `/api/v1/workspaces/{id}/api`. Each has get, getList, create, edit
  and delete with validation, 409 duplicate handling, 404 cross-workspace ids,
  `CONTACT_READ`/`CONTACT_WRITE` permissions and named audit events.
- `main.py`: the generated `/openapi.json` now declares a `BearerAuth` HTTP
  scheme on every protected route, including all notification, workflow and
  jobs routes; public sign-in routes stay public.
- `apps/web/app.js`: the Workspaces page now loads and renders the admin
  summary, a settings form (name, timezone, currency) and live feature-flag
  controls (create, enable, disable). Every control has one dispatcher.
- Migration `9b7c4e2a1d63` adds `workspace_settings`, `api_forms` and `api_pages`
  idempotently and reverses cleanly.

## Commands and results

From `D:\NOVARA\apps\api` (Python at `D:\NOVARA\.venv\Scripts\python.exe`):

```
python -m pytest tests/test_api_surface_p0.py -q       -> 4 passed
python -m pytest -q                                     -> 244 passed, 1 warning in 84.34s
python -m compileall -q novara_core migrations tests    -> exit 0
python -m alembic heads                                 -> 9b7c4e2a1d63 (head)
```

From `D:\NOVARA`:

```
node --check apps\web\app.js                            -> no syntax errors
python scripts\runtime_smoke.py                         -> RUNTIME SMOKE: PASS (sections 1-14)
python C:\...\novara_t060_migrate_check.py
  upgrade -> downgrade -> upgrade                        -> ROUND TRIP PASS, existing data preserved
python docs\FEATURE_PARITY\validate_inventories.py      -> ALL VALID: True, 1,488 rows
python docs\FEATURE_PARITY\generate_deliverables.py     -> ALL DELIVERABLES GENERATED
```

The only warning is the known Starlette/httpx TestClient deprecation notice.
No bearer tokens, response bodies or credentials were printed.

## Behavior proved

- One identity creates a second workspace, switches to it by signing in with its
  id, and both memberships persist. Settings survive a reload; secret-looking
  keys are rejected with 422; every cross-workspace admin read returns 403.
- The Plane adapter is useless until the workspace explicitly configures it,
  then records each of the five context verbs as a local mock with no delivery.
  The source has no HTTP client and no Plane code or URL.
- All three API contexts survive a real create → getList → get → edit → delete
  cycle; invalid email/status/slug values are 422, duplicates 409, and a foreign
  workspace's id is 404. Auth is 401 without a token.
- `/openapi.json` declares bearer auth on every live notification/workflow/jobs
  route, and runtime checks confirm 401 without a token and 403 across workspaces.
- Runtime smoke section [14] repeats the same journeys over real HTTP.

## Matrix accounting

Only PL-001, PL-043, MT-072 and NV-057 were changed in `MASTER_FEATURE_MATRIX.csv`;
all seven FEATURE_PARITY deliverables were regenerated:

- 1,488 permanent IDs, zero omissions
- VERIFIED_COMPLETE 77 (was 73)
- complete-like 162 / 1,488 = 10.89% (was 158 / 10.42%)
- PARTIALLY_IMPLEMENTED 135 (was 139)
- P0: 111 rows — 70 verified, 0 partial, 32 compatible replacements,
  9 licensing-restricted

## Not claimed

- No live Plane, Mautic or Novu instance, credential, source code or outbound
  call; all adapters are local mocks.
- No generated SDK or second API host; there is one native NOVARA API surface.
- No commit, push, tag, deployment or public publishing. Git HEAD remains
  `73e9f76`.
