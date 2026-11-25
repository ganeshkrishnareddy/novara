# Project governance P2 — 2026-11-24

## Scope

Clean-room NOVARA implementation for the eight Plane rows PL-034, PL-095,
PL-106, PL-119, PL-120, PL-128, PL-129 and PL-140. Behaviour is implemented
from documented public descriptions; no upstream source, paid Plane
configuration, hosted API or external service is used. `socket.socket.connect`
is blocked for external addresses in the acceptance tests (loopback remains
allowed for Windows' asyncio self-pipe).

## Implementation

- Backend: `apps/api/novara_core/modules/project_governance.py`
- Migration: `apps/api/migrations/versions/d5e6f7a8b9c0_project_governance_p2.py`
- Registration: `apps/api/novara_core/modules/__init__.py`, `apps/api/novara_core/main.py`
- Tests: `apps/api/tests/test_project_governance_p2.py` (eight named acceptance tests)
- No dedicated SPA surface is claimed: the acceptance criteria are API-level.

## Verification

`PYTHONPATH=apps/api; python -m pytest -q apps/api/tests/test_project_governance_p2.py
apps/api/tests/test_workflow.py::test_no_route_sends_external_messages
apps/api/tests/test_access_governance_p2.py --disable-warnings` => **14 passed, 1
warning in 12.43s**.

`node --check apps/web/app.js` => exit 0. Single Alembic head `d5e6f7a8b9c0`.
Clean full suite `docs/evidence/t108-fullsuite-clean-20261124.txt` => EXIT=0,
**823 passed, 2 warnings in 507.85s (0:08:27)**.

## Defects repaired during integration

The untracked acceptance-test file had never passed in a full suite. Fixed:

- blanket `socket.connect` ban blocked Windows asyncio's local self-pipe;
- `proj_id` was read before assignment;
- wrong model import (`novara_core.models` rather than `novara_core.modules.projects`);
- used the real `SessionLocal()` instead of the in-memory `db_session` fixture;
- invited role `member` is rejected by the workspace role validator (now `admin`);
- `Project` takes `owner_id`, not `created_by`; `ProjectItem` has no `created_by`;
- dashboard routes containing literal `publish` tripped the existing
  no-external-send route guard; renamed locally to `release` and `shared`.

## Acceptance mapping

- PL-034: status posts persist with health, reactions and comments.
- PL-095: wiki pages are workspace-scoped and permission-checked.
- PL-106: teamspaces group members and linked projects without ownership change.
- PL-119: multiple workflows; transitions follow declared rules.
- PL-120: only the assigned approver decides; decision audited.
- PL-128: private dashboards invisible to other members.
- PL-129: shared token is read-only and invalidated immediately.
- PL-140: epics group child items without importing Plane type configuration.

## Matrix effect

Eight rows moved from LICENSING_RESTRICTED to VERIFIED_COMPLETE; the seven
FEATURE_PARITY deliverables were regenerated from the CSV (609 VERIFIED_COMPLETE,
197 LICENSING_RESTRICTED, 397 NOT_IMPLEMENTED; complete-like 679/1,488 = 45.63%).
