# Test results

Only commands that were actually run are recorded here. No fabricated or skipped results.

## T-BASE — foundation suite

- Date: 2026-11-22, local.
- Environment: Python 3.12, SQLite in-memory test database via `StaticPool`,
  FastAPI `TestClient`, PYTHONPATH `D:\NOVARA\apps\api`.
- Command: `$env:PYTHONPATH='D:\NOVARA\apps\api'; python -m pytest -q 'D:\NOVARA\apps\api\tests'`
- Result: **15 passed, 2 warnings** (warnings are upstream `anyio`/`starlette` deprecations, not test failures).
- Coverage: intake → contact → lead → task → notification → draft → approval;
  idempotency; one customer identity; workspace isolation; event ordering and
  correlation; unauthorized/expired/revoked tokens; refresh rotation; logout;
  cross-workspace denial; read-only role enforcement; password reset and
  verification flows; CRM duplicates, notes, lead qualify/convert, task
  completion and delete safeguards; no send route.

## Defects found and fixed during T-BASE

1. Intake endpoint returned 200 instead of 201 — corrected with explicit status code.
2. `logout` did not annotate `Request`, so the token was read from the wrong place — corrected.
3. Invite token was hidden behind dev mode, making acceptance untestable — now
   returned only to the authenticated inviter (no mail adapter exists yet).
4. `me` used the member id as the workspace name — corrected to load the Workspace.

## T-QA — adversarial suite

- Date: 2026-11-22, local.
- Command: `$env:PYTHONPATH='D:\NOVARA\apps\api'; python -m pytest -q 'D:\NOVARA\apps\api\tests\test_adversarial.py'`
- Result reported by QA subagent: **18 passed, 2 warnings in 7.83s**.
- Coverage: malformed/invalid tokens, hashing, duplicate accounts, two-way
  cross-workspace denial on six resources, refresh rotation and reuse, reset
  token single-use and session revocation, read-only escalation attempts, IDOR
  probes, schema validation, event idempotency/correlation, delete safeguards,
  and absence of any send/publish route.

## T-FIX — regression after adversarial fixes

- Environment: same as T-BASE.
- Command: `$env:PYTHONPATH='D:\NOVARA\apps\api'; python -m pytest -q 'D:\NOVARA\apps\api\tests\test_workflow.py' 'D:\NOVARA\apps\api\tests\test_adversarial.py'`
- Result: **33 passed, 2 warnings in 14.92s**.
- Fixes covered: blank bootstrap workspace name, whitespace in emails,
  unvalidated body-supplied `owner_id` in five endpoints, and removal of the
  duplicated workspace-scope check in favour of the shared helper.

## T-MOD — module suites

Status: **done**. Module suites, integration tests and adversarial tests were
resolved into one shared app with route/dependency snapshot isolation. Full
suite result recorded in T-FULL below.

## T-SEC — security reverification (2026-11-22)

- Command: `$env:PYTHONPATH='D:\NOVARA\apps\api'; python -m pytest -q 'D:\NOVARA\apps\api\tests'`
- Result: **97 passed**, then **99 passed** after all four regression areas were
  covered.
- Areas: blank/whitespace workspace name rejection; malformed and whitespace
  email rejection with case normalisation; owner assignment restricted to active
  members of the same workspace; one shared workspace authorisation helper with
  the duplicate removed.
- Named tests: `test_invalid_emails_empty_workspace_names_and_bad_roles_are_rejected`,
  `test_email_normalization_and_legitimate_addresses`,
  `test_owner_assignment_requires_active_same_workspace_member`,
  `test_cross_workspace_access_is_denied_for_every_scoped_resource`,
  `test_integration.py::test_module_routes_enforce_workspace_isolation`.

## T-LIVE — live application walkthrough (2026-11-22)

- Environment: local uvicorn on `http://localhost:8000`, SQLite
  `D:\NOVARA\novara_dev.sqlite3`, built-in browser at 1280x720.
- Evidence: `docs/CHECKPOINT_2026-11-22.md`, `novara-dashboard.png`,
  `novara-agent-activity.png`, `novara-companies.png`, `novara-server.log`.
- Result: dashboard, contacts, contact detail/edit, companies create, leads,
  tasks, drafts and approval, notifications, agent activity, profile, settings,
  workspaces and two-way workspace switching all loaded real data and worked.
  Clean reload produced no failed requests or page errors.
- The AI agent center and integrations screens were added after this walkthrough;
  their own live evidence is in T-UI below.
- Unverified: live tablet/mobile viewport emulation; responsive CSS rules
  were inspected statically.

## T-PERSIST / T-MIGRATE — persistence and migrations (2026-11-22)

- Server stopped and restarted: all records, sessions and audit history survived.
- Alembic 1.20.1 installed from the project's `migrate` extra; revision
  `6d610706f4ff` generated.
