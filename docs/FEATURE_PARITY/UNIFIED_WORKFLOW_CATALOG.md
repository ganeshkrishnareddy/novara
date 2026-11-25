# Unified workflow catalog

How the ten source capabilities collapse into NOVARA workflows rather than ten separate apps. Each workflow lists the permanent feature IDs it draws on and its real state. ID lists are drawn from `MASTER_FEATURE_MATRIX.csv` and are representative (first matches), not a re-mapping of IDs — the full mapping stays in the matrix.

| Workflow | User outcome | Representative feature IDs | NOVARA surface | State |
| --- | --- | --- | --- | --- |
| Universal search across the workspace | Find any contact, company, lead, task, note or draft from one box | MS-001, MS-002, MS-003, MS-004, MS-005, MS-006, MS-007, MS-008, CW-030, CW-089, CW-156 | modules/search.py + Global Search UI | DONE in Phase 4 — /search wired to global search + full view + type filter. Evidence: phase4-browser-20261122.md. |
| Customer inbox / shared conversation | Read and reply to customer tickets in one queue | CW-001, CW-002, CW-003, CW-004, CW-006, CW-009, CW-010, CW-011, SB-029 | modules/support.py + Customer Inbox UI | DONE in Phase 4 — /tickets list/detail/reply/status; local/no-send. Evidence: phase4-browser-20261122.md. |
| Campaign lifecycle and measurement | Plan, record and measure a campaign without sending anything automatically | MT-012, MT-013, MT-014, MT-015, MT-016, MT-017, MT-018, MT-019 | modules/marketing.py + Campaign Studio UI | DONE in Phase 4 — create/metrics/status browser-verified. Evidence: phase4-browser-three-views-20261122.md. |
| Sales pipeline from lead to close | Track deals, stages and activities with an approval gate on outreach | SB-014, SB-017, SB-018, SB-020, SB-021, SB-024, SB-030, SB-031, PL-002, PL-003, PL-004, PL-005, PL-006, PL-008, PL-012, PL-013 | modules/sales.py + Sales pipeline UI | DONE in Phase 4 — deal/activity/stage browser-verified; outreach stays local drafts. Evidence: phase4-browser-three-views-20261122.md. |
| Feedback and satisfaction loop | Create surveys, capture responses and act on the score | FB-001, FB-002, FB-003, FB-004, FB-005, FB-006, FB-007, FB-008, CW-100, CW-102, CW-103, CW-104, CW-105 | modules/feedback.py + Feedback Studio UI | DONE in Phase 4 — survey/response browser-verified. Evidence: phase4-browser-three-views-20261122.md. |
| Document room with tracked views | Create a room, record document metadata and observe view events | PM-001, PM-002, PM-003, PM-004, PM-005, PM-006, PM-007, PM-008 | modules/documents.py + events | PARTIAL — metadata/room lifecycle only; no file I/O and no UI. See FEATURE_MATRIX P1–P5 and PM rows. |
| Experiment and metric evaluation | Define flags/experiments and read clean-room results | GB-007, GB-012, GB-013, GB-014, GB-015, GB-016, GB-019, GB-020 | modules/analytics.py | PARTIAL — analytics/event APIs exist; no Experiments UI; Pro/Enterprise statistics excluded. |
| Work management and cycles | Plan projects, work items and cycles with clean-room status tracking | PL-002, PL-003, PL-004, PL-005, PL-006, PL-008, PL-009, PL-010 | modules/projects.py | PARTIAL/VERIFIED slice — core project APIs tested; full Plane UX not claimed. |
| Notification workflow and adapters | Queue local notifications through provider adapters without sending | NV-002, NV-003, NV-004, NV-005, NV-006, NV-007, NV-008, NV-010 | modules/jobs.py + modules/adapters.py | PARTIAL — local queue/adapters tested; real outbound delivery blocked pending credentials. |
| Guided marketing content and growth plays | Use MIT skill-derived playbooks for SEO, copy and growth without bundling code | MK-001, MK-002, MK-003, MK-004, MK-005, MK-006, MK-007, MK-008 | content/workflows (no runtime module) | CONTENT DOCUMENTED — 53 MK rows VERIFIED_COMPLETE in MASTER_FEATURE_MATRIX.csv; no runtime module bundled; reuse with attribution. |

## Design rules for the unified product

1. One workspace, one identity, one event spine. No second login and no per-source silo.
2. Clean-room implementations only; upstream EE/proprietary paths stay restricted with an alternative in `LICENSING_EXCEPTION_REGISTER.md`.
3. Local/no-send by default: drafts, metrics and responses are recorded locally; nothing is emailed, posted or sent without explicit approval and verified credentials.
4. Light theme only; no fake data, providers or AI models.
5. A workflow is done only when its rows are `VERIFIED_COMPLETE` with named evidence.

## Coverage note

The catalogue tracks 1488 individual features; this workflow view groups them into 10 cross-source user outcomes. Grouping here never removes a feature from the matrix — every ID remains individually accounted for.
