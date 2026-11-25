# NOVARA module test results

Date: 2026-11-24. Instance: local `http://127.0.0.1:8765` with a fresh isolated QA database.
Source of feature IDs: `docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv` (1,488 rows).

## How to read this table

"Disposition" is a **test-execution** disposition from `FEATURE_EXECUTION_REGISTRY.csv`, not an implementation claim.
- `PASS`: the specific behaviour was directly observed in this QA pass.
- `PARTIAL`: the endpoint/route/workflow was observed, but the individual source feature was not accepted one-by-one.
- `REPLACEMENT_VERIFIED`: the row was recorded as a compatible clean-room replacement; the replacement surface was observed. No original vendor service was contacted.
- `NOT_APPLICABLE`: an explicit local-scope boundary (absent, gated, paid/hosted, deployment, or research-only row).
- `NOT_TESTED`: no per-feature execution evidence was recorded.

| Source project | Rows | PASS | PARTIAL | REPLACEMENT_VERIFIED | NOT_APPLICABLE | NOT_TESTED | Observed evidence |
|---|---:|---:|---:|---:|---:|---:|---|
| GrowthBook | 284 | 1 | 132 | 1 | 149 | 1 | Experiment create/observe/analyze, flag-governance route, API sweep |
| Formbricks | 234 | 0 | 154 | 7 | 73 | 0 | Survey/feedback API surface and feedback-studio route |
| Chatwoot | 168 | 6 | 104 | 12 | 45 | 1 | Ticket create/message/note/counts; customer-inbox route |
| Plane | 158 | 7 | 106 | 7 | 32 | 6 | Project/item/status/progress/comment workflow; planning route |
| Papermark | 156 | 1 | 135 | 12 | 7 | 1 | Room, document, share link, link detail; engagement route |
| Mautic | 133 | 7 | 96 | 9 | 20 | 1 | Campaign draft/active/schedule, segment, lifecycle analytics; studio route |
| Novu | 119 | 0 | 75 | 7 | 36 | 1 | Automation create/status, workflow trigger, templates; automation route |
| Meilisearch | 103 | 0 | 55 | 9 | 39 | 0 | Search route and read-only search API surface |
| Sellbird | 80 | 6 | 22 | 6 | 31 | 15 | Intake, contact, notes, lead qualification/conversion, events |
| Marketing Skills | 53 | 0 | 53 | 0 | 0 | 0 | Campaign/marketing read-only API surface and route render |
| **Total** | **1,488** | **28** | **932** | **70** | **432** | **26** | |

Registry totals are generated directly from the CSV; see `../artifacts/final_qa_2026-11-24/_tools/build_registry.py`.

## Module-by-module notes

### Platform, identity and data
- Fresh QA SQLite DB migrated from zero to head `e0f1a2b3c4d5`; `alembic upgrade head` and `alembic check` both exited 0 (`test-results/migration-check.txt`).
- Bootstrap/login/identity, invalid credentials, tampered and missing bearer tokens, cross-workspace denial, and public-form boundary were executed and observed (`evidence/qa_api_log.jsonl`, `evidence/qa_security_log.jsonl`).
- Read-only sweep of 220 module endpoints obtained required query parameters from the live OpenAPI contract; streaming endpoints were deliberately excluded.

### Contacts, leads, sales and activity
- Observed: website-form intake, synthetic contact creation, contact listing/search, lead creation (409 on rerun treated as "already exists"), lead list, transition and conversion, event listing.
- Browser: UI contact creation through the real modal produced a success toast and the record appeared in the list; screenshot `screenshots/17_contact_created.png`.
- No real email, phone number, or external CRM was used.

### Campaigns and marketing
- Observed: draft campaign creation, list, segment creation, status change to active, local schedule, lifecycle analytics.
- **Not executed:** campaign send/dispatch, email/SMS/WhatsApp delivery, provider APIs. Recorded as `NOT_EXECUTED` in `evidence/qa_e2e_log.jsonl` (record 17) and covered in `KNOWN_LIMITATIONS.md` and `BLOCKED_FEATURES.md`.

### Support / customer inbox
- Observed: ticket creation, agent reply, private note, ticket detail, ticket counts.
- Browser: customer inbox route rendered. Help-centre governance, teams, labels, routing and custom attributes were not individually accepted.

### Documents and engagement
- Observed: data-room creation (409 on rerun), document creation, local share link creation, document detail, link detail, room listing.
- Browser: documents and document-engagement routes rendered. No public notification or external link delivery was performed.

### Projects, tasks and work-item planning
- Observed: project creation, work-item creation, `PATCH` status change, project detail, comment, project listing.
- Browser: projects and work-item-planning routes rendered. Planning sub-features were not individually accepted.

### Experimentation and governance
- Observed: local metric and two-variant experiment creation, two observations, local statistical analysis, experiment listing, API-contract read.
- Browser: advanced-experiments, flag-governance and access-governance routes rendered. A genuine frontend defect in access governance was found and fixed, then re-verified (see `MASTER_QA_REPORT.md`).
- No hosted SDK, provider control plane, billing, or external exposure was contacted.

### Automation, notifications and agents
- Observed: automation creation/status/read, notification workflow templates and triggers, local agent creation and simulated run, progress to `awaiting_approval`, human approval, outreach-draft creation/read.
- No external notification channel was consumed; the SSE stream was excluded from the read-only sweep.

### Feedback and surveys
- Survey-related endpoints responded in the read-only API sweep and the feedback-studio/survey-delivery routes rendered. Individual survey response submission was not accepted.

## Defects found during this QA pass

1. `apps/web/app.js` ended with a corrupted trailing fragment `ener('hashchange', onHashChange); boot();` after the valid `window.addEventListener('hashchange', onHashChange); boot();`. This caused a frontend syntax/runtime fault. Removed the fragment; `node --check` exits 0.
2. `loadAccessGovernance` wrote to `el.content.innerHTML`, but the current view renderer mounts content through `renderViewHtml(...)`. Access governance could not display its data. Replaced both `el.content.innerHTML` calls with `renderViewHtml(...)`; route re-render passed after the fix.

Both changes are in the working tree and uncommitted. They were necessary to observe the UI; no backend module was modified to make tests pass.

## Evidence index

- `../artifacts/final_qa_2026-11-24/evidence/qa_api_log.jsonl` — 293 API checks, all PASS.
- `../artifacts/final_qa_2026-11-24/evidence/qa_e2e_log.jsonl` — 61 workflow records (52 PASS, 9 INFO, 0 FAIL).
- `../artifacts/final_qa_2026-11-24/evidence/qa_browser_log.jsonl` — 68 browser observations.
- `../artifacts/final_qa_2026-11-24/evidence/qa_security_log.jsonl` — 17 security checks, all PASS.
- `../artifacts/final_qa_2026-11-24/screenshots/` — 16 successful desktop captures.
- `../artifacts/final_qa_2026-11-24/test-results/` — console logs, migration log, final regression output.
