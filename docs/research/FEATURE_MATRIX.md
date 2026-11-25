# Feature and acceptance matrix (T-009)

Status: **POPULATED** — 2026-11-22. Replaces the earlier scaffold.

Purpose: turn the ten deep repository audits into one checkable map from **source project → feature actually available under the community licence → NOVARA module → reuse approach → acceptance criteria → licence constraint**. It is the acceptance companion to `docs/VISION.md` (intent), `docs/research/LICENSE_COMPLIANCE.md` (licence decisions) and `docs/architecture/MODULE_CONTRACT.md` (how a module is built).

Founder rule applied throughout: **advertised ≠ available**. A feature that merely appears in a public source tree is not treated as available under the community licence when the licence file, feature map or README carves it out. Where the audit could not confirm a boundary, the matrix says so instead of assuming.

Sources: `docs/research/repos/01…04` (source-verified features), `docs/research/LICENSE_COMPLIANCE.md` (resolved terms), `THIRD_PARTY_NOTICES.md` (attribution), `apps/api/novara_core/modules/` and `apps/api/tests/` (what NOVARA actually implements), `docs/evidence/backend-suite-20261122-201553.txt` (143 passed, 2 warnings).

## Status legend

| Label | Meaning |
|---|---|
| IMPLEMENTED + VERIFIED | Module present, wired into the one app, and covered by named passing tests. |
| IMPLEMENTED + PARTIAL | Real, tested slice exists; the rest of the source capability is deliberately not claimed. |
| PATTERN ADOPTED | Clean-room design informed by the source; no source code imported. |
| CONTENT NOT BUNDLED | Licence permits reuse, but the asset is not shipped yet; notice is recorded only. |
| OUT OF SCOPE | Excluded by licence, cost or the founder rule. Must not be claimed as a NOVARA feature. |

## Summary matrix

