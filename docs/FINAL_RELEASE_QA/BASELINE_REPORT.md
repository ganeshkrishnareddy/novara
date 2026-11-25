# Checkpoint 0 — baseline report

Timestamp: 2026-11-25 11:20 IST. Repository: `D:\NOVARA` (public `ganeshkrishnareddy/novara`), branch `main`.

| Item | Observed baseline |
|---|---|
| HEAD before publication | `73e9f76f6c8dd3360b73f7c5c8abec98726f28f8` |
| Working tree | 564 uncommitted status entries, preserved |
| Feature matrix | 1,488 rows: 1,418 `VERIFIED_COMPLETE`, 70 compatible replacements |
| Execution registry | 1,488 rows: 28 PASS, 932 PARTIAL, 70 REPLACEMENT_VERIFIED, 432 NOT_APPLICABLE, 26 NOT_TESTED, 0 FAIL |
| Migration head | single head `e0f1a2b3c4d5` (`python -m alembic heads`, run from `apps/api`) |
| Baseline full suite | 1,641 passed / 4 warnings / exit 0 in 1267.47s (2026-11-25 rerun) |
| API surface | 293 recorded API checks; 50 configured UI routes |
| Pages workflow | `.github/workflows/pages.yml` present but untracked; GitHub Pages not enabled |
| Known defects | Two frontend defects corrected in the QA pass; see `../QA/MASTER_QA_REPORT.md` |
| External blockers | Docker, live PostgreSQL, hosted providers, credentials, signed binaries — see `../BLOCKERS.md` |

No baseline file was deleted or rewritten. Evidence: `FEATURE_EXECUTION_REGISTRY.csv`, `../FEATURE_PARITY/COMPLETION_DASHBOARD.md`,
`../QA/MASTER_QA_REPORT.md`, `../../artifacts/final_qa_2026-11-24/test-results/regression-20261125-final.txt`.
