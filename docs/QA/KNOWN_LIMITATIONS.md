# Known limitations of this QA pass

Date: 2026-11-24. Read this alongside `MASTER_QA_REPORT.md` and `FEATURE_EXECUTION_REGISTRY.csv`.

## Test scope

1. **No 100% feature-acceptance claim.** The 1,488-row registry records 28 PASS, 932 PARTIAL, 70 REPLACEMENT_VERIFIED, 432 NOT_APPLICABLE and 26 NOT_TESTED dispositions. `PARTIAL` means a route/endpoint/workflow was observed, not that the individual source feature was accepted.
2. **Local instance only.** The app ran at `http://127.0.0.1:8765` against a fresh isolated SQLite QA database (`artifacts/final_qa_2026-11-24/qa_db/novara_qa.sqlite3`). No production PostgreSQL, Docker or hosted deployment was used.
3. **Synthetic data only.** Identities are `.invalid` addresses such as `qa.owner@novara.invalid`. No real customer record, token, credential or personal information was used.
4. **No external transactions.** No email, SMS, WhatsApp, push, payment, hosted AI, webhook, OAuth/SSO or provider API call was made. Campaign delivery is explicitly `NOT_EXECUTED`.
5. **No real message delivery.** Outreach drafts, local share links, tickets, workflow triggers and agent runs are local records. Anything that looks like a message is labelled simulated/local.

## API and browser limits

6. The API harness executed 293 checks: 275 GET surface sweeps, 17 POST and 1 PATCH. Streaming endpoints were excluded. A successful GET shows the endpoint exists and responds; it is not acceptance of the underlying feature.
7. Some POST checks expected `409` on rerun and were marked PASS with an explicit note that the synthetic record already existed from an earlier QA run. This is idempotence handling in the harness, not silent failure suppression.
8. The browser log retains 14 CDP screenshot timeout FAIL rows. Route-render checks passed and 16 desktop screenshots were later captured with ffmpeg; the tool failure was not erased from the evidence.
9. Browser testing used a locally launched Chrome attached through a Python CDP driver. The built-in browser's `browser_prepare` refused to attach to the existing profile (`browser_consent_required`), so desktop capture and CDP evaluation were used.
10. Only light theme was exercised, as required. Dark theme was not tested.
11. The UI sweep rendered all 50 configured module routes, but visual rendering is not the same as exercising every form, filter, permission variant and edge case.

## Security limits

12. The 17 security checks are smoke-level negative tests, not a penetration test or formal security audit.
13. A SQL-like search string returning 200 and a script-like string being stored as data do not prove SQL-injection or XSS immunity. No exhaustive payload matrix or browser XSS replay was performed.
14. A 200,000-character field was accepted by one endpoint (201). No conclusion about size limits should be drawn beyond the observed response.
15. Permission checks used two synthetic workspace identities; no enterprise role matrix, SSO, SCIM, or hosted identity provider was exercised.

## Application changes made during QA

16. Two frontend defects were fixed in the working tree so the UI could be tested: a corrupted trailing `ener(...)` fragment in `apps/web/app.js`, and `el.content.innerHTML` in `loadAccessGovernance` replaced by `renderViewHtml(...)`. Both are uncommitted. No backend module was modified to make tests pass.
17. `apps/web/index.html` was temporarily changed to `app.js?qa_cache_bust=20261124b` during browser testing to avoid stale cached JavaScript. This QA-only cache-bust must be reverted before delivery; the change is untracked in Git.

## Media and tooling limits

18. No `ffmpeg`, `ffprobe` or OBS was available on PATH. The bundled `imageio_ffmpeg` binary was used for `gdigrab` capture and encoding; `ffprobe` metadata is therefore from ffmpeg decode output, not a separate probe tool.
19. The two MP4 files are assembled from real screen capture plus generated title/chapter/limitation cards and synthesized SAPI narration. They evidence visible UI behaviour, not per-feature acceptance.
20. Recordings are 1920x1080 at 15 fps. Small text may be hard to read; the screenshots and JSONL logs are the primary evidence.

## Baseline interpretation

21. Prior `T-131` parity accounting described 1,488 rows as covered by an implementation/replacement ledger. It did not mean all rows were executed or passed in a live QA pass. This QA pass deliberately separates implementation status from execution disposition.
22. The phrase "100%" should only be used, if at all, for parity-ledger accounting of NOVARA-local capabilities. It is not a test result and does not cover commercial providers, deployments, mobile installers or live integrations.