| # | Source project → VISION capability | Community feature actually verified (advertised vs real) | Not available under community licence | NOVARA module (status) | Reuse approach | Licence constraint |
|---|---|---|---|---|---|---|
| 1 | Formbricks → surveys, NPS/CSAT, feedback | Advertised: no-code survey editor, targeting, link surveys, Slack/Notion/Zapier/n8n. Verified: `link`/`app` survey types, survey/response/contact/action models, delivery packages, MCP endpoint. NPS/CSAT are **template claims**, not schema types. | `apps/web/modules/ee`: SSO, teams, role management, 2FA, audit logs, quotas, white-labelling, retention, workflow/contact extras. | `modules/feedback.py` — IMPLEMENTED + PARTIAL (F1–F4) | Clean-room survey runtime; MIT client SDK only if an external engine is ever needed. No second login. | AGPLv3 community core (§13 network source offer); MIT SDK subset; EE excluded. |
| 2 | Meilisearch → universal search | Advertised: hybrid/vector search, typo tolerance, facets, synonyms, geosearch, sharding, conversational search. Verified: full-text + vector crates, filtering/facets, async task scheduler, multi-search, MCP routes. Sharding/S3 snapshots/search-rule previews are **EE-flagged in source**. | BUSL-1.1 EE: sharding, S3-streaming snapshots, network/leader features, search-rule previews. | `modules/search.py` — IMPLEMENTED + PARTIAL (S1–S5) | Clean-room, read-only SQL search over shared CRM tables. No external engine in the default install. | MIT + OpenLDAP core; BUSL EE excluded; no cloud dependency. |
| 3 | GrowthBook → flags, experiments, analytics | Advertised: flags, experiments, bandits, visual editor, analytics, interleaving. Verified in MIT code: flag CRUD/environments/revisions, A/B tests, holdouts, interleavings, bandits, metric types, fact tables, SQL explorer, webhooks. `oss` plan has **zero** commercial features. | Pro/Enterprise: advanced permissions, scheduled flags, sequential testing/CUPED/post-stratification, visual editor, remote evaluation, advanced RBAC, SSO/SCIM, audit logs, dashboards. | `modules/analytics.py` — IMPLEMENTED + PARTIAL (G1–G5) | Clean-room evaluation core; consume MIT SDK/public API only for an explicit external instance. | MIT community; `packages/*/enterprise` excluded. |
| 4 | Papermark → secure documents, data rooms, viewer tracking | Advertised: shareable links, custom domain, tracking analytics, self-hosting. Verified: document/version/page models, links, visits/views/reactions, data-room models, webhooks. Data Rooms, Q&A and advanced permissions are **EE features despite models in the community schema**. | `ee/` and `app/(ee)/`: Data Rooms UI, Q&A conversations, advanced permissions, AI/workflows, SAML/SCIM. | `modules/documents.py` — IMPLEMENTED + PARTIAL (P1–P5) | Clean-room metadata + room lifecycle; view events via the shared event spine. No file I/O. | AGPLv3 community core; commercial EE excluded. No code copied. |
| 5 | Plane → projects, tasks, issues, kanban, cycles | Advertised: work items, cycles, modules, views, pages, analytics. Verified in community source: project/work-item/cycle/module/state/label APIs and background tasks. SAML/OIDC/LDAP, audit logs, dashboards, initiatives, teamspaces are **paid-tier claims, not verified community features**. | Paid tiers: custom work-item types/properties, dashboards, initiatives, teamspaces, integrations, SAML/OIDC/LDAP, granular access control, audit logs. | `modules/projects.py` — IMPLEMENTED + VERIFIED (PL1–PL4) | Clean-room work management; public REST API only for user-configured interoperability. | AGPL-3.0-only entire repo; no source reuse. |
| 6 | Mautic → segmentation, campaigns, landing pages, journeys | Advertised: open-source marketing automation, "all features" in self-host package. Verified: Lead/Email/Campaign/Page/Form/Point/Stage/DynamicContent/Asset/Webhook/Report/Dashboard bundles and plugins. No separate enterprise source edition found in `7.x`. | No source feature gate found. Paid items are **hosting services** (managed tiers, SSO, higher sending limits), not withheld GPL source. | `modules/marketing.py` — IMPLEMENTED + PARTIAL (M1–M3) | Clean-room campaign/metrics module; optional MIT `mautic/api-library` at an explicit boundary only. | GPL-3.0 core (no network clause); Mautic trademark not licensed. No core code copied. |
| 7 | Chatwoot → support, shared inbox, omnichannel | Advertised + source-verified in community: live-chat widget, email/Facebook/Instagram/Twitter/Telegram/Line/SMS/WhatsApp channels, shared inbox, contacts, conversations, labels, canned responses, teams, CSAT, help centre, automation rules, webhooks. | `enterprise/`: conversation monitors verified; SSO/advanced compliance listed as **unverified** by the audit — not assumed available. | `modules/support.py` — IMPLEMENTED + PARTIAL (C1–C3) | Clean-room ticket/conversation core; MIT core API/SDK for channel connectivity if added later. | MIT community; commercial `enterprise/` excluded. |
| 8 | Novu → notification workflows, multi-channel delivery | Advertised + source-verified in MIT/core: multi-channel API, workflow engine with branching/digests, embeddable Inbox, subscriber preferences, no-code editor, provider folders (20 email/37 SMS/8 push/13 chat), event triggers. | `enterprise/packages` + `*ee*` paths: auth, billing, DAL, shared services, translation under the proprietary licence (no modification, no redistribution, prior written approval). | `modules/jobs.py`, `modules/adapters.py`, `modules/operations.py` — IMPLEMENTED + VERIFIED (N1–N6) | Clean-room job queue + provider adapters; local mock never claims delivery. | MIT core + SDKs; proprietary packages excluded entirely. |
| 9 | Marketing Skills → SEO, copywriting, growth content | Advertised: free MIT skill pack. Verified: 53 skills with frontmatter and evals, 128 integration guides, 69 Node CLIs, plugin manifests. No enterprise gate; sponsorship tiers are funding, not access control. | None in the repo. Private-site features could not be verified because site source is not public. | No runtime module — CONTENT NOT BUNDLED (MS1–MS2) | Vendor content only through a defined local path with version pinning; keep provenance headers. | MIT; preserve copyright notice, skill frontmatter, partner disclosures and `partners.json`. |
| 10 | Sellbird → lead research, prospecting, outreach | Advertised: find companies/decision-makers, verify email, write and send cold email, handle replies. Verified: multi-agent pipeline, 29-signal catalog (26 free), discovery providers, verification, sequence drafting, Outbox approval, sending, reply classification, suppression, MCP server, CSV export. Entire repo is AGPL-3.0-only from v0.4.0. | No enterprise gate; hosted `sellbird.ai` is private beta with no public pricing/terms. Paid data-provider APIs are third-party dependencies, not Sellbird features. | `modules/sales.py` + workflow/agent center — IMPLEMENTED + PARTIAL / PATTERN ADOPTED (SB1–SB6) | Clean-room: adopt the approval-gate, observation-row and Outbox patterns; import no AGPL code. | AGPL-3.0-only v0.4.0+; older ≤0.3.x MIT notice preserved; hosted service not a dependency. |

