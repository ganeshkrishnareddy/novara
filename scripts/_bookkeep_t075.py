"""Append the final P1 verification record (T-075) to the status docs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

with (ROOT / "docs" / "NOVARA_AUTONOMOUS_EXECUTION.md").open("a", encoding="utf-8") as fh:
    fh.write("""

### T-075 - final verification and deliverable regeneration (2026-11-23)

- Closed out the remaining P1 clusters from T-073/T-074 with a fresh full
  verification. API keys (PL-045/PL-070), Plane work items and progress
  (PL-021/PL-042), project intake (PL-088) and support saved replies and
  segments (CW-023/CW-075) are all VERIFIED_COMPLETE in the matrix with
  per-field evidence and named tests: test_api_keys_p1.py,
  test_api_keys_ui_p1.py, test_project_intake_p1.py and
  test_plane_support_ui_p1.py.
- Targeted re-run from D:\\NOVARA:
  - API-key backend + settings UI: 6 passed.
  - Plane/support UI + project intake: 6 passed.
- Full verification from D:\\NOVARA:
  - full API suite: **410 passed, 1 warning in 277.61s** (upstream
    Starlette/httpx deprecation only);
  - `node --check apps/web/app.js`: exit 0;
  - runtime smoke: PASS, sections [1]-[15] against a real uvicorn server;
  - migration round trip e2f4a6b8c0d3 -> f5a7b9c1d2e4 -> e2f4a6b8c0d3 ->
    head: PASS with existing data preserved.
- Matrix accounting (1,488 rows): 213 VERIFIED_COMPLETE, 65 compatible
  replacements, 236 LICENSING_RESTRICTED, 135 EXTERNAL_DEPENDENCY_BLOCKED,
  85 PARTIALLY_IMPLEMENTED, 30 IMPLEMENTED_UNVERIFIED and 724
  NOT_IMPLEMENTED. The P0 set (111 rows) remains fully disposed.
- All seven FEATURE_PARITY deliverables regenerated from the live matrix
  (FEATURE_TEST_EVIDENCE: 213 verified / 30 unverified; completion dashboard:
  308/1,488 = 20.70% complete-like).
- No commit, push, deploy, publish or external send was made.
""")

with (ROOT / "docs" / "MASTER_TASK_BOARD.md").open("a", encoding="utf-8") as fh:
    fh.write(
        "| T-075 | Final verification + FEATURE_PARITY deliverable "
        "regeneration (T-073/T-074 closure) | MausBot | DONE | T-074 | "
        "`docs/FEATURE_PARITY/*.md`, `docs/NOVARA_AUTONOMOUS_EXECUTION.md`, "
        "`docs/TEST_RESULTS.md` | Full suite 410 passed, 1 warning; "
        "`node --check` exit 0; runtime smoke PASS [1]-[15]; migration "
        "round-trip PASS with data preserved; matrix 213 VERIFIED / 1,488 "
        "rows; all seven deliverables regenerated | - |\n"
    )

with (ROOT / "docs" / "TEST_RESULTS.md").open("a", encoding="utf-8") as fh:
    fh.write("""

## T-075 - final full suite after P1 API-key / UI closure (2026-11-23)

- Test ID: T-075 / T-FULL.
- Environment: `D:\\NOVARA`, local `.venv` Python 3.12, SQLite dev database,
  no external services.
- Preconditions: API-key module and Settings UI, grouped work-item list,
  progress cards, project intake and support saved-reply/segment UI in place;
  migration head `f5a7b9c1d2e4`.
- Command: `.venv\\Scripts\\python.exe -m pytest apps/api/tests -q`
- Result: **410 passed, 1 warning in 277.61s** (upstream Starlette/httpx
  deprecation).
- Targeted: `test_api_keys_p1.py` + `test_api_keys_ui_p1.py` -> 6 passed;
  `test_plane_support_ui_p1.py` + `test_project_intake_p1.py` -> 6 passed.
- Other checks: `node --check apps/web/app.js` exit 0; runtime smoke PASS
  sections [1]-[15] on a real uvicorn server; migration round trip PASS with
  existing data preserved.
- Evidence: `docs/evidence/plane-api-keys-p1-20261123.md`,
  `docs/evidence/plane-support-ui-p1-20261123.md`,
  `docs/evidence/plane-project-intake-p1-20261123.md`.
- Result: PASS. No external network calls or real sends.
""")

print("bookkeeping appended")