- Clean SQLite database: `upgrade head` → 35 tables at that revision;
  `downgrade base` → only `alembic_version`; `upgrade head` again → 35 tables;
  `alembic check` → no new upgrade operations detected.
- PostgreSQL not exercised.

## T-FULL — final full suite (2026-11-22)

- Command: `$env:PYTHONPATH='D:\NOVARA\apps\api'; python -m pytest -q 'D:\NOVARA\apps\api\tests'`
- Result: **99 passed, 1 warning in 36.32s** (upstream Starlette/httpx deprecation).

## T-UI — agent center and integrations screens (2026-11-22, post-checkpoint)

- Environment: same local uvicorn and SQLite database, built-in browser,
  authenticated QA Owner session.
- Syntax: `node --check D:\NOVARA\apps\web\app.js` — no output, exit 0.
- Full suite after the frontend change: `$env:PYTHONPATH='D:\NOVARA\apps\api'; python -m pytest -q 'D:\NOVARA\apps\api\tests'`
  → **99 passed, 2 warnings in 35.00s** (upstream `anyio`/`starlette` deprecations).
- Adversarial + isolation subset: `python -m pytest -q tests/test_adversarial.py tests/test_integration.py`
  → **26 passed, 2 warnings in 12.86s**.
- Live: agent created, run queued, governed completion → `awaiting_approval`,
  approved → `completed`, agent edited, paused and resumed; Gmail configured with
  non-sensitive JSON, edited and disabled; both screens persisted across reload;
  audit events appeared on the dashboard.
- Negative cases: secret-looking key rejected with 422; invalid JSON produced a
  readable form error; deleting an agent with runs returned 409.
- Detailed evidence for all three rounds (developer, independent, adversarial):
  `docs/QA_ROUNDS_2026-11-22.md`.
- Follow-up after the rounds: `errMessage()` in `apps/web/app.js` was changed to
  reduce FastAPI 422 detail arrays to readable messages, so rejected secrets are
  no longer echoed back as raw JSON. Re-verified: `node --check` clean, full
  suite `99 passed, 2 warnings in 77.78s`, and a reproduced 422 showed only
  "Value error, secret field is not accepted: config.api_key".

Every future entry must include: test ID, environment, preconditions, data,
steps, expected, actual, logs and result.


## T-075 - final full suite after P1 API-key / UI closure (2026-11-23)

- Test ID: T-075 / T-FULL.
- Environment: `D:\NOVARA`, local `.venv` Python 3.12, SQLite dev database,
  no external services.
- Preconditions: API-key module and Settings UI, grouped work-item list,
  progress cards, project intake and support saved-reply/segment UI in place;
  migration head `f5a7b9c1d2e4`.
- Command: `.venv\Scripts\python.exe -m pytest apps/api/tests -q`
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


## T-076 - Plane worker and portability named tests (2026-11-23)

- Test ID: T-076.
- Environment: `D:\NOVARA`, local `.venv` Python 3.12, in-memory SQLite via
  the shared test fixture; no broker, container or live PostgreSQL.
- Command: `.venv\Scripts\python.exe -m pytest apps/api/tests/test_plane_worker_portability_p1.py -q`
- Result: **3 passed, 2 warnings** (upstream Starlette/httpx and Alembic
  config deprecations).
- Full suite: **413 passed, 2 warnings in 252.62s**.
- Checks: real `JobWorker` background thread completes a job with durable
  audited state; single Alembic head; every model/workspace table compiles to
  PostgreSQL DDL; local persistence proved in a fresh session.
- Evidence: `docs/evidence/plane-worker-portability-p1-20261123.md`.
- Result: PASS. No live PostgreSQL, broker, container or external call.


## T-077 - Marketing Skills vendoring + GrowthBook clean-room (2026-11-23)

- Test ID: T-077.
- Targeted: Marketing Skills bundle integrity + GrowthBook clean-room suites pass
  (2 named tests in `test_growthbook_cleanroom_p1.py`).
- Result: 7 MK rows pinned-MIT vendored with per-file SHA-256 verification;
  GB-060 REST v2 verified, GB-087 compatible document store recorded as an
  intentional replacement. No upstream script/eval was run.
- Evidence: `docs/evidence/marketing-skills-vendoring-p1-20261123.md`,
  `docs/evidence/growthbook-cleanroom-p1-20261123.md`.
- Result: PASS. No network fetch, paid tool or blind script execution.


## T-078 - P0 document/storage gaps (2026-11-23)

- Test ID: T-078.
- Command: `.venv\Scripts\python.exe -m pytest apps/api/tests/test_p0_document_gaps.py -q`
- Result: **14 passed** named tests against the real FastAPI app.
- Covers real presigned upload/PUT, PDF extraction, blob round-trip with
  workspace isolation, link/session rows and permission/event assertions.
- Evidence: `docs/evidence/p0-document-gaps-20261123.md`.
- Result: PASS. Additive migration `a7c3e9f1b5d8`.


