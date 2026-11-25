"""Append the T-076 plane worker/portability record to the status docs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

with (ROOT / "docs" / "NOVARA_AUTONOMOUS_EXECUTION.md").open("a", encoding="utf-8") as fh:
    fh.write("""

### T-076 - Plane worker and portability P1 (PL-071, PL-147, PL-148)

- Added `apps/api/tests/test_plane_worker_portability_p1.py` with three named
  acceptance tests (3 passed):
  - PL-071 proves the real `JobWorker` claims and completes a job on its own
    background thread with no direct `tick()` call from the test, and that the
    completed state and audit events are readable from a fresh session. This
    is a local stand-in for a Celery worker; no broker or Docker is claimed.
  - PL-147 proves the Alembic chain has exactly one head and every model table
    compiles to PostgreSQL DDL without SQLite-only syntax (compile-only; no
    live PostgreSQL run).
  - PL-148 proves every workspace-scoped table compiles to PostgreSQL DDL and
    that a bootstrap membership row persists locally in a fresh session.
- Matrix: the three rows moved to VERIFIED_COMPLETE via
  `scripts/specs/p1-plane-worker-portability-20261123.json`; evidence in
  `docs/evidence/plane-worker-portability-p1-20261123.md`.
- Full API suite: **413 passed, 2 warnings in 252.62s**. No frontend or
  migration change in this cluster, so the T-075 node check, runtime smoke and
  migration round trip remain current.
- Regenerated all seven FEATURE_PARITY deliverables: 216 VERIFIED_COMPLETE of
  1,488 rows, complete-like 310/1,488 = 20.83%. P1 now stands at 171 verified,
  16 compatible replacements, 9 not implemented, 12 licensing-restricted,
  8 externally blocked and 2 partially implemented.
- Remaining P1 rows are deliberately blocked or deferred: MT-051/MT-066 need
  verified external actions with credentials; GB-060/GB-087 stay deliberately
  unclaimed as clean-room slices; the seven MK rows require a vendoring
  decision and the pinned third-party skill sources, which are not present
  locally. No external fetch, send, commit, push or deploy was made.
""")

with (ROOT / "docs" / "MASTER_TASK_BOARD.md").open("a", encoding="utf-8") as fh:
    fh.write(
        "| T-076 | Stage 2: Plane worker + portability P1 "
        "(PL-071/147/148) | MausBot | DONE | T-075 | "
        "`modules/jobs.py`, `scripts/job_worker.py`, "
        "`tests/test_plane_worker_portability_p1.py`, "
        "`scripts/specs/p1-plane-worker-portability-20261123.json`, "
        "`docs/evidence/plane-worker-portability-p1-20261123.md` | "
        "3 named tests pass; real async worker thread with durable state; "
        "single Alembic head; all tables compile to PostgreSQL DDL; "
        "full suite 413 passed; 3 P1 rows VERIFIED_COMPLETE | - |\n"
    )

with (ROOT / "docs" / "TEST_RESULTS.md").open("a", encoding="utf-8") as fh:
    fh.write("""

## T-076 - Plane worker and portability named tests (2026-11-23)

- Test ID: T-076.
- Environment: `D:\\NOVARA`, local `.venv` Python 3.12, in-memory SQLite via
  the shared test fixture; no broker, container or live PostgreSQL.
- Command: `.venv\\Scripts\\python.exe -m pytest "
        "apps/api/tests/test_plane_worker_portability_p1.py -q`
- Result: **3 passed, 2 warnings** (upstream Starlette/httpx and Alembic
  config deprecations).
- Full suite: **413 passed, 2 warnings in 252.62s**.
- Checks: real `JobWorker` background thread completes a job with durable
  audited state; single Alembic head; every model/workspace table compiles to
  PostgreSQL DDL; local persistence proved in a fresh session.
- Evidence: `docs/evidence/plane-worker-portability-p1-20261123.md`.
- Result: PASS. No live PostgreSQL, broker, container or external call.
""")

print("bookkeeping appended")
