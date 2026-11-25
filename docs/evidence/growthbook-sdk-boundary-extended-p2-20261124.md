# Extended clean-room GrowthBook SDK compatibility boundary — evidence (T-116, 2026-11-24)

Rows closed: GB-158, GB-159, GB-160, GB-161, GB-162, GB-163, GB-164, GB-165,
GB-166, GB-167, GB-168, GB-169, GB-170, GB-171, GB-172, GB-173 (16 rows).

## Source basis

Documented/public SDK and provider references in the feature catalogue and the
GrowthBook MIT notice preserved in `THIRD_PARTY_NOTICES.md`. No upstream SDK
source, package, hosted instance, licence server, warehouse or enterprise code
was copied or contacted. The catalogued adapter names are NOVARA-local boundary
names, not package imports.

## Implementation

The existing clean-room module
`apps/api/novara_core/modules/growthbook_sdk_boundary.py` was extended from the
GB-148..GB-157 catalogue to GB-148..GB-173. No new table, column, route family,
permission or Alembic revision was needed: the additive workspace-scoped
`gbsdk_boundaries` table created by revision `e0f1a2b3c4d5` already stores the
public documentation reference, NOVARA-local boundary/adapter name, preserved
MIT attribution, `default_dependency = false`, no external endpoint and the
explicit boundary note. Seeding remains idempotent through the unique
`(workspace_id, sdk_id)` constraint and publishes
`growthbook_sdk_boundary.changed` on NOVARA's shared event spine. All routes keep
`verify_workspace`, `require(WORKSPACE_MANAGE)` for writes and `require(EVENT_READ)`
for reads; cross-workspace reads fail closed.

Sixteen new named acceptance tests live in
`apps/api/tests/test_growthbook_sdk_boundary_extended_p2.py`. The original ten
T-115 tests were rerun together with them.

## Constraints held

No GrowthBook SDK dependency is declared in `apps/api/pyproject.toml`,
`Dockerfile` or `docker-compose.yml`; no `import growthbook` or
`require('growthbook')` appears in the static web runtime sources. The preserved
MIT notice remains in `THIRD_PARTY_NOTICES.md`. No commit, push, tag,
deployment, publish, upstream source copy, outbound HTTP or external delivery
was made. `socket.socket.connect` is patched to fail for non-loopback addresses
in every acceptance test.

## Verification

| Check | Result |
|---|---|
| Targeted named suites | `test_growthbook_sdk_boundary_p2.py` + `test_growthbook_sdk_boundary_extended_p2.py` — **26 passed, 1 warning in 16.51s** (10 T-115 rows + 16 T-116 rows) |
| Full regression | `docs/evidence/t116-fullsuite-20261124.txt` — **893 passed, 2 warnings in 591.11s (0:09:51)**, exit 0 (`docs/evidence/t116-fullsuite-exit.txt`) |
| Alembic head | unchanged single head `e0f1a2b3c4d5`; fresh-DB `alembic upgrade head` exit 0 |
| `alembic check` | `No new upgrade operations detected`, exit 0, on a fresh DB in the project virtual environment |

The baseline before this cluster was 877 passed; the delta of 16 is exactly the
new named acceptance tests. No production behaviour was changed outside the
catalogue data of the additive SDK-boundary module.
