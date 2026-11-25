# Clean-room Formbricks SDK replacement boundary — evidence (T-117, 2026-11-24)

Rows closed: FB-132, FB-133, FB-134, FB-135, FB-136, FB-137, FB-138, FB-139,
FB-140, FB-141, FB-142 (11 rows).

## Source basis

Public package paths in the feature catalogue for the MIT-licensed Formbricks
SDK subset, and the Formbricks GmbH notice already preserved in
`THIRD_PARTY_NOTICES.md`. No AGPL community core source, enterprise source,
package, hosted instance or external service was copied or contacted. The
replacement contracts are NOVARA-local names, not package imports.

## Implementation

New module `apps/api/novara_core/modules/formbricks_sdk_boundary.py`, registered
in `novara_core/modules/__init__.py`. It serves an immutable, workspace-scoped
catalogue through `GET /api/v1/workspaces/{workspace_id}/formbricks-sdk-boundary`
and `GET .../formbricks-sdk-boundary/{row_id}`. Each of the 11 rows records:

- the exact advertised package path/name;
- a NOVARA-local replacement contract (`novara_*`);
- the public documentation reference;
- the preserved Formbricks GmbH MIT notice reference;
- `dependency_declared = false` and no external endpoint;
- an explicit clean-room replacement note.

There is no database table and no migration. Every route calls
`verify_workspace` and uses `require(EVENT_READ)`; cross-workspace access is
denied with 403 and unknown rows return 404.

## Constraints held

No Formbricks SDK dependency appears in `apps/api/pyproject.toml`, `Dockerfile`
or `docker-compose.yml`; no `import formbricks`, `from formbricks`,
`require('formbricks')` or `require('@formbricks/...')` appears in the static web
runtime. No AGPL/EE source was vendored. The preserved notice text remains in
`THIRD_PARTY_NOTICES.md`. No commit, push, tag, deployment, publish, outbound
HTTP or external delivery was made. `socket.socket.connect` is patched to fail
for non-loopback addresses in every acceptance test.

## Verification

| Check | Result |
|---|---|
| Targeted named suite | `apps/api/tests/test_formbricks_sdk_boundary_p2.py` — **11 passed, 1 warning in 8.24s** |
| Full regression | `docs/evidence/t117-fullsuite-20261124.txt` — **904 passed, 2 warnings in 714.97s (0:11:54)**, exit 0 (`docs/evidence/t117-fullsuite-exit.txt`) |
| Alembic head | unchanged single head `e0f1a2b3c4d5`; fresh-DB `alembic upgrade head` exit 0 |
| `alembic check` | `No new upgrade operations detected`, exit 0, on a fresh DB in the project virtual environment |

The baseline before this cluster was 893 passed; the delta of 11 is exactly the
new named acceptance tests. No production behaviour was changed outside the new
read-only boundary module and its router registration.
