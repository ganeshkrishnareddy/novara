# Clean-room GrowthBook SDK compatibility boundary — evidence (T-115, 2026-11-24)

Rows closed: GB-148, GB-149, GB-150, GB-151, GB-152, GB-153, GB-154, GB-155,
GB-156, GB-157 (10 rows).

## Source basis

Documented/public SDK references in the feature catalogue and the GrowthBook MIT
notice preserved in `THIRD_PARTY_NOTICES.md`. No upstream SDK source, package,
hosted instance, licence server, warehouse or enterprise code was copied or
contacted. The catalogued adapter names are NOVARA-local boundary names, not
package imports.

## Implementation

New module `apps/api/novara_core/modules/growthbook_sdk_boundary.py`, registered
in `novara_core/modules/__init__.py`. Alembic revision `e0f1a2b3c4d5` (down
revision `d9e0f1a2b3c4`, single head) adds one workspace-scoped `gbsdk_boundaries`
table. It records, for each advertised SDK path:

- the feature ID and public documentation reference;
- a NOVARA-local compatibility boundary and adapter name;
- the preserved `Copyright (c) 2025 GrowthBook, Inc. | MIT license` attribution;
- `default_dependency = false` and no external endpoint;
- an explicit note that this is a compatibility boundary only.

Seeding is idempotent through a unique `(workspace_id, sdk_id)` constraint and
publishes a `growthbook_sdk_boundary.changed` event on NOVARA's shared event
spine. All routes call `verify_workspace` and use `require()` with
`WORKSPACE_MANAGE` for seeding and `EVENT_READ` for reads. Cross-workspace reads
fail closed.

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
| Targeted named suite | `apps/api/tests/test_growthbook_sdk_boundary_p2.py` — **10 passed, 1 warning in 7.71s** |
| Full regression | `docs/evidence/t115-fullsuite-20261124.txt` — **877 passed, 2 warnings in 576.07s (0:09:36)**, exit 0 (`docs/evidence/t115-fullsuite-exit.txt`) |
| Alembic head | single head `e0f1a2b3c4d5`; fresh-DB `alembic upgrade head` exit 0 |
| `alembic check` | `No new upgrade operations detected`, exit 0, on a fresh DB in the project virtual environment |

The baseline before this cluster was 867 passed; the delta of 10 is exactly the
new named acceptance tests. No production behaviour was changed outside the
additive SDK-boundary table and the new module.