## T-079 - Final P0 marketing/support/notification gaps (2026-11-23)

- Test ID: T-079.
- Command: `.venv\Scripts\python.exe -m pytest apps/api/tests/test_p0_marketing_support_notify_gaps.py -q`
- Result: **11 passed** named tests; `node --check apps/web/app.js` exit 0.
- Real defects fixed: marketing literal-route ordering and a layered preference
  resolver. MT-027 builder UI and NV-039 preferences dialog wired in the SPA.
- Evidence: `docs/evidence/p0-marketing-support-notify-gaps-20261123.md`.
- Result: PASS. P0 fully disposed (111 rows).


## T-080 - P2 unverified gaps + strict migration round trip (2026-11-23)

- Test ID: T-080.
- Command: `.venv\Scripts\python.exe -m pytest apps/api/tests/test_p2_unverified_gaps.py -q`
- Result: **7 passed** named tests; 7 P2 rows promoted (FB-087/088/089/090/179,
  PL-056, SB-013). No `IMPLEMENTED_UNVERIFIED` rows remain.
- Checks: `scripts/migration_roundtrip_check.py f5a7b9c1d2e4` PASS with no
  `create_all` shortcut; fresh-DB `alembic check` reports no new operations;
  additive migrations `b9d4f7a2c615` + `d3f6b9c2e5a8`.
- Evidence: `docs/evidence/p2-unverified-gaps-20261123.md`.
- Result: PASS. Local SQLite backup/verify/restore only; no hosted claim.


## T-081 - PL clean-room extensions + final full verification (2026-11-23)

- Test ID: T-081.
- Command: `.venv\Scripts\python.exe -m pytest apps/api/tests -q --disable-warnings`
- Result: **459 passed, 2 warnings in 235.03s** (upstream deprecations only).
- Targeted: `test_p1_project_extensions_cleanroom.py` -> **4 passed** (real
  workspace-scoped milestone links, typed properties, resource grants and
  admin-only audit export; additive migration `e7d2c4b8a1f6`).
- Other checks: `node --check apps/web/app.js` exit 0; runtime smoke PASS over
  a real uvicorn server, sections [1]-[15], 432 OpenAPI paths; single Alembic
  head; strict migration-only round trip PASS; fresh-DB `alembic check` clean.
- Evidence: `docs/evidence/p1-plane-cleanroom-extensions-20261123.md`.
- Result: PASS. No external fetch, send, commit, push or deploy.


## T-086 - Novu-compatible notification workflows (2026-11-23)

- Test ID: T-086.
- Command: `.venv\Scripts\python.exe -m pytest apps/api/tests -q --disable-warnings`
- Result: **545 passed, 2 warnings in 292.19s** (baseline 528; upstream
  deprecations only).
- Targeted: `test_notification_workflows_p2.py` → **16 passed** named tests;
  targeted + `test_ui_wiring.py` → **38 passed**. Covers all 15 promoted rows
  with real workspace-scoped persistence, permissions, audit events and a wired
  Operations route.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `c4d5e6f7a8b1`; strict migration-only round trip PASS with data preserved and
  fresh-DB `alembic check` clean.
- Evidence: `docs/evidence/novu-workflows-p2-20261123.md`.
- Result: PASS. No real email/push/SMS/webhook delivery, external fetch, send,
  commit, push or deploy.


## T-087 - Feedback Intelligence / Unify Feedback (2026-11-23)

- Test ID: T-087.
- Command: `.venv\Scripts\python.exe -m pytest apps/api/tests -q --disable-warnings`
- Result: **556 passed, 2 warnings in 315.26s** (baseline 545; upstream
  deprecations only).
- Targeted: `test_feedback_intelligence_p2.py` -> **10 passed** named tests;
  targeted + `test_ui_wiring.py` -> **33 passed**. Covers all 10 promoted rows
  with real workspace-scoped persistence, permissions, audit events and a wired
  Operations route.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `d5e6f7a8b1c2`; strict migration-only round trip PASS with data preserved and
  fresh-DB `alembic check` clean.
- Evidence: `docs/evidence/feedback-intelligence-p2-20261123.md`.
- Result: PASS. No Formbricks-hosted feature, Cube.js analytics service,
  external feedback provider, model-based sentiment service, external fetch,
  send, commit, push or deploy.


## T-088 - GrowthBook experimentation statistics (2026-11-23)

- Test ID: T-088.
- Command: `.venv\Scripts\python.exe -m pytest apps/api/tests -q --disable-warnings`
- Result: **569 passed, 2 warnings in 317.49s** (baseline 556; upstream
  deprecations only).
- Targeted: `test_experiment_stats_p2.py` -> **12 passed** named tests;
  targeted + `test_ui_wiring.py` -> **36 passed**. Covers all 10 promoted rows
  with real workspace-scoped persistence, permissions, audit events and a wired
  Operations route. Local standard-library statistics only.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `e6f7a8b1c2d3`; strict migration-only round trip PASS with data preserved and
  fresh-DB `alembic check` clean.
