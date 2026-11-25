# NOVARA final QA report — 2026-11-24

## Executive summary

This is an evidence-based QA pass against the **actual local NOVARA application**, not a claim that every source feature passed. The application was exercised with a fresh isolated SQLite database, synthetic identities and local deterministic adapters. All API, browser, security, workflow, migration, regression and media evidence is stored in `../artifacts/final_qa_2026-11-24/`.

Headline observations:
- 1,488 source feature IDs each received one execution disposition: **28 PASS, 932 PARTIAL, 70 REPLACEMENT_VERIFIED, 432 NOT_APPLICABLE, 26 NOT_TESTED, 0 FAIL**. See `FEATURE_EXECUTION_REGISTRY.csv`.
- 293 API checks observed, all PASS under their recorded expectations; 220 were read-only GET surface sweeps.
- 8 end-to-end workflows executed: 61 records, **52 PASS, 9 informational, 0 FAIL**.
- 17 dedicated negative/security checks, all PASS under their recorded expectations.
- All 50 configured UI module routes rendered after two genuine frontend defects were corrected in the working tree.
- Fresh-database migration and migration check both exited 0 at head `e0f1a2b3c4d5`.
- Two real MP4 deliverables were produced from actual desktop screen recording, with chapter cards and narration.
- No real email, SMS, WhatsApp, payment, provider, hosted AI or external integration was used.
- **No commit, push, tag, deploy, publish or external transaction was performed.**

## Environment and isolation

| Item | Value |
|---|---|
| Application URL | `http://127.0.0.1:8765` |
| QA database | `artifacts/final_qa_2026-11-24/qa_db/novara_qa.sqlite3` |
| Separate regression DB | `artifacts/final_qa_2026-11-24/qa_db/novara_regression_final.sqlite3` |
| Migration-check DB | `artifacts/final_qa_2026-11-24/qa_db/novara_migration_check.sqlite3` |
| Development DB | `D:\NOVARA\novara_dev.sqlite3` — not written during QA |
| Identities | `qa.owner@novara.invalid`, `qa.other@novara.invalid` (synthetic) |
| Chrome profile | `artifacts/final_qa_2026-11-24/qa_chrome_profile_cdp` (local, isolated) |
| Theme | Light only |
| Git HEAD | `73e9f76f6c8dd3360b73f7c5c8abec98726f28f8` |

Data isolation check (`evidence/data_isolation_check.json`): the development DB was last written at 22:27:30 local time, before QA started at about 22:40, and contains zero `.invalid` synthetic markers; the QA DB contains 16 such markers. Conclusion: **PASS** — synthetic QA data did not affect other data.

## Method

1. Derived synthetic payloads from the live `/openapi.json` (988 paths, 816 schemas), saved at `evidence/openapi.json`.
2. Ran a fresh Alembic migration and `alembic check` on an isolated DB.
3. Executed a deterministic API harness: bootstrap/login, module create/read/update flows, explicit negative checks, and a read-only GET sweep with required query parameters. Streaming endpoints were excluded.
4. Executed 8 end-to-end workflows through the same live API using synthetic records.
5. Drove the visible Chrome UI through a local CDP driver: signed in, rendered all 50 module routes, created a contact through the real modal, swept JavaScript errors, and captured light-theme computed styles.
6. Ran dedicated security/negative checks for authentication, authorization, cross-workspace isolation, validation and hostile-looking inputs.
7. Ran the full automated regression suite on a separate fresh QA DB.
8. Recorded the live UI with bundled ffmpeg `gdigrab`, then assembled two MP4 deliverables with generated chapter cards and SAPI narration. Recorded limitations in both the videos and this document set.

## Observed results

### API
- 293 records in `evidence/qa_api_log.jsonl`: 275 GET, 17 POST, 1 PATCH; all PASS under their expected status sets.
- Some expected outcomes are `409` on rerun with an explicit note that the synthetic record already exists; these are idempotence observations, not hidden failures.
- Cross-workspace denial, tampered token, missing token, invalid login and duplicate contact were observed as expected.

### Browser
- 50/50 module routes rendered with non-empty content and no error state (`evidence/ui_routes.json`, `evidence/qa_browser_log.jsonl`).
- UI contact creation through the real modal produced a success toast and the record appeared in the list.
- JavaScript error sweep empty; light theme computed background `rgb(245, 247, 245)`.
- 14 `FAIL` rows remain in the browser log: every one is a CDP screenshot timeout, not an application failure. All 16 required screenshots were subsequently captured successfully via desktop `gdigrab` (`evidence/qa_screenshot_log.jsonl`).

