# Blocked / not-executed features and scope boundaries

Date: 2026-11-24. This document lists what was **not** executed or not claimed, and why. It is intentionally explicit so that implementation status is never presented as test execution.

## Execution dispositions in the registry

`FEATURE_EXECUTION_REGISTRY.csv` contains one disposition for each of the 1,488 source feature IDs:

| Disposition | Rows | Meaning |
|---|---:|---|
| PASS | 28 | Directly observed behaviour in this QA pass |
| PARTIAL | 932 | Endpoint/route/workflow observed; individual source feature not accepted one-by-one |
| REPLACEMENT_VERIFIED | 70 | Compatible clean-room replacement surface observed; original vendor not contacted |
| NOT_APPLICABLE | 432 | Explicit local-scope boundary: absent, gated, paid/hosted, deployment, research, or no-claim row |
| NOT_TESTED | 26 | No per-feature execution evidence in this pass |
| FAIL | 0 | No observed application failure in the final harness runs |

Rows marked `PARTIAL` or `NOT_TESTED` are not passes. They remain honest gaps in per-feature acceptance.

## Not executed by design

| Area | Why not executed | Evidence |
|---|---|---|
| Campaign send / outbound email, SMS, WhatsApp, push | No real message delivery permitted; local synthetic instance only | `evidence/qa_e2e_log.jsonl` record 17 `NOT_EXECUTED` |
| Hosted email/SMS/push providers and webhooks | External service calls are out of scope and would require credentials | `KNOWN_LIMITATIONS.md` |
| Public document link notification | Local share-link record only, no recipient contacted | W4 records 25-30 |
| Live AI model providers | Agent run is simulated locally and held at approval gate | W8 records 55-59 |
| External experimentation SDK / hosted control plane / billing | Clean-room boundary; no vendor service contacted | W5 and flag-governance notes |
| SSE notification stream | Streaming endpoints deliberately excluded from read-only sweep | `qa_api_harness.py`, `evidence/qa_api_log.jsonl` |
| Mobile installers / native apps | No mobile build or installer was produced in this QA pass | `KNOWN_LIMITATIONS.md` |
| Production PostgreSQL, Docker, hosted deployment | QA used a fresh local SQLite database only | `test-results/migration-check.txt` |
| Real payment, identity provider, OAuth/SSO, live CRM/helpdesk | No external accounts, credentials or personal data were used | `SECURITY_TEST_RESULTS.md` |

## Observed tool-side failures (not application defects)

- 14 `FAIL` rows remain in `evidence/qa_browser_log.jsonl`; every one is a `Screenshot failed ... Connection timed out` record from Chrome's CDP screenshot call. The corresponding route-render checks passed, and all 16 required screenshots were subsequently captured from the desktop with bundled ffmpeg (`evidence/qa_screenshot_log.jsonl`). The log was not rewritten to hide these tool failures.
- Early E2E harness payload errors (422/409) were corrected against the live API contract. The final E2E log has zero FAIL rows; corrections are documented in `END_TO_END_WORKFLOW_RESULTS.md`.

## Genuine application defects found and fixed during this pass

1. **Frontend boot corruption** — `apps/web/app.js` contained a duplicated/corrupted trailing fragment `ener('hashchange', onHashChange); boot();` after the valid listeners. Removed; `node --check` exits 0.
2. **Access governance view mount** — `loadAccessGovernance` used `el.content.innerHTML`, which does not mount into the current view container. Replaced with `renderViewHtml(...)` in both the success and error paths; route re-render passed after correction.

Both fixes are uncommitted working-tree changes. No backend code was altered to influence test results.

## Not claimed anywhere in this QA set

- 100% feature acceptance of the 1,488 source records.
- Real delivery of any campaign, message, document, or notification.
- Production-grade security, performance, scalability, or deployment verification.
- Licensing or code provenance beyond what `docs/FEATURE_PARITY/` already records.