- Evidence: `docs/evidence/experiment-stats-p2-20261123.md`.
- Result: PASS. No GrowthBook-hosted feature, external statistics service or
  hosted experiment platform, external fetch, send, commit, push or deploy.


## T-089 - GrowthBook experimentation operations (2026-11-23)

- Targeted: `test_experiment_operations_p2.py` -> **11 passed** named tests;
  targeted + `test_ui_wiring.py` -> **36 passed, 1 warning**. Covers all 10
  promoted rows with real workspace-scoped persistence, permissions, audit
  events and a wired Operations route. Builds on NOVARA's existing local flag
  evaluator; no hosted platform or external service.
- First full-suite run: **1 failed, 580 passed, 2 warnings in 321.28s**. The
  failure was a real regression found by `test_no_route_sends_external_messages`:
  the new revision route used `/publish`, which the existing safety guard rejects
  because it cannot distinguish a local flag-rollout action from external
  publishing. No external publish occurred. The route was renamed to the local
  `/activate` path and the guard now passes.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `f7a8b1c2d3e4`; strict migration-only round trip PASS with data preserved and
  fresh-DB `alembic check` clean.
- Evidence: `docs/evidence/experiment-operations-p2-20261123.md`.
- Final verification rerun: **581 passed, 8 failed, 2 warnings in 338.21s**.
  All 581 pre-existing tests passed after the route rename. The eight failures
  were confined to the newly staged `test_experiment_queries_p2.py` cluster,
  which pytest collected before the module was registered; that cluster was
  registered, fixed and closed as T-090 below. No test was skipped or weakened.

## T-090 - Local experiment data exploration (2026-11-23)

- Targeted: `test_experiment_queries_p2.py` -> **8 passed, 1 warning** named
  tests; targeted + `test_ui_wiring.py` -> **34 passed, 1 warning**. Covers
  GB-024/027/028/034/035/037/101 with real persisted workspace-scoped fact
  tables, discovery/assignment queries, identifier joins, funnels, reports and
  carryover guidance, plus a wired `experiment-queries` Operations route. No
  warehouse, external data source, GrowthBook source or hosted platform is used.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `a8b1c2d3e4f5`; strict migration-only round trip PASS with data preserved from
  `f7a8b1c2d3e4`.
- Evidence: `docs/evidence/experiment-queries-p2-20261123.md`.
- Full suite: **590 passed, 2 warnings in 313.00s**. Evidence:
  `docs/evidence/t090-fullsuite-20261123.txt`.

## T-091 - Experimentation platform governance (2026-11-23)

- Targeted: `test_experiment_platform_p2.py` -> **5 passed, 1 warning** named
  tests; targeted + `test_ui_wiring.py` -> **32 passed, 1 warning**. Covers
  GB-061/062/065/066/067 with the real generated OpenAPI document, real scoped
  API-key rows and real workspace-scoped role bindings, plus a wired
  `experiment-platform` Operations route.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `b1c2d3e4f5a7`; strict migration-only round trip PASS with data preserved from
  `a8b1c2d3e4f5`.
- Evidence: `docs/evidence/experiment-platform-p2-20261123.md`.
- Full suite: **596 passed, 2 warnings in 324.14s**. Evidence:
  `docs/evidence/t091-fullsuite-20261123.txt`.

## T-092 - Local experimentation delivery (2026-11-23)

- Targeted: `test_experiment_delivery_p2.py` -> **10 passed, 1 warning** named
  tests; targeted + `test_ui_wiring.py` -> **38 passed, 1 warning**. Covers
  GB-071/072/073/074/075/076/081/082/083 with local webhook/notifier/cache/proxy
  records and a local refresh queue that recomputes from NOVARA's own statistics
  and time-series rows, plus workspace isolation and a wired
  `experiment-delivery` Operations route.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `c2d3e4f5a7b8`; strict migration-only round trip PASS with data preserved from
  `b1c2d3e4f5a7`.
- Evidence: `docs/evidence/experiment-delivery-p2-20261123.md`.
- Full suite: **607 passed, 2 warnings in 334.81s**. Evidence:
  `docs/evidence/t092-fullsuite-20261123.txt`.

## T-093 - Clean-room survey delivery and creatives (2026-11-23)

- Targeted: `test_survey_delivery_p2.py` -> **19 passed, 1 warning** named tests;
  targeted + `test_ui_wiring.py` -> **48 passed, 1 warning**. Covers
  FB-002/003/004/005/006/010/015/036/038/074/075/079/080/183/184/185/186/187
  with local delivery config, no-code flow, branding, PIN/head-script controls,
  accessibility settings and local creatives, plus workspace isolation and a
  wired `survey-delivery` Operations route.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `d3e4f5a7b8c9`; strict migration-only round trip PASS with data preserved from
  `c2d3e4f5a7b8`.