## Gap register and next actions (per source feature)

A route, table or placeholder is not evidence of a finished workflow. This register records what is still missing for each source feature set and the next concrete action. Priorities: **P0** = close this cycle; **P1** = next cycle; **P2** = after the unified experience is coherent.

| Source / feature set | Refs | Missing functionality (verified in this workspace) | Next action | Priority |
|---|---|---|---|---|
| Formbricks → Feedback Studio | F1–F4 | **CLOSED 2026-11-22:** Feedback Studio UI now wired to `/surveys`; survey create + response capture browser-verified. Still absent: link/app distribution, targeting rules and NPS/CSAT presets (upstream NPS/CSAT are template claims, not schema types). | Evidence: `docs/evidence/phase4-browser-three-views-20261122.md`. Remaining distribution/targeting work is tracked by MK/FB rows in the feature-parity matrix. | P1 |
| Meilisearch → Universal Search | S1–S5 | **CLOSED 2026-11-22:** global search and Universal Search view now call `/search?q=…`, render `type`/`title`/`subtitle`/`url_hint`, and offer a full view with type filters. Literal-wildcard and workspace-isolation guarantees preserved. | Evidence: `docs/evidence/phase4-browser-20261122.md`. | DONE |
| GrowthBook → Analytics & Experiments | G1–G5 | Experiment/funnel/event APIs are tested but have **no Experiments UI**; no clean-room flag CRUD slice. Advanced stats, bandits and visual editor are out of scope by licence decision. | Add an Experiments view (list/create/status/results) over `/analytics`; do not claim Pro/Enterprise statistics. | P1 |
| Papermark → Documents & Data Rooms | P1–P5 | Metadata/room APIs exist but have **no UI**. No file-storage boundary is defined, no room access-control rules exist, and view tracking is registered as an event type only (P5 = PARTIAL). | Add a Data Rooms view for metadata lifecycle; state explicitly that no file is uploaded/read; define room-level access rules before any file feature. | P1 |
| Plane → Projects & Work | PL1–PL4 | Project/item/progress APIs exist but have **no UI**; cycles, modules and kanban are absent. | Add a Projects & Work view for projects, items and SQL-computed progress, linked to the shared task/contact records. | P1 |
| Mautic → Campaign Studio / Marketing Intelligence | M1–M3 | **CLOSED 2026-11-22:** Campaign Studio UI wired to `/campaigns`; create, daily metrics and status changes browser-verified. Still absent: scheduling, segmentation, journey builder and landing pages (explicitly not claimed). | Evidence: `docs/evidence/phase4-browser-three-views-20261122.md`. Remaining capability tracked in MT rows. | P1 |
| Chatwoot → Customer Inbox | C1–C3 | **CLOSED 2026-11-22:** Customer Inbox UI wired to `/tickets`; list/filter, create, replies and status changes browser-verified (local/no-send). Channel connectors, widget and CSAT remain unimplemented. | Evidence: `docs/evidence/phase4-browser-20261122.md`. Channel/CSAT work tracked in CW rows. | DONE |
| Novu → Notification Center / jobs | N1–N6 | Job, adapter and operations UIs exist. No notification preferences or digests; real provider delivery remains externally blocked and must not be claimed. | Add notification preferences under Settings; keep local-mock and blocked-component labels explicit. | P2 |
| Marketing Skills → content pack | MS1–MS2 | Licence permits reuse, but **no content is bundled**; only the attribution notice is recorded. | Decide whether to vendor pinned MIT content with provenance headers and `partners.json`; add no runtime dependency. | P2 |
| Sellbird → Sales Autopilot | SB1–SB6 | **CLOSED 2026-11-22:** Sales pipeline UI wired to `/deals`; deal create, activity and stage changes browser-verified (no outreach sent). Prospect research, email verification and the approval queue remain unimplemented. | Evidence: `docs/evidence/phase4-browser-three-views-20261122.md`. Remaining work tracked in SB rows. | P1 |

