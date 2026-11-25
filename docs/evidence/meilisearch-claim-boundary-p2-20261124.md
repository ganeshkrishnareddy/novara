# Meilisearch no-unverified-claim boundary — evidence (T-120, 2026-11-24)

Rows closed: MS-052, MS-054, MS-060, MS-066, MS-068, MS-069, MS-070, MS-071,
MS-072, MS-073, MS-079, MS-081, MS-082, MS-094, MS-100, MS-102 (16 rows).

## Source basis

The Meilisearch feature catalogue contains rows whose acceptance criterion is a
negative evidence claim: NOVARA must not advertise a webhook delivery, remote
export, metrics, document-level RBAC, framework connector, MCP search tool,
conversational answer, source citation, vector store, personalized ranking,
image search, engine certificate, telemetry opt-out, bulk importer, vendored
external crate or CLI-driven search that is backed by an unverified
Meilisearch dependency or external service. The Meilisearch MIT notice was
preserved unchanged.

## Implementation

New module `apps/api/novara_core/modules/meilisearch_claim_boundary.py`,
registered in `novara_core/modules/__init__.py`. It serves a read-only,
workspace-scoped catalogue through
`GET /api/v1/workspaces/{workspace_id}/meilisearch-claim-boundary` and
`GET .../meilisearch-claim-boundary/{row_id}`. Each of the 16 rows records a
NOVARA-local boundary name, the denied claim, the preserved Meilisearch MIT
notice, `dependency_declared = false`, no external endpoint, and an explicit
note that no SDK import, vendored crate, external endpoint or unverified search
result is created by the boundary.

There is no database table and no migration. Every route calls
`verify_workspace` and uses `require(EVENT_READ)`; cross-workspace access is
denied with 403 and unknown rows return 404.

## Constraints held

Named tests scan every active (non-comment) line of `apps/api/pyproject.toml`,
`Dockerfile` and `docker-compose.yml`, all runtime module sources except the
boundary module itself, and the static web runtime for precise tokens
indicating each claimed capability. Vendored crate directories are checked for
copies of external Meilisearch crates. The local search module is checked to
contain neither a Meilisearch SDK reference nor a mock-result claim. The
Meilisearch MIT notice text remains in `THIRD_PARTY_NOTICES.md`. No commit,
push, tag, deployment, publish, outbound HTTP or external delivery was made.
`socket.socket.connect` is patched to fail for non-loopback addresses in every
acceptance test.

## Verification

| Check | Result |
|---|---|
| Targeted named suite | `apps/api/tests/test_meilisearch_claim_boundary_p2.py` — **16 passed, 1 warning in 11.53s** |
| Full regression | `docs/evidence/t120-fullsuite-clean-20261124.txt` — **929 passed, 2 warnings in 699.28s (0:11:39)**, exit 0 (`docs/evidence/t120-fullsuite-clean-exit.txt`) |
| Alembic head | unchanged single head `e0f1a2b3c4d5`; fresh-DB `alembic upgrade head` exit 0 |
| `alembic check` | `No new upgrade operations detected`, exit 0, on a fresh DB in the project virtual environment |

The baseline before this cluster was 913 passed; the delta of 16 is exactly the
new named acceptance tests. An earlier partial full-suite file
(`t120-fullsuite-20261124.txt`) was interrupted and is not evidence of a run;
the clean run above supersedes it.
