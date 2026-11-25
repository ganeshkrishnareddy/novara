# No-default-dependency boundary — evidence (T-118, 2026-11-24)

Rows closed: MS-067, MS-097, PL-068, PL-149, PL-150, CW-122, NV-058, NV-059,
NV-094 (9 rows).

## Source basis

Feature-catalogue rows whose acceptance criterion is a negative evidence claim:
no unverified SDK, broker, cache connector, framework package or vendored
library is installed or claimed as a default. Existing third-party notices for
Meilisearch, Plane, Chatwoot and Novu were preserved unchanged.

## Implementation

New module `apps/api/novara_core/modules/dependency_boundary.py`, registered in
`novara_core/modules/__init__.py`. It serves a read-only, workspace-scoped
catalogue through `GET /api/v1/workspaces/{workspace_id}/dependency-boundary`
and `GET .../dependency-boundary/{row_id}`. Each of the 9 rows records a
NOVARA-local boundary name, the relevant provider, the notice to preserve,
`dependency_declared = false`, no external endpoint and an explicit note that no
SDK import, vendored package, external endpoint or unverified result is created
by the boundary.

There is no database table and no migration. Every route calls
`verify_workspace` and uses `require(EVENT_READ)`; cross-workspace access is
denied with 403 and unknown rows return 404.

## Constraints held

Named tests scan every active (non-comment) line of `apps/api/pyproject.toml`,
`Dockerfile` and `docker-compose.yml` for Slack SDK, Redis, RabbitMQ, Novu,
Meilisearch, LMDB and `@chatwoot/*` dependency tokens. Runtime sources are
checked for corresponding import/require statements. Vendored package
directories for those providers must not exist. The local search module is
checked to contain neither a Meilisearch SDK reference nor a mock-result claim.
Third-party notice text remains in `THIRD_PARTY_NOTICES.md`. No commit, push,
tag, deployment, publish, outbound HTTP or external delivery was made.
`socket.socket.connect` is patched to fail for non-loopback addresses in every
acceptance test.

## Verification

| Check | Result |
|---|---|
| Targeted named suite | `apps/api/tests/test_dependency_boundary_p2.py` — **9 passed, 1 warning in 8.85s** |
| Full regression | `docs/evidence/t118-fullsuite-20261124.txt` — **913 passed, 2 warnings in 708.99s (0:11:48)**, exit 0 (`docs/evidence/t118-fullsuite-exit.txt`) |
| Alembic head | unchanged single head `e0f1a2b3c4d5`; fresh-DB `alembic upgrade head` exit 0 |
| `alembic check` | `No new upgrade operations detected`, exit 0, on a fresh DB in the project virtual environment |

The baseline before this cluster was 904 passed; the delta of 9 is exactly the
new named acceptance tests. No production behaviour was changed outside the new
read-only boundary module and its router registration.