## Phase 4 / feature-parity checkpoint (2026-11-22)

- Skye's `docs/PHASE_4_MODULE_AUDIT.md` Top 5 gaps are all **closed in code and browser-verified**: #1 Universal Search and #2 Customer Inbox (`docs/evidence/phase4-browser-20261122.md`); #3 Campaign Studio, #4 Sales pipeline and #5 Feedback Studio (`docs/evidence/phase4-browser-three-views-20261122.md`). The "no UI"/"in progress" wording in the historical gap register above is reconciled by the CLOSED annotations added on 2026-11-22; the original rows are retained for audit history.
- The permanent ten-source feature catalogue supersedes this 10-row summary matrix as the **complete** specification: `docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv` (1,488 rows, permanent IDs) and the eight deliverables in `docs/FEATURE_PARITY/`.
- Honest completion: `docs/FEATURE_PARITY/COMPLETION_DASHBOARD.md` reports 98/1,488 (6.59%) at code level, with 846 NOT_IMPLEMENTED, 173 PARTIALLY_IMPLEMENTED, 236 LICENSING_RESTRICTED and 135 EXTERNAL_DEPENDENCY_BLOCKED rows — **not 100% complete**.
- Backend suite after all wiring: 148 passed, 1 warning (`docs/evidence/phase4-after-three-views-20261122.txt`). `node --check apps/web/app.js` clean. Git HEAD unchanged (`73e9f76`), all work local/uncommitted.

## Acceptance criteria in detail

Every row below is checkable in this workspace. Evidence paths are relative to `D:\NOVARA`. Test names are the actual functions in the 143-test suite. A criterion marked "design constraint" is enforced by review, not by a test.

### 1 — Feedback / surveys (Formbricks)

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| F1 | Survey list/create and response endpoints are registered on the production app and return 200/201 through it. | `apps/api/tests/test_integration.py::test_every_module_is_registered_on_the_production_app`, `::test_module_endpoints_work_through_the_real_app` | PASS |
| F2 | Every survey mutation writes an append-only event carrying the verified `workspace_id`. | `test_integration.py::test_module_event_appears_in_shared_audit_log` (asserts `survey.created`) | PASS |
| F3 | A user from another workspace gets 403 on survey routes. | `test_integration.py::test_module_routes_enforce_workspace_isolation` | PASS |
| F4 | No NPS/CSAT preset, in-app targeting or EE capability is claimed as implemented. | Audit `01` §2 and §11; `modules/feedback.py` exposes survey/response CRUD only | Design constraint |