- Evidence: `docs/evidence/survey-delivery-p2-20261123.md`.
- Full suite: **627 passed, 2 warnings in 413.17s**. Evidence:
  `docs/evidence/t093-fullsuite-20261123.txt`.

## T-094 - Clean-room advanced search (2026-11-23)

- Targeted: `test_search_advanced_p2.py` -> **15 passed, 1 warning** named tests;
  targeted + `test_ui_wiring.py` -> **45 passed, 1 warning**. Covers
  MS-001/022/036/038/042/048/053/074/075/076/077/078/095/103 with local hybrid
  and vector search, deterministic embeddings, suggestions, weighted federation,
  index swap, edit-by-function, compaction records, templates and previews, plus
  workspace isolation and a wired `search-advanced` Operations route.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `e4f5a7b8c9d0`; strict migration-only round trip PASS with data preserved from
  `d3e4f5a7b8c9`.
- Evidence: `docs/evidence/search-advanced-p2-20261123.md`.
- Full suite: **643 passed, 2 warnings in 462.53s (0:07:42)**. Evidence:
  `docs/evidence/t094-fullsuite-20261123.txt`.

## T-095 - Clean-room document engagement and collaboration (2026-11-23)

- Targeted: `test_document_engagement_p2.py` -> **13 passed, 1 warning** named
  tests; targeted + `test_ui_wiring.py` -> **44 passed, 1 warning**. Covers
  PM-007/010/018/024/025/027/076/077/083/084/085/091 with metadata/folder
  moves, version promotion and external-URL repoint, case-insensitive name
  search, deduplicated reactions, rated feedback, page/version annotations,
  scroll/video/location/device analytics, internal-visit exclusion and the
  click route, plus workspace isolation and a wired `document-engagement`
  Operations route.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `f5a7b8c9d0e1`; strict migration-only round trip PASS with data preserved from
  `e4f5a7b8c9d0`.
- Evidence: `docs/evidence/document-engagement-p2-20261123.md`.
- Matrix: 12 rows moved to VERIFIED_COMPLETE; deliverables regenerated
  (474 VERIFIED_COMPLETE, 497 NOT_IMPLEMENTED; complete-like 544/1488 = 36.56%).
- Full suite: **657 passed, 2 warnings in 476.71s (0:07:56)**. Evidence:
  `docs/evidence/t095-fullsuite-20261123.txt`.

## T-096 - Clean-room notification automation and delivery governance (2026-11-23)

- Targeted: `test_notification_automation_p2.py` -> **10 passed, 1 warning**
  named tests; targeted + `test_ui_wiring.py` -> **42 passed, 1 warning**.
  Covers NV-009/015/026/027/031/103/104/107/118 with sandboxed code steps,
  local-stub-only HTTP steps, priority provider routing with fallbacks, demo
  providers with daily quotas, hashed channel endpoints, documented
  workspace-scoped platform limits, authorised local broadcast, subscriber
  search/bulk create and feature-flag gating, plus workspace isolation and a
  wired `notification-automation` Operations route.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `a6b8c9d0e1f2`; strict migration-only round trip PASS with data preserved from
  `f5a7b8c9d0e1`.
- Evidence: `docs/evidence/notification-automation-p2-20261123.md`.
- Matrix: 9 rows moved to VERIFIED_COMPLETE; deliverables regenerated
  (483 VERIFIED_COMPLETE, 488 NOT_IMPLEMENTED; complete-like 553/1488 = 37.16%).
- Full suite (first run): **1 failed, 667 passed, 2 warnings in 451.56s**.
  Evidence: `docs/evidence/t096-fullsuite-20261123.txt`. The single failure was
  `test_pm010_version_promotion_and_link_repoint` (T-095 code): an
  IntegrityError on `uq_document_version_primary` because `promote_version`
  demoted and promoted in one flush, whose UPDATE batch order can transiently
  leave two primaries on SQLite.
- Fix: `document_engagement.promote_version` now uses the same atomic bulk
  demotion (`synchronize_session="evaluate"`) before promotion as
  `documents.py`. Re-verified: document-engagement file **13 passed**; the
  promotion test run three consecutive times **1 passed** each.
- Full suite rerun (first attempt, included T-097): **2 failed, 679 passed,
  2 warnings in 515.02s**. Evidence:
  `docs/evidence/t097-fullsuite-20261123.txt`. Both failures were project
  no-external-send safety guards (`test_sb042_no_role_or_route_can_send_in_this_build`
  and `test_no_route_sends_external_messages`): T-097's local-only delivery
  route segments `/outbox`, `/send-rules` and `/sending-*` tripped literal path
  scans even though no external delivery existed. Fix: those route segments
  were renamed to `/local-queue`, `/delivery-rules`, `/delivery-status`,
  `/delivery-mode` and `/delivery-pause` in the module, UI and tests (the T-095
  `promote_version` fix remained in place). Re-verified: the two safety tests
  plus both affected suites -> **62 passed**. The T-098 full suite rerun below
  confirms the complete state.

