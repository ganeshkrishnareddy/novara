# Phase 2/3 execution checklist and dependency map

Created 2026-11-22. Living document; status changes only with linked evidence.

## Baseline captured before any change

| Item | Observed |
|---|---|
| Git HEAD | `73e9f76` (`docs: complete final repository audit; close research gate`) |
| Git status | 8 modified tracked docs; untracked `apps/`, `docs/CHECKPOINT_2026-11-22.md`, `docs/QA_ROUNDS_2026-11-22.md`, `docs/INSTALL.md`, `docs/architecture/`, `scripts/`, Dockerfile, docker-compose.yml, .gitignore |
| Backend suite | `99 passed, 2 warnings in 77.60s` (upstream `anyio`/`starlette` deprecations) |
| Health endpoint | `{"status":"ok","product":"NOVARA"}` after restart on 127.0.0.1:8000 |
| Database | SQLite `D:\NOVARA\novara_dev.sqlite3`; Alembic revision `6d610706f4ff` |
| Frontend | `apps/web/{index.html,styles.css,app.js}`, light theme only; `node --check` clean |
| Modules | 11 registered modules, all routers attached by `include_all(app)` |
| Known blockers | No Docker/PostgreSQL; no real outbound adapters; no installers/signing; owner decisions on licence/domain |

## Dependency map

```
database / models / permissions / events / security / dependencies
        -> core API (main.py, workflow.py)
        -> capability modules (including jobs.py, adapters additions)
        -> frontend (app.js) -> browser E2E
        -> docs (phase reports, release readiness)
```

File ownership during this execution: one owner (MausBot) edits each file
sequentially; no two workstreams touch the same file at once.

## Phase 2 workstreams

| ID | Work | Evidence | Status |
|---|---|---|---|
| P2-1 | PostgreSQL portability review + local compatibility tests | `tests/test_portability.py`; all 37 tables compile to PG DDL, `FOR UPDATE SKIP LOCKED` compiles | IMPLEMENTED / VERIFICATION BLOCKED (no driver or server) |
| P2-2 | Multi-workspace isolation tests (2 workspaces, multiple roles, allowed/denied) | `tests/test_isolation.py` | PASS |
| P2-3 | CRM transaction integrity (idempotency, rollback, correlation, retries) | `tests/test_integrity.py` | PASS |
| P2-4 | Durable job queue: enqueue, run, retry/backoff, dead-letter, cancel, recovery, dashboard API | `modules/jobs.py` + `tests/test_jobs.py` (9 tests) | PASS |
| P2-5 | Adapter architecture with mock/sandbox providers, validation, logs | `modules/adapters.py` + `tests/test_adapters.py` (7 tests) | PASS (local mock only) |
| P2-6 | Audit/monitoring: job and integration events, operational summary | `modules/operations.py` + `tests/test_operations.py` (4 tests) | PASS |
| P2-7 | Backup/restore into an isolated SQLite database | `scripts/backup_restore.py` + `tests/test_backup_restore.py` (2 tests) | PASS |
| P2-8 | Security hardening: headers, rate limit, CORS config, tests | `middleware.py`, `errors.py` + `tests/test_security.py` (4 tests); live headers observed on `/health` | PASS |

## Phase 3 workstreams

| ID | Work | Evidence | Status |
|---|---|---|---|
| P3-1 | Frontend integration for dashboard metrics and job/adapter views | Browser walkthrough: Overview system-health card renders real counts; Job queue and Adapters views load | PASS (three bugs found and fixed during E2E: same-origin API base, operations object coercion, cwd-relative DB path) |
| P3-2 | Dashboard BI endpoint with real aggregates and workspace filters | `tests/test_listing.py` (4 tests) + browser Insights view showing real counts and event-volume bars | PASS |
| P3-3 | Agent Center / Integrations status distinctions and mock test actions | Browser: System health reports Local/Local Mock/Blocked separately; adapter "Test mock" on a `not_configured` provider was rejected and recorded with `delivered = false` | PASS |
| P3-4 | Search/filter/sort/pagination on leads and tasks | `tests/test_listing.py`: search, status filter, sort, order, skip/limit, invalid-value rejection, workspace scoping | PASS |
| P3-5 | E2E acceptance journeys in browser | Browser: sign-in → Overview → intake workflow submit → draft approval → cross-view navigation, all with real stored rows | PASS (local) |
| P3-6 | Performance measurements (local, honest parameters) | `scripts/performance_probe.py` + `docs/evidence/performance-probe-20261122.txt` — 20 sequential iterations × 10 endpoints, medians 6–29 ms, all 200 | PASS (local, not a load test) |
| P3-7 | Deployment preparation (config template, runbook, rollback) | `.env.example`, `docs/DEPLOYMENT_RUNBOOK.md` | PASS (preparation only; no deployment performed) |
| P3-8 | Phase 2/3 completion reports + final release readiness | `docs/PHASE_3_COMPLETION_REPORT.md`, `docs/FINAL_RELEASE_READINESS.md` | PASS |

## Acceptance gate between phases

Phase 3 starts only after the Phase 2 report exists and no blocking failure is
open. Infrastructure-blocked items are marked implementation-complete /
verification-blocked, never passed.

## Final verification evidence (2026-11-22)

- Backend suite after all Phase 2/3 edits: `143 passed, 2 warnings in 48.10s`
  (evidence: `docs/evidence/backend-suite-20261122-201553.txt`). Baseline was
  99 passed; Phase 2 added 40, Phase 3 added 4.
- Alembic head `9951aadc14c8`; `alembic check` from `apps/api` → exit 0,
  "No new upgrade operations detected".
- `GET /health` → 200 `{"status":"ok","product":"NOVARA"}` with security headers
  (`nosniff`, `DENY`, `no-referrer`, CSP, cross-domain-policies none) present.
- `node --check apps/web/app.js` → clean after frontend edits.
- Follow-up (2026-11-22): the Dockerfile now carries the Alembic config and
  migrations and runs `alembic upgrade head` before uvicorn. Verified locally
  against a fresh SQLite file: both revisions applied, DB stamped at
  `9951aadc14c8` with 37 tables, `alembic check` clean. Evidence:
  `docs/evidence/container-migration-check-20261122.txt`. This is migration-logic
  verification only — the image build and container run remain blocked (B-01).
- Git HEAD unchanged at `73e9f76`; no commit, push, tag, reset, rebase,
  force-push or deploy. All product work is local/uncommitted.
- Two warnings remain from upstream `anyio`/`starlette` deprecations, present at
  baseline and reported openly; no test was weakened or skipped to reach green.

Infrastructure-blocked items stay `IMPLEMENTED / VERIFICATION BLOCKED`, not
`PASS`: PostgreSQL live, Docker/container, real credentials/outbound delivery,
installer/signing/store, physical device testing, production deployment.