### 2 — Search (Meilisearch)

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| S1 | Search spans contacts, leads, companies, tasks, notes and outreach drafts, including joined lead/note fields. | `test_search.py::search_across_all_shared_types`, `::search_matches_joined_lead_and_note_records` | PASS |
| S2 | User `%` and `_` are matched literally, never expanded as wildcards. | `test_search.py::literal_wildcards_are_not_expanded`; `_pattern()` in `modules/search.py` | PASS |
| S3 | Result limits and invalid queries are handled without errors or data leaks. | `test_search.py::limit_and_invalid_queries` | PASS |
| S4 | No result from another workspace is ever returned. | `test_search.py::search_never_exposes_other_workspace` | PASS |
| S5 | No external search engine, typo tolerance, facets, semantic search or EE feature is a default-install dependency or claim. | `modules/search.py` docstring ("pure reads only, no new tables"); audit `01` §11 | Design constraint |

### 3 — Experiments / analytics (GrowthBook)

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| G1 | Experiment CRUD, status changes, results and events work end to end. | `test_analytics.py::experiment_crud_results_and_events` | PASS |
| G2 | Funnel counts come from real workspace-shared rows, not fixtures. | `test_analytics.py::funnel_summary_counts_workspace_shared_tables`, `test_listing.py::analytics_funnel_uses_real_rows_and_is_workspace_scoped` | PASS |
| G3 | Event volume honours a date window. | `test_analytics.py::event_volume_with_date_range`, `test_listing.py::event_volume_supports_date_window` | PASS |
| G4 | Analytics are workspace-isolated and reject invalid payloads. | `test_analytics.py::workspace_isolation`, `::invalid_payloads` | PASS |
| G5 | No bandits, sequential testing, visual editor, SSO or Pro/Enterprise feature is claimed in the default install. | Audit `01` §11 (`oss` has zero commercial features) | Design constraint |

### 4 — Documents / data rooms (Papermark)

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| P1 | Data-room and document metadata lifecycle works (create/read/update/delete). | `test_documents.py::dataroom_and_document_metadata_lifecycle` | PASS |
| P2 | Room names are unique per workspace; deleting a room with document metadata is guarded. | `test_documents.py::dataroom_name_must_be_unique_per_workspace`, `::room_delete_guarded_by_existing_document_metadata` | PASS |
| P3 | Rooms and documents are workspace-isolated; bad payloads are rejected. | `test_documents.py::documents_and_rooms_are_workspace_isolated`, `::document_filters_and_bad_payloads` | PASS |
| P4 | The module opens, reads, writes and uploads **no** file; `storage_path` is an opaque caller reference. | `modules/documents.py` module docstring | Design constraint |
| P5 | "Document viewed" feeds the shared event spine for the cross-module proposal flow. | Event types registered in `modules/documents.py`; no real file-view endpoint exists — view tracking is **not claimed** as delivered | PARTIAL |

### 5 — Projects (Plane)

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| PL1 | Project CRUD, work items, completion and events work end to end. | `test_projects.py::project_crud_items_completion_and_events` | PASS |
| PL2 | Progress summary is computed in SQL from real rows. | `test_projects.py::project_progress_summary_is_computed_in_sql` | PASS |
| PL3 | Projects are workspace-isolated and reject bad payloads/missing rows. | `test_projects.py::project_workspace_isolation`, `::project_bad_payloads_and_missing_rows` | PASS |
| PL4 | No Plane source code or embedded instance is used. | `docs/research/LICENSE_COMPLIANCE.md` decision 5; `modules/projects.py` is native code | Design constraint |

### 6 — Marketing (Mautic)

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| M1 | Campaign CRUD, metric rollups, summary and events work. | `test_marketing.py::campaign_metrics_rollups_summary_and_events` | PASS |
| M2 | Duplicate campaign names and invalid payloads are rejected; campaigns are workspace-isolated. | `test_marketing.py::duplicate_campaign_names_are_rejected`, `::invalid_campaign_payloads_are_rejected`, `::campaigns_are_isolated_by_workspace` | PASS |
| M3 | No route sends external email or publishes publicly; landing pages are not claimed. | `test_workflow.py::no_route_sends_external_messages`, `test_adversarial.py::no_route_can_send_or_publish_external_messages` | PASS |