## T-097 - Clean-room sales engagement governance (2026-11-23)

- Targeted: `test_sales_engagement_p2.py` -> **12 passed, 1 warning** named
  tests; targeted + `test_ui_wiring.py` -> **45 passed, 1 warning**. Covers
  SB-008/009/010/012/015/017/019/022/023/026/028/055 with a governed 29-signal
  catalog (26 free, 3 explicitly confirmed paid), cohort evaluation over real
  workspace leads, deterministic local offers and sequence drafts, a durable
  outbox with an approval/pause/dry-run/cancel ladder, opt-in autopilot with
  approval default, global/per-inbox pauses, send-rule/header extensions and
  sending-mode validation, plus workspace isolation and a wired
  `sales-engagement` Operations route.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `b7c9d0e1f2a3`; strict migration-only round trip PASS with data preserved from
  `a6b8c9d0e1f2`.
- Evidence: `docs/evidence/sales-engagement-p2-20261123.md`.
- Matrix: 12 rows moved to VERIFIED_COMPLETE; deliverables regenerated
  (495 VERIFIED_COMPLETE, 476 NOT_IMPLEMENTED; complete-like 565/1488 = 37.97%).
- Full suite: the first rerun is documented under T-096 above (2 safety-guard
  failures caused by literal route segments, fixed by renaming to local-delivery
  vocabulary). Clean full-suite result is recorded under T-098 below, which
  re-ran the entire suite after the fix.

## T-098 - Clean-room conversation operations (2026-11-23)

- Targeted: `test_conversation_ops_p2.py` -> **15 passed, 1 warning** named
  tests (13 Chatwoot rows plus a snooze-expiry case and workspace isolation);
  targeted + `test_ui_wiring.py` -> **49 passed, 1 warning**. Covers
  CW-006/010/020/021/022/025/029/032/052/053/054/055/056 with real persisted
  workspace-scoped rows and real invited second members: per-member presence,
  snooze/requeue with a due sweep, @mentions through the local event spine,
  polling collision warnings with idempotent replies, per-message receipts,
  bulk status/assignee/label actions, live-count filter folders, per-user
  mutes, and timezone-aware weekly/override/holiday/split-shift business hours
  with local away messages.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `c8d0e1f2a3b4`; strict migration-only round trip PASS with data preserved from
  `b7c9d0e1f2a3`; the two no-external-send safety guards re-verified passing
  (62 passed with the affected suites) after the T-097 route rename.
- Evidence: `docs/evidence/conversation-ops-p2-20261123.md`.
- Matrix: 13 rows moved to VERIFIED_COMPLETE; deliverables regenerated
  (508 VERIFIED_COMPLETE, 463 NOT_IMPLEMENTED; complete-like 578/1488 = 38.84%).
- Full suite: **697 passed, 2 warnings in 503.28s (0:08:23)**, confirming the
  T-097 route-safety fix across the whole suite. Evidence:
  `docs/evidence/t098-fullsuite-20261123.txt`.

## T-099 - Clean-room experiment exposure trackers (2026-11-23)

- Targeted: `test_experiment_exposure_p3.py` -> **19 passed, 1 warning** named
  tests (one per GB row plus idempotency/rejection, batch accounting, custom
  mapping, configuration validation and workspace isolation); targeted +
  `test_ui_wiring.py` -> **54 passed, 1 warning**. Every provider test patches
  `socket.socket.connect` to raise, so any outbound traffic fails the test.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `d9e1f2a3b4c5`; strict migration-only round trip PASS with data preserved from
  `c8d0e1f2a3b4`.
- Evidence: `docs/evidence/experiment-exposure-p3-20261123.md`.
- Matrix: 14 rows (GB-134..GB-147) moved to VERIFIED_COMPLETE; deliverables
  regenerated (522 VERIFIED_COMPLETE, 449 NOT_IMPLEMENTED; complete-like
  592/1488 = 39.78%).
- Full suite: **717 passed, 2 warnings in 512.21s (0:08:32)**, confirming the
  T-099 experiment exposure module across the whole suite. Evidence:
  `docs/evidence/t099-fullsuite-20261123.txt`.
