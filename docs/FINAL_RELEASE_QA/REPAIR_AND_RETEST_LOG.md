# Repair and retest log

| # | Defect or issue | Repair | Retest |
|---|---|---|---|
| 1 | Two frontend defects found during the 2026-11-24 browser pass | Corrected in `apps/web/app.js` in the working tree | All 50 configured UI routes rendered; browser checks pass |
| 2 | Layered mojibake (`ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â` for `—`) in `docs/MASTER_TASK_BOARD.md` and four stale worktree `app.js` copies | Reversed the encoding layers; backups under `artifacts/final_qa_2026-11-24/evidence/mojibake_backups_20261125/` | Repository-wide scan: only intentional QA test fixtures remain; `node --check` exit 0 on all five files |
| 3 | Stale Alembic head `9951aadc14c8` in `docs/INSTALL.md` | Updated to verified head `e0f1a2b3c4d5` | `python -m alembic heads` → single head `e0f1a2b3c4d5` |
| 4 | Site FAQ/footer claimed "not published" while publication was authorized | Wording changed to neutral/official-site wording in `site/index.html` | Static validator 35 passed / 0 failed; CI build job success |
| 5 | Final gate forbids `PARTIAL` as a status | Generated `FEATURE_BY_FEATURE_ACCEPTANCE.csv` with conservative mapping; original disposition preserved in a separate column | 1,488 rows, 0 PARTIAL; 28 PASS / 70 REPLACEMENT_VERIFIED / 221 BLOCKED_EXTERNAL / 737 NOT_TESTED / 432 NOT_APPLICABLE |

No test was weakened to hide a product defect. Full regression after repairs: 1,641 passed, exit 0.

## Campaign 2 additions (2026-11-25)

| # | Item | Repair or action | Retest / evidence |
|---|---|---|---|
| 6 | No new application or test-code defect was repaired by Campaign 2 orchestration | Documentation and evidence reports were added; the conservative final status labels were preserved | Fresh targeted batches: 10/10 workflow, 27/27 integration contract, 17/17 security/reliability; all exit 0 |
| 7 | Previously recorded access-governance frontend defect | Corrected before Campaign 2; no new edit in this campaign | `KNOWN_LIMITATIONS.md`, `MODULE_TEST_RESULTS.md`; re-verified in prior QA and in the fresh workflow/UI wiring batches |
| 8 | Marketing-site FAQ/footer wording | Corrected before publication; no new edit in this campaign | Validator 35 passed / 0 failed; CI build job success; live deployment still blocked |
| 9 | README community-link advisory gap | No edit made; README audit hash preserved | Explicit Star/Fork/PR links are on the published site but not in README; advisory only, no banned engagement practice found |

If any application or test repair is made after this log, the complete backend suite must be rerun and its output recorded before final acceptance is reconsidered.
