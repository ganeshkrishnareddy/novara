# T-058 evidence — P0 Plane project membership and roles (2026-11-22)

## Scope

| ID | Source feature | Acceptance evidence |
| --- | --- | --- |
| PL-003 | Project members | `test_project_membership_p0.py::test_project_membership_registry_and_roles`, `::test_member_management_requires_project_admin_and_valid_identity` |
| PL-040 | Permissions / RBAC | `::test_project_roles_enforce_read_write_on_every_route`, `::test_public_projects_keep_workspace_role_fallback`, `tests/test_ui_wiring.py::test_project_membership_controls_are_wired_and_guarded` |

Clean-room implementation. No Plane instance, schema, bundle or proprietary code
was copied.

## What was built

- `modules/projects.py`: a `ProjectMember` table is the single registry for a
  project's `role` (lead/member/viewer), one `is_default_assignee` flag and
  `subscribed`. The creator is always a lead, so a private project never becomes
  unadministrable. Four endpoints (GET/POST list/add, PATCH/DELETE one member)
  manage it; they reject duplicates, non-workspace users, invalid roles, empty
  patches and removal of the project owner.
- PL-040: a `PROJECT_PERMISSIONS` matrix maps lead → read/write/admin, member →
  read/write, viewer → read. A router-level `project_access` dependency checks
  the role on **every** project route using the HTTP verb, so no endpoint is
  accidentally left open. Whole-project deletion additionally requires
  `project:admin`; project lists hide restricted projects the user is not a
  member of. Workspace owner/admin remain an explicit bypass and public
  projects keep the previous workspace-role fallback (T-053 semantics).
- `apps/web/app.js`: the New project dialog has a "Private project" checkbox;
  the project detail header marks a private project; and a Project access card
  (shown only to admins) lists members with role, default-assignee and
  subscription controls plus an add-member form. The member picker is the
  existing workspace assignee list, so no new privileged endpoint was needed.
  A 403 hides the card rather than presenting a dead button.
- Migration `c7d3e8a4f926` adds `projects.restricted` and `project_members`,
  idempotently, and reverses cleanly. Project deletion removes member rows.

## Commands and results

From `D:\NOVARA\apps\api` (Python at `D:\NOVARA\.venv\Scripts\python.exe`):

```
python -m pytest tests/test_project_membership_p0.py -q -rs
  4 passed, 1 warning in 2.54s

python -m pytest tests/test_project_membership_p0.py tests/test_ui_wiring.py -q -rs
  15 passed, 1 warning in 2.55s

python -m pytest -q -rs
  234 passed, 1 warning in 79.57s
```

From `D:\NOVARA`:

```
node --check apps\web\app.js                    -> no syntax errors
python -m compileall -q apps\api\novara_core    -> no errors
python scripts\runtime_smoke.py                 -> RUNTIME SMOKE: PASS (sections 1-12)
python C:\...\novara_t058_migrate_check.py
  upgrade -> downgrade -> upgrade                -> ROUND TRIP PASS, seeded project preserved
```

The only warning is the known Starlette/httpx TestClient deprecation notice.
No bearer tokens, response bodies or credentials were printed. A transient
diagnostic printed only a FastAPI validation detail (a workspace-custom state
name); it was removed once the smoke used a valid state.

## Behavior proved

- Restricted project creation returns `restricted: true` and a single lead row
  for the creator; role, default-assignee and subscription changes are audited.
- A viewer reads the project and items but cannot write or delete; after
  promotion to member they can write items but still cannot delete the project;
  after removal the project and its items are 404/403 and it disappears from
  their list.
- Public projects remain readable and writable by ordinary workspace members
  without a project membership row.
- Member management requires project admin; duplicates, invalid roles,
  non-members, empty patches and owner removal are all rejected.
- Runtime smoke section [12] repeats the grant → read → block → promote →
  write → revoke journey over real HTTP against a real uvicorn server.

## Matrix accounting

Only PL-003 and PL-040 were changed in `MASTER_FEATURE_MATRIX.csv`; all seven
FEATURE_PARITY deliverables were regenerated:

- 1,488 permanent IDs, zero omissions
- VERIFIED_COMPLETE 70 (was 68)
- complete-like 155 / 1,488 = 10.42% (was 153 / 10.28%)
- PARTIALLY_IMPLEMENTED 142 (was 144)
- P0: 111 rows — 63 verified, 7 partial, 32 replacement, 9 restricted

## Not claimed

- No live Plane instance, license or external sync.
- No workspace settings/feature-flag admin surface (PL-001 remains partial).
- No commit, push, tag, deployment or public publishing. Git HEAD remains
  `73e9f76`.

## Next

T-059: select from the 7 remaining P0 partial rows (PL-001, PL-043, MT-025,
MT-072, MT-112, MT-115, NV-057).