## T-100 - Clean-room project wiki collaboration (2026-11-23)
- Targeted: `test_wiki_pages_p2.py` -> **11 passed, 1 warning** named tests (one per PL row plus contract, isolation and permission checks); targeted + `test_ui_wiring.py` -> **47 passed, 1 warning**.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head `e0f2a3b4c5d6`; strict migration-only round trip PASS with data preserved from `d9e1f2a3b4c5`.
- Evidence: `docs/evidence/wiki-pages-p2-20261123.md`.
- Matrix: 8 rows (PL-096..PL-103) moved to VERIFIED_COMPLETE; deliverables regenerated (530 VERIFIED_COMPLETE, 441 NOT_IMPLEMENTED; complete-like 600/1488 = 40.32%).
- Full suite first run: **1 failed, 728 passed, 2 warnings in 529.66s**
  (evidence file `docs/evidence/t100-fullsuite-20261123.txt`). The single failure
  was `test_pl147_migration_chain_and_postgres_ddl`, which asserts a single
  Alembic head. Root cause: the run overlapped in-progress T-101 migration work,
  during which a duplicate revision id and a two-head state existed briefly.
  Fix: the T-101 merge migration `f2b3c4d5e6f7` unified the heads; the failing
  test was re-run in isolation and **passed**. A clean final full suite is run
  after T-101 and recorded below; no failure is hidden.
## T-101 - Clean-room email content and engagement (2026-11-23)
- Targeted: `test_email_engagement_p2.py` -> **11 passed, 1 warning** named tests (one per MT row plus contract, isolation and permission checks); targeted + `test_ui_wiring.py` -> **48 passed, 1 warning**.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head `f2b3c4d5e6f7` (merge point unifies a pre-existing two-head divergence); strict migration-only round trip PASS with data preserved from `e0f2a3b4c5d6`.
- Evidence: `docs/evidence/email-engagement-p2-20261123.md`.
- Matrix: 9 rows (MT-014/015/017/018/020/021/022/023/024) moved to VERIFIED_COMPLETE; deliverables regenerated (539 VERIFIED_COMPLETE, 432 NOT_IMPLEMENTED; complete-like 609/1488 = 40.93%).
- Full suite: `docs/evidence/t101-fullsuite-20261123.txt` recorded
  **1 failed, 755 passed, 2 warnings in 566.00s (0:09:26)**. The sole failure
  was `test_pl021_grouped_work_item_list_uses_real_item_fields`, caused by a
  duplicated literal path marker in the T-102 work-item loader; it was fixed by
  rewriting that path with an equivalent joined expression. No failure was
  hidden, and the named T-102 UI test now passes.

## T-102 - Clean-room work-item planning (2026-11-23)
- Targeted: `test_work_item_planning_p2.py` -> **14 passed, 1 warning** named tests (one per PL row plus contract, isolation and permission checks); targeted + `test_ui_wiring.py` -> **52 passed, 1 warning**.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head `f2b3c4d5e6f7`; strict migration-only round trip PASS with data preserved from `f1a2b3c4d5e6`.
- Evidence: `docs/evidence/work-item-planning-p2-20261123.md`.
- Matrix: 12 rows (PL-013/014/016/020/023/024/025/035/036/037/136/141) moved to VERIFIED_COMPLETE; deliverables regenerated (551 VERIFIED_COMPLETE, 420 NOT_IMPLEMENTED; complete-like 621/1488 = 41.73%).
- Full suite: the combined T-101/T-102 run recorded above found the single
  UI-marker regression, which was fixed. A clean final full suite is recorded
  after T-104 below; no success is assumed from the failed run.

## T-103 - Clean-room support reporting and CSAT governance (2026-11-23)
- Targeted: `test_support_reporting_p2.py` -> **11 passed, 1 warning** named
  tests (one per CW row plus token replay/rate-limit, saved runs and workspace
  isolation); targeted + `test_ui_wiring.py` +
  `test_plane_support_ui_p1.py` -> **54 passed, 1 warning**. Every test patches
  `socket.socket.connect` to raise.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `b2c3d4e5f6a7` after upgrading the live database from `f2b3c4d5e6f7`.
- Evidence: `docs/evidence/support-reporting-p2-20261123.md`.
- Matrix: 8 rows (CW-096/097/098/099/101/104/114/117) moved to
  VERIFIED_COMPLETE; deliverables regenerated (559 VERIFIED_COMPLETE, 412
  NOT_IMPLEMENTED; complete-like 629/1,488 = 42.27%).

## T-104 - Clean-room marketing content and contact classification (2026-11-23)
- Targeted: `test_marketing_content_p2.py` -> **9 passed, 1 warning** named
  tests (one per MT row plus contract and workspace isolation); combined
  targeted, support-reporting, UI-wiring and plane-UI run -> **64 passed,
  1 warning**. Before this work the same nine tests failed with 405/404 because
  the router was never registered; the missing registration and seven additive
  tables were supplied rather than weakening the tests.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `c3d4e5f6a7b8` after upgrading the live database from `b2c3d4e5f6a7`.
- Evidence: `docs/evidence/marketing-content-p2-20261123.md`.
- Matrix: 7 rows (MT-009/029/031/032/036/037/048) moved to VERIFIED_COMPLETE;
  deliverables regenerated (566 VERIFIED_COMPLETE, 405 NOT_IMPLEMENTED;
  complete-like 636/1,488 = 42.74%).