### End-to-end workflows
See `END_TO_END_WORKFLOW_RESULTS.md`. All 8 workflows have observed evidence. Campaign delivery, external notifications and hosted AI calls were explicitly not executed.

### Security
See `SECURITY_TEST_RESULTS.md`. 17/17 checks matched expectations. These are smoke-level negative checks, not a penetration test.

### Regression
The authoritative clean full-suite artifact is `docs/evidence/t131-fullsuite-clean-20261124.txt`: `1641 passed, 4 warnings in 1395.31s (0:23:15)`, with exit code 0 recorded in `docs/evidence/t131-fullsuite-clean-exit.txt`. It was run on a fresh isolated QA database configured through `NOVARA_DB_PATH`. The capture at `../artifacts/final_qa_2026-11-24/test-results/final-regression.txt` is an incomplete UTF-16 progress log (it stops at 57%) and is **not** used as the recorded result; see the "Regression result" section below.

## Genuine defects found and corrected

1. `apps/web/app.js` ended with a corrupted duplicate fragment `ener('hashchange', onHashChange); boot();` after the valid listener registration. It prevented the frontend from booting correctly. The fragment was removed; `node --check` exits 0.
2. `loadAccessGovernance` used `el.content.innerHTML`, but the current view renderer mounts via `renderViewHtml(...)`. The access-governance page could not display data. Both success and error paths were changed to `renderViewHtml(...)`; the route rendered successfully after correction.

These are uncommitted working-tree changes and are the only application modifications made for this QA pass. No backend module was changed to make tests pass.

`apps/web/index.html` was temporarily cache-busted to `app.js?qa_cache_bust=20261124b` during UI testing and has been restored to `app.js`. It remains untracked in Git, as it was before this QA pass.

## Honesty statement

- A passing API check means the endpoint responded as expected; it does not prove the underlying feature is fully implemented.
- A rendered route is not per-feature acceptance.
- `PARTIAL` and `NOT_TESTED` dispositions are not passes.
- No recording was fabricated; both MP4 files derive from real desktop screen capture.
- No delivery, provider call or external transaction was simulated as if real; anything of that kind is labelled local/simulated/`NOT_EXECUTED`.
- The 100% figure used in parity ledgers refers only to NOVARA-local capability accounting; it is not a test result.

## Deliverables

| Path | Contents |
|---|---|
| `FEATURE_EXECUTION_REGISTRY.csv` | 1,488 rows, one disposition each |
| `MASTER_QA_REPORT.md` | This report |
| `MODULE_TEST_RESULTS.md` | Per-source-project results and disposition counts |
| `SECURITY_TEST_RESULTS.md` | 17 negative/security checks |
| `END_TO_END_WORKFLOW_RESULTS.md` | 8 workflow results and boundaries |
| `BLOCKED_FEATURES.md` | Not-executed, not-applicable and tool-side failures |
| `VIDEO_CHAPTER_INDEX.md` | Chapter timings for both MP4 files |
| `KNOWN_LIMITATIONS.md` | Limits of scope and interpretation |
| `../artifacts/final_qa_2026-11-24/videos/NOVARA_Complete_QA_Walkthrough.mp4` | 00:03:16, H.264 + AAC, 1920x1080 |
| `../artifacts/final_qa_2026-11-24/videos/NOVARA_Product_Demo_1.0.mp4` | 00:01:40, H.264 + AAC, 1920x1080 |
| `../artifacts/final_qa_2026-11-24/evidence/` | JSONL logs, OpenAPI contract, screenshots, video metadata, isolation check |
| `../artifacts/final_qa_2026-11-24/test-results/` | Console logs, migration log, final regression output |
| `../artifacts/final_qa_2026-11-24/reports/` | Copies of all QA documents |

## Regression result

**Completed.** `1641 passed, 4 warnings in 1395.31s (0:23:15)`, exit code 0, with zero failures. Authoritative evidence: `docs/evidence/t131-fullsuite-clean-20261124.txt` and `docs/evidence/t131-fullsuite-clean-exit.txt`, produced on a fresh isolated QA database via `NOVARA_DB_PATH`. The `final-regression.txt` capture in this artifact folder is truncated (UTF-16, stops at 57%) and is not used as the recorded result.