### 7 — Support (Chatwoot)

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| C1 | Ticket lifecycle, messages and events work end to end. | `test_support.py::ticket_lifecycle_messages_and_events` | PASS |
| C2 | Status/priority filters work; bad payloads rejected; tickets workspace-isolated. | `test_support.py::ticket_status_and_priority_filters`, `::ticket_bad_payloads_and_missing_rows`, `::ticket_workspace_isolation` | PASS |
| C3 | No second user store, live-chat widget or channel integration is claimed in the default install. | `modules/support.py`; audit `02` §2.15 | Design constraint |

### 8 — Jobs, adapters, operations (Novu)

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| N1 | Enqueue is idempotent and audited. | `test_jobs.py::enqueue_is_idempotent_and_audited` | PASS |
| N2 | A local handler creates a real in-app notification; mocks and AI adapters never claim delivery or fabricate output. | `test_jobs.py::local_handler_creates_real_notification`, `test_adapters.py::local_mock_invocation_never_claims_delivery`, `::ai_adapter_does_not_fabricate_output` | PASS |
| N3 | Retry with backoff, dead letter, manual retry, cancel, stale-job recovery and workspace-scoped recovery all work. | `test_jobs.py::retry_backoff_then_success`, `::dead_letter_and_manual_retry`, `::unknown_handler_dead_letters_without_consuming_retries`, `::cancel_and_retry_lifecycle`, `::recover_stale_jobs_after_crash`, `::recovery_is_scoped_to_one_workspace` | PASS |
| N4 | Secret-like fields are rejected before an adapter or integration can record them. | `test_integrations.py::secret_fields_are_rejected`, `::secret_like_fields_are_rejected_even_when_nested_or_camel_case`, `test_adapters.py::secrets_are_rejected_before_adapter_can_record_them` | PASS |
| N5 | Capabilities distinguish configured / disabled / not configured; invoking an unconfigured provider is rejected. | `test_adapters.py::capabilities_distinguish_configured_disabled_and_not_configured`, `::invoke_rejected_when_not_configured` | PASS |
| N6 | Operations summary reports real counts and components distinguish local from blocked. | `test_operations.py::summary_reports_real_counts`, `::components_distinguish_local_and_blocked` | PASS |

### 9 — Marketing Skills content pack

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| MS1 | No skill/CLI content is vendored into NOVARA; only the attribution notice is recorded. | `THIRD_PARTY_NOTICES.md` "Marketing Skills — Corey Haines" | PASS (by inspection) |
| MS2 | If bundled later, preserve LICENSE, skill frontmatter, partner disclosure headers and `partners.json`, with version pinning. | Audit `04` §14–15; future action, not yet performed | Pending |

### 10 — Sales / outreach patterns (Sellbird)

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| SB1 | Deal lifecycle, filters, summary, activities and events work. | `test_sales.py::deal_lifecycle_filters_summary_activities_and_events` | PASS |
| SB2 | Duplicate deals and invalid payloads rejected; deals workspace-isolated. | `test_sales.py::duplicate_deals_are_rejected`, `::invalid_deal_payloads_are_rejected`, `::deals_are_isolated_by_workspace` | PASS |
| SB3 | Outreach requires an authorised approver and is never sent; approval cannot create an external message. | `test_workflow.py::outreach_requires_an_authorised_approver_and_is_never_sent`, `::no_route_sends_external_messages`, `test_integrity.py::approval_never_sends_external_message` | PASS |
| SB4 | Agent approval is role-gated, publishes events, enforces execution limits, is workspace-isolated and requires auth. | `test_agent_center.py` (all 5 tests) | PASS |
| SB5 | Intake creates one identity with linked records, is idempotent, updates one contact instead of duplicating, and qualification converts with tasks. | `test_workflow.py::intake_creates_one_identity_and_linked_records`, `::intake_is_idempotent_for_the_same_submission`, `::same_email_updates_one_contact_instead_of_duplicating`, `::lead_qualification_conversion_and_tasks` | PASS |
| SB6 | No Sellbird AGPL source is imported; only the signal/observation/Outbox/approval patterns are adopted. | `docs/research/LICENSE_COMPLIANCE.md` decision 10; `THIRD_PARTY_NOTICES.md` preserves the older MIT notice | Design constraint |