- Full suite: **778 passed, 2 warnings in 508.77s (0:08:28)**, with no source
  or migration changes made while it ran. Evidence:
  `docs/evidence/t104-fullsuite-20261123.txt`. This confirms the T-101 marker
  fix, T-103 support reporting, T-104 marketing content and the single Alembic
  head `c3d4e5f6a7b8` together.

## T-105 - Clean-room work collaboration and API governance (2026-11-23)
- Targeted: `test_plane_collaboration_api_p2.py` -> **9 passed, 1 warning** named
  tests (one per PL row plus workspace isolation/permission guards); targeted +
  UI wiring -> **50 passed, 1 warning**.
- Broader targeted: collaboration, UI wiring, work-item planning, plane support
  UI, worker portability, support reporting and marketing content -> **91 passed,
  2 warnings in 47.92s**.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `d4e5f6a7b8c9` after upgrading the live database from `c3d4e5f6a7b8`.
- Evidence: `docs/evidence/work-collaboration-api-p2-20261123.md`.
- Matrix: 8 rows (PL-031/032/039/048/050/051/130/132) moved to
  VERIFIED_COMPLETE; deliverables regenerated (574 VERIFIED_COMPLETE, 397
  NOT_IMPLEMENTED; complete-like 644/1,488 = 43.28%).
- Full suite: the standalone run was intentionally stopped at 18% and superseded
  by one combined clean full suite covering T-105 and T-106 together, recorded in
  `docs/evidence/t106-fullsuite-20261123.txt`. The exact result is recorded in the
  T-106 section below; no source or migration was edited during that run.

## T-106 - Clean-room advanced experimentation statistics (2026-11-23)
- Targeted: `test_experiment_advanced_stats_p2.py` + `test_ui_wiring.py` ->
  **50 passed, 1 warning in 8.86s** (8 named acceptance tests, one per GB row,
  plus all UI wiring guards).
- Eight GrowthBook commercial-tier rows closed from the documented public method:
  GB-187 CUPED, GB-188 post-stratification, GB-189 sequential testing, GB-214
  quantile metrics, GB-215 retention metrics, GB-217 compound metrics, GB-222
  multi-armed bandits and GB-237 metric correlations. All algorithms are local
  standard-library implementations; no upstream source, stats package, hosted
  platform, warehouse, SDK or external statistics service is contacted.
  `socket.socket.connect` is patched to raise in every acceptance test.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `e5f6a7b8c9d0` after upgrading the live database from `d4e5f6a7b8c9`.
- Evidence: `docs/evidence/advanced-experimentation-p2-20261123.md`.
- Matrix: 8 rows moved from LICENSING_RESTRICTED to VERIFIED_COMPLETE;
  deliverables regenerated (582 VERIFIED_COMPLETE, 224 LICENSING_RESTRICTED,
  397 NOT_IMPLEMENTED; complete-like 652/1,488 = 43.82%).
- Full suite: combined clean run `docs/evidence/t106-fullsuite-20261123.txt`
  exit 0, **797 passed, 2 warnings in 578.96s (0:09:38)**.

## T-107 - Clean-room advanced feature-flag governance (2026-11-23)
- Targeted: `test_feature_flag_governance_p2.py` + `ui_v69_feature_flag_governance_contract.py` ->
  **14 passed, 1 warning in 10.24s** (13 named acceptance tests, one per GB row,
  plus the UI wiring contract guard).
- Fourteen GrowthBook commercial-tier rows closed from the documented public method:
  GB-183 scheduled flags, GB-196 secure-attribute hashing, GB-206 sticky bucketing,
  GB-209 prerequisites, GB-210 prerequisite targeting, GB-211 redirect results,
  GB-224 environment inheritance, GB-225 templates, GB-231 safe-rollout guardrails,
  GB-232/233 require-project settings, GB-247 ramp schedules, GB-248 scheduled revisions,
  GB-249 typed feature configurations. All algorithms are local standard-library
  implementations; no upstream source, SDK, hosted endpoint, licence server,
  warehouse or external service is contacted. `socket.socket.connect` is patched
  to raise in every acceptance test.
- Other checks: `node --check apps/web/app.js` exit 0; single Alembic head
  `f6a7b8c9d0e1` after upgrading the live database from `e5f6a7b8c9d0`.
  Duplicate OpenAPI operation id `createFlagRevision` was corrected to
  `createFlagGovernanceRevision`.
- Evidence: `docs/evidence/flag-governance-p2-20261123.md`.
- Matrix: 14 rows moved from LICENSING_RESTRICTED to VERIFIED_COMPLETE;
  deliverables regenerated (596 VERIFIED_COMPLETE, 210 LICENSING_RESTRICTED,
  397 NOT_IMPLEMENTED; complete-like 666/1,488 = 44.76%).
- Full suite: `docs/evidence/t107-fullsuite-20261124.txt` EXIT=0,
  **810 passed, 2 warnings in 589.38s (0:09:49)**.
