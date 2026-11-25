# Evidence — Plane worker and portability P1 (PL-071, PL-147, PL-148)

Date: 2026-11-23. All checks run locally from `D:\NOVARA` with the project
virtualenv. No live PostgreSQL server, broker, container or external service
was used; no commit, push, deploy, publish or external send was made.

## Named tests

`apps/api/tests/test_plane_worker_portability_p1.py` — 3 passed.

### PL-071 — Celery worker / durable async jobs

`test_pl071_worker_processes_job_asynchronously_with_durable_state`

- A real `JobWorker` is started on its own background thread with a 20 ms poll
  interval and an injected session factory bound to the test database.
- A `noop` job is enqueued through `enqueue_job`; the test never calls `tick()`,
  `run_one_job()` or `run_pending_jobs()` itself. The job reaches `succeeded`
  solely through the worker thread, proving asynchronous processing.
- Durable state is read from a brand-new session: `finished_at` is set, the job
  is unlocked, and the `job.started` event carries `worker_id=test-async-worker`
  while `job.completed` records one attempt.
- This is a local stand-in for a Celery worker. No broker, Docker or distributed
  infrastructure is claimed.

### PL-147 — Migration workflow / PostgreSQL DDL

`test_pl147_migration_chain_and_postgres_ddl`

- Alembic's script directory reports exactly one migration head, so the chain
  is linear and migrates cleanly.
- Every table in `Base.metadata.sorted_tables` compiles to PostgreSQL DDL with
  no SQLite-only `AUTOINCREMENT` or `PRAGMA` syntax; `events` uses `SERIAL`
  and the compiled schema contains `JSON`.
- This is compile-only verification of PostgreSQL DDL. No live PostgreSQL run
  is claimed.

### PL-148 — PostgreSQL persistence

`test_pl148_workspace_tables_compile_and_persist`

- Every table in the metadata that carries a `workspace_id` column is
  discovered dynamically and asserted to compile to PostgreSQL DDL containing
  that column; there are at least 30 such tables.
- A workspace membership row written through the real bootstrap flow is read
  back from a fresh session, proving local persistence of the same table.
- Live PostgreSQL persistence is not claimed; compile-to-PostgreSQL plus local
  persistence is the stated acceptance criterion.

## Verification summary

- Targeted: 3 passed.
- Full API suite after folding: see `docs/TEST_RESULTS.md` (T-076).
- `node --check apps/web/app.js`: exit 0 (no frontend change in this cluster).
