# Final regression report

Timestamp: 2026-11-25 11:35 IST. All commands run locally on this computer; no external service contacted.

| Command | Observed result |
|---|---|
| `python -m pytest apps/api/tests -q` (from `D:\NOVARA`) | **1,641 passed, 4 warnings, exit 0 in 1267.47s (0:21:07)** |
| `python scripts/validate_site.py` | **35 passed, 0 failed, 0 warnings, 15 informational; RESULT: PASS** |
| `node --check apps/web/app.js` (main + 4 worktrees) | exit 0 for all five files |
| `python -m alembic heads` (from `apps/api`) | `e0f1a2b3c4d5 (head)` — single head |
| `git ls-remote origin HEAD` | reachable, no credential exposed |

Evidence: `../../artifacts/final_qa_2026-11-24/test-results/regression-20261125-final.txt`,
`../../artifacts/marketing_site_qa/validator-final.txt`, `../TEST_RESULTS.md`.

The 4 pytest warnings are upstream `starlette`/`httpx` and `alembic` deprecations, not failures.
This is a local regression result only; it does not establish deployment or provider readiness.