### Cross-cutting acceptance (applies to all ten)

| Ref | Acceptance criterion | Evidence | Status |
|---|---|---|---|
| X1 | Every scoped resource denies cross-workspace reads and writes. | `test_adversarial.py::cross_workspace_access_is_denied_for_every_scoped_resource`, `::cross_workspace_write_is_denied`, `::guessed_cross_tenant_ids_never_return_data`; `test_isolation.py` (5 tests) | PASS |
| X2 | Auth, RBAC, token rotation/revocation and read-only roles hold. | `test_adversarial.py` (auth/role tests), `test_workflow.py::unauthenticated_request_is_rejected`, `::read_only_role_cannot_write`, `::logout_revokes_token_and_refresh_rotates` | PASS |
| X3 | Security headers on success and error, no reflected validation values, rate limiting, same-origin CORS default. | `test_security.py` (4 tests) | PASS |
| X4 | Events are append-only, idempotent and correlated. | `test_adversarial.py::events_are_append_only_idempotent_and_correlated` | PASS |
| X5 | Failed writes roll back with no partial records; duplicate submissions create one run. | `test_integrity.py` (5 tests) | PASS |
| X6 | All 37 tables compile to PostgreSQL DDL, tenant tables carry `workspace_id`, `SKIP LOCKED` compiles; **no live PostgreSQL run is claimed**. | `test_portability.py` (4 tests) | PASS (compile only) |
| X7 | Backup, verify and restore work; restore refuses to overwrite without force. | `test_backup_restore.py` (2 tests) | PASS |
| X8 | One light-theme-only professional experience; no dark mode. | `apps/web/styles.css` `color-scheme: light`; `docs/VISION.md` §"One professional experience" | PASS (source inspection) |
| X9 | The whole suite passes with no skips or weakened tests. | `docs/evidence/backend-suite-20261122-201553.txt` — `143 passed, 2 warnings in 48.10s` | PASS |

## Excluded / out-of-scope register

These are **not** NOVARA features in the default install and must not be described as such in docs, UI or outreach:

- Formbricks EE: SSO, teams, role management, 2FA, audit logging, quotas, white-labelling, data retention, contact/creative/workflow extras.
- Meilisearch EE: sharding, S3-streaming snapshots, network/leader topology, search-rule previews.
- GrowthBook Pro/Enterprise: advanced statistics (sequential testing, CUPED, post-stratification), bandits, interleaving, holdouts, visual editor, remote evaluation, advanced RBAC, SSO/SCIM, audit logs, analytics dashboards.
- Papermark EE: Data Rooms UI, Q&A conversations, advanced permissions, AI/workflows, SAML/SCIM.
- Plane paid tiers: custom work-item types/properties, dashboards, initiatives, teamspaces, integrations, SAML/OIDC/LDAP, granular access control, audit logs.
- Chatwoot Enterprise: conversation monitors; SSO/advanced compliance unconfirmed.
- Novu proprietary: `enterprise/packages` and all `*ee*` paths.
- Sellbird: all AGPL v0.4.0+ code and the private-beta hosted service.
- Any external email, SMS or public post without authorisation; any paid cloud tier as a default dependency.

## Limits of this matrix

- Acceptance rows marked PASS reflect local SQLite, in-process FastAPI tests and source inspection. PostgreSQL, Docker/container builds, physical devices, non-Chromium browsers and real outbound providers remain unverified (see `docs/FINAL_RELEASE_READINESS.md` §E).
- "IMPLEMENTED + PARTIAL" is deliberate: the audited source capability is documented, but NOVARA only claims the slice that has real code and tests. The gap is recorded, not hidden.
- NOVARA's own licence is still an owner decision (`docs/BLOCKERS.md` B-03); this matrix does not choose it.
