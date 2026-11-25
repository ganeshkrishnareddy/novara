# Access governance P2 — 2026-11-24

## Scope

Clean-room NOVARA implementation for licensing-restricted rows CW-130, CW-139, PL-124, PL-125, NV-070. No upstream source copied. No external service/licence/hosted control plane/IdP/SCIM/SIEM/EE auth package used. `socket.socket.connect` patched to fail in acceptance tests.

## Implementation

- Backend: `apps/api/novara_core/modules/access_governance.py`
- Permissions: `apps/api/novara_core/permissions.py` (NV-070 governance perms; admin role includes them)
- Enforcement: `apps/api/novara_core/dependencies.py` (`require` resolves `custom:<id>` roles)
- Migration: `apps/api/migrations/versions/c4d5e6f7a8b9_access_governance.py` (additive custom_roles, permission_schemes, permission_scheme_assignments)
- Module registration: `apps/api/novara_core/modules/__init__.py`
- SPA: `apps/web/app.js` (route/nav/loader/contract action/ag-* forms)
- Tests: `apps/api/tests/test_access_governance_p2.py`, `apps/web/tests/ui_v70_access_governance_contract.py`
- Spec: `docs/research/specs/access-governance-p2-20261124.json`

## Verification

`PYTHONPATH=apps/api; pytest apps/api/tests/test_access_governance_p2.py apps/web/tests/ui_v70_access_governance_contract.py -q --disable-warnings` => **7 passed, 1 warning in 5.73s**.

Alembic: single head `c4d5e6f7a8b9`; live DB upgraded from `f6a7b8c9d0e1`.

## Acceptance mapping

- CW-130: create/assign/change/revoke; server-enforced; cross-workspace denied.
- CW-139: audit query/export returns real actor/type/timestamp/correlation; `ip_recorded=false`; no IP column fabricated; workspace isolated.
- PL-124: allow-listed custom role editor; unknown/* rejected.
- PL-125: scheme create/assign/update propagates to assignments; audited.
- NV-070: fine-grained notification_workflow/integration/webhook/billing/audit permissions with named denial tests.
