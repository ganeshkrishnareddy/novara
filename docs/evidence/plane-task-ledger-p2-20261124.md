# Clean-room Plane local background-task ledger — evidence (T-114, 2026-11-24)

Rows closed: PL-073, PL-076, PL-078, PL-081, PL-082, PL-083, PL-084, PL-086
(8 rows).

## Source basis

Documented/public behaviour from the Plane background-task descriptions and the
acceptance criteria in the feature catalogue. No upstream Plane source, Celery
broker, hosted instance, paid tier or external service was copied or contacted.
Every algorithm and route is a clean-room implementation derived only from the
published behaviour and the row acceptance criteria.

## Implementation

New module `apps/api/novara_core/modules/plane_task_ledger.py`, registered in
`novara_core/modules/__init__.py`. Nine additive workspace-scoped `plt_*` tables
were created by Alembic revision `d9e0f1a2b3c4` (down revision `c8d9e0f1a2b3`,
single head): `plt_task_results`, `plt_email_policies`, `plt_email_drafts`,
`plt_webhook_endpoints`, `plt_webhook_deliveries`, `plt_exports`,
`plt_page_versions`, `plt_asset_processings`, `plt_seed_defaults`. Execution uses
NOVARA's existing durable `jobs` table and its registered local handlers; no
existing job, project, page, storage or event row is altered.

Per row, with `external_calls: false` and `external_delivery: false` throughout:

- **PL-073** — a completed local task writes a durable result keyed by
  `request_key`; the result is queryable afterwards and a different workspace
  cannot read it.
- **PL-076** — the default install has no email policy and generates no draft.
  Enabling requires an explicit authorization act; even then the background
  task only creates a local `local_only` draft, never an outbound message.
- **PL-078** — webhook deliveries are HMAC-SHA256 signed, locally recorded with
  attempt number and outcome, retried through the durable queue, and listed as
  an audit trail. Only the secret hash is stored; the signing secret is shown
  once at creation. No outbound HTTP occurs.
- **PL-081** — a work-item export task completes into a stored local CSV/JSON
  file and is downloaded through a workspace-scoped boundary; a foreign
  workspace's work item never appears.
- **PL-082** — chart export reuses the same `chart_series` aggregate function as
  the displayed series endpoint, excluding internal job audit events, so the
  downloaded data matches what is shown.
- **PL-083** — each page-edit task snapshots the current `project_pages` row
  into the next retrievable version, with stable per-page version numbering.
- **PL-084** — asset metadata is written only after real local bytes are read,
  the size matches and the SHA-256 checksum matches the stored file; a missing
  file leaves no metadata row.
- **PL-086** — workspace seeding is idempotent through a unique workspace/key
  constraint and creates only the three declared defaults, once.

Every route calls `verify_workspace` and the appropriate `require()` capability
(`EVENT_READ` or `WORKSPACE_MANAGE`). `plane_task_ledger.changed` events are
published on NOVARA's shared event spine. All acceptance criteria are
API/server-level, so no dedicated SPA surface or dark-mode UI is claimed.

## Constraints held

All work is local: no commits, pushes, tags, deployments, publishes, upstream
source copies or real external sends. No broker, outbound email, outbound
webhook, outbound HTTP or external delivery is used.
`socket.socket.connect` is patched to fail for non-loopback addresses in every
acceptance test.

## Verification

| Check | Result |
|---|---|
| Targeted named suite | `apps/api/tests/test_plane_task_ledger_p2.py` — **8 passed, 1 warning in 6.79s** |
| Full regression | `docs/evidence/t114-fullsuite-20261124.txt` — **867 passed, 2 warnings in 581.12s (0:09:41)**, exit 0 (`docs/evidence/t114-fullsuite-exit.txt`) |
| Alembic head | single head `d9e0f1a2b3c4`; fresh-DB `alembic upgrade head` exit 0 |
| `alembic check` | `No new upgrade operations detected`, exit 0, on a fresh DB in the project virtual environment |

The baseline before this cluster was 859 passed; the delta of 8 is exactly the
new named acceptance tests. No production behaviour was changed outside the
additive task-ledger tables and the new module.
