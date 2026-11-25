# Phase 4 module audit — NOVARA

Date: 2026-11-22. Scope: read-only audit of the 16 Phase 4 product areas against
`docs/VISION.md` and the verified code under `apps/api/novara_core/**`,
`apps/web/app.js`, `apps/web/styles.css`, and tests under `apps/api/tests/**`.
No code, tests, task board, `FEATURE_MATRIX.md`, evidence files or git state were
changed. Only this file was created.

Code + tests are authoritative; `docs/IMPLEMENTATION_STATUS.md` and
`docs/PHASE_3_COMPLETION_REPORT.md` are cross-checks only. A route, table or UI
placeholder is not treated as proof of a complete workflow.

## Classification labels

- **Fully implemented and verified** — backend route(s) + module tables + named passing
  tests, and (where applicable) a frontend view wired to them; complete for the
  locally verified scope.
- **Partially implemented** — a real, tested slice exists, but significant
  VISION capability for that area is missing.
- **Backend only** — backend module and tests exist, but no frontend view/route
  consumes them.
- **Frontend only** — UI exists without a backing API (none found in this build).
- **Placeholder** — UI shell or dead button with no backend workflow.
- **Not implemented** — no code or tests.
- **Externally blocked** — depends on external credentials, providers or
  infrastructure not available locally.

## Audit table

| Area | VISION requirement(s) | Classification | Backend evidence | Frontend evidence | Test evidence | Missing functionality | Next action | Priority |
|---|---|---|---|---|---|---|---|---|
| 1 Command Center | One dashboard with unified navigation and real workspace aggregates (VISION "One product" / "Everything must work together") | Partially implemented | `apps/api/novara_core/modules/operations.py` `summary()` (OperationsSummary), `analytics.py` `funnel_summary()`, `event_volume()`; jobs/adapters routers | `apps/web/app.js` `loadDashboard()` (Overview), `loadOperations()` (System health), `loadInsights()`, `loadJobs()`, `loadAdapters()` | `apps/api/tests/test_operations.py` (4), `test_listing.py` (4), `test_integration.py` | Dashboard aggregates only contacts/leads/tasks/notifications/drafts/events/jobs/adapters; no consolidated KPIs for deals, campaigns, tickets, projects, documents, automations or agents | Extend Overview/System health to pull and link counts for all modules | P1 |
| 2 CRM & Contacts | Single Contact identity, duplicate check, contacts/companies/notes/tasks/timeline (T-013) | Fully implemented and verified | `apps/api/novara_core/main.py` contact/company/note/task routes (`_contact_or_404`, `create_contact`, `archive_contact`, `restore_contact`, `delete_contact`), `workflow.py` `handle_website_form`; models Contact, Company, Note, Task | `apps/web/app.js` `loadContactsPage()`, `loadContactDetail()`, `loadCompanies()`, `loadTasks()` | `apps/api/tests/test_workflow.py` (15), `test_listing.py`, `test_integrity.py`, `test_isolation.py`, `test_adversarial.py`, `test_security.py` | No company update/delete endpoints; no bulk import/export or duplicate merge | Add company edit/delete + import/export if required; otherwise document as scoped | P2 |
| 3 Lead Intelligence | Lead research, prospecting, enrichment, qualification, conversion (VISION Sellbird) | Partially implemented | `apps/api/novara_core/main.py` lead routes (`list_leads`, `create_lead`, `update_lead`, `qualify_lead`, `convert_lead`); `modules/search.py` lead joins | `apps/web/app.js` `loadLeads()` | `apps/api/tests/test_workflow.py` (`lead_qualification_conversion_and_tasks`), `test_listing.py`, `test_search.py` | No prospect discovery, enrichment, automated scoring or source ingestion beyond manual entry; `score` is manual | Add rule-based scoring + duplicate detection over existing Lead rows | P1 |
| 4 Sales Autopilot | Sales pipeline, deals, activities, outreach drafts, approval, agents (VISION Sellbird) | Backend only | `apps/api/novara_core/modules/sales.py` `Deal`, `DealActivity`, deal CRUD/summary/activities; `main.py` outreach-drafts + `approve_draft`; `workflow.py` `approve_outreach_draft`; `modules/agents.py` | `apps/web/app.js` `loadDrafts()` only; no deals view (no `/deals` reference in app.js) | `apps/api/tests/test_sales.py` (4), `test_workflow.py`, `test_agent_center.py` (5) | No deals/pipeline UI; no prospect research or email verification; outreach never sends by design | Add Sales view for deals, pipeline summary and approval queue over `/deals` + `/outreach-drafts` | P1 |
| 5 Campaign Studio | Campaigns, segmentation, journeys, metrics (VISION Mautic) | Backend only | `apps/api/novara_core/modules/marketing.py` `Campaign`, `CampaignMetric`, campaign CRUD, `campaign_performance()`, metric upsert | none found (no `/campaigns` reference in `apps/web/app.js`) | `apps/api/tests/test_marketing.py` (4), `test_integration.py` | No Campaign Studio UI; no scheduling, segmentation, journeys or landing pages (landing pages not claimed) | Add Campaign Studio view for campaign lifecycle + metrics over `/campaigns` | P1 |
| 6 Marketing Intelligence | SEO, copywriting, growth, content, competitor research (VISION Marketing Skills) | Partially implemented | `apps/api/novara_core/modules/analytics.py` `funnel_summary()`, `event_volume()`; `modules/marketing.py` `campaign_performance()` | `apps/web/app.js` `loadInsights()` (funnel + event volume only) | `apps/api/tests/test_analytics.py` (5), `test_marketing.py` (4) | No SEO/copy/content tooling, competitor research or scheduling; insights limited to funnel/event volume | Decide on bundling Marketing Skills content (MS1/MS2) and extend insights with campaign performance | P2 |
| 7 Customer Inbox | Support tickets, shared inbox, messages (VISION Chatwoot) | Backend only | `apps/api/novara_core/modules/support.py` `Ticket`, `TicketMessage`, ticket CRUD, messages, filters | none found (no `/tickets` reference in `apps/web/app.js`) | `apps/api/tests/test_support.py` (4), `test_integration.py` | No inbox UI; no channel connectors, widget, CSAT or canned responses | Add Customer Inbox view with contact-linked tickets, status changes and threads over `/tickets` | P0 |
| 8 Feedback Studio | Surveys, NPS, CSAT, feedback (VISION Formbricks) | Backend only | `apps/api/novara_core/modules/feedback.py` `Survey`, `SurveyResponse`, survey/response CRUD and detail | none found (no `/surveys` reference in `apps/web/app.js`) | `apps/api/tests/test_integration.py` (registration, event, isolation rows) | No Feedback Studio UI; no distribution/targeting; NPS/CSAT are upstream template claims, not schema types | Add Feedback Studio view for survey lifecycle and response capture over `/surveys` | P1 |
| 9 Analytics & Experiments | Feature flags, experiments, A/B testing, product analytics (VISION GrowthBook) | Partially implemented | `apps/api/novara_core/modules/analytics.py` `Experiment`, `ExperimentResult`, experiment CRUD/status/results, funnel, event volume | `apps/web/app.js` `loadInsights()` (funnel/event volume only; no experiments UI) | `apps/api/tests/test_analytics.py` (5), `test_listing.py` | No Experiments UI or flag CRUD; advanced stats, bandits and visual editor out of scope by licence | Add Experiments view over `/analytics`; do not claim Pro/Enterprise statistics | P1 |
| 10 Universal Search | Fast, typo-tolerant, filterable universal search (VISION Meilisearch) | Partially implemented | `apps/api/novara_core/modules/search.py` `universal_search()` across contacts, leads, companies, tasks, notes, outreach drafts with wildcard escaping | `apps/web/app.js` global search uses `/contacts?search=` + cached leads/tasks; does not call `/search` | `apps/api/tests/test_search.py` (5) | Frontend not wired to `/search`; no type filters/results view; no typo tolerance/facets by design | Wire global search + Universal Search view to `/search?q=...` | P0 |
| 11 Projects & Work | Projects, tasks, issues, kanban, cycles, milestones (VISION Plane) | Backend only | `apps/api/novara_core/modules/projects.py` `Project`, `ProjectItem`, project/item CRUD, `project_progress()` | none found (no `/projects` reference in `apps/web/app.js`) | `apps/api/tests/test_projects.py` (4), `test_integration.py` | No Projects UI; no cycles, modules or kanban | Add Projects & Work view for projects, items and SQL-computed progress over `/projects` | P1 |
| 12 Documents & Data Rooms | Secure sharing, viewer tracking, permissions, data rooms (VISION Papermark) | Backend only | `apps/api/novara_core/modules/documents.py` `DataRoom`, `Document`, room/document metadata lifecycle; metadata only, no file I/O | none found (no `/documents` reference in `apps/web/app.js`) | `apps/api/tests/test_documents.py` (5), `test_integration.py` | No UI; no file-storage boundary or room access rules; viewer tracking registered as event type only (P5 partial) | Add Data Rooms view; define storage/access rules before any file feature | P1 |
| 13 Notification Center | Notification workflows: email, push, SMS, in-app (VISION Novu) | Partially implemented | `apps/api/novara_core/main.py` notification routes (`list_notifications`, `mark_notification_read`); `modules/jobs.py` `notification.create` handler; `modules/adapters.py` | `apps/web/app.js` `loadNotifications()` (list + mark read) | `apps/api/tests/test_jobs.py` (`local_handler_creates_real_notification`), `test_operations.py` | No notification preferences, digests or templates; real delivery externally blocked | Add notification preferences under Settings; keep local-mock/blocked labels | P2 |
| 14 Visual Automation Builder | Stored definitions plus real execution logs (VISION automation) | Backend only | `apps/api/novara_core/modules/automation.py` `Automation`, `AutomationRun`, CRUD, status, `dry_run()` (read-only evaluation) | none found (no `/automations` reference in `apps/web/app.js`) | `apps/api/tests/test_automation.py` (5), `test_integration.py` | No builder UI; no executable actions (dry-run only); no event triggers | Add automation builder view with step editor + dry run over `/automations` | P1 |
| 15 AI Agent Control Center | Agent ecosystem with sub-agents, orchestrator, bounded autonomy (VISION controlled autonomy) | Partially implemented | `apps/api/novara_core/modules/agents.py` `AgentConfig`, `AgentRun`, config CRUD, status, run request/progress/approve, limits | `apps/web/app.js` `loadAgents()` (agent center) | `apps/api/tests/test_agent_center.py` (5), `test_integration.py` | Governor-only: no external AI provider called, no fabricated output, no sub-agent delegation or orchestration | Keep governor-only honestly; any execution must use adapters + approval gates | P1 |
| 16 Settings & Integrations | Settings, integration catalog, non-sensitive config, secret rejection | Fully implemented and verified | `apps/api/novara_core/main.py` auth/settings routes (`change_password`, email verify); `modules/integrations.py` integration CRUD/capabilities/secret rejection; `modules/adapters.py` mock invoke | `apps/web/app.js` `loadSettings()`, `loadIntegrations()` | `apps/api/tests/test_integrations.py` (5), `test_adapters.py` (7), `test_security.py` (4), `test_operations.py` | Notification preferences absent; real provider activation/delivery externally blocked (no credentials) | Add notification preferences; keep real providers as externally blocked | P2 |

## Top 5 gaps by value

Ranking the highest-value locally implementable gaps (no external credentials, no
new system installs), each with a one-sentence rationale.

1. **Universal Search frontend wiring** — the tested `/search` API already spans
   six record types, so connecting the existing global search box to it unlocks
   cross-record findability with no new backend work.
2. **Customer Inbox UI** — ticket/message APIs and tests already exist, so a view
   over `/tickets` delivers the core support workflow that is currently unreachable
   from the app.
3. **Campaign Studio UI** — campaign and metric endpoints are implemented and
   tested, so surfacing them gives marketing a usable campaign workspace instead
   of a dead area.
4. **Sales Autopilot deals UI** — deal lifecycle, summary and activity APIs are
   verified, so a pipeline view converts already-shipped backend capability into
   user-visible sales tracking.
5. **Feedback Studio UI** — survey and response endpoints are registered and
   event-audited, so a view over `/surveys` makes the feedback capability usable
   without adding new data or services.

## Verification note

This audit was performed by reading the source files listed above; no tests were
run and no repository state was modified. Counts and route names reflect the
tree as of 2026-11-22. Items marked "none found" mean no matching frontend
reference or dedicated test file was located; absence of evidence is reported
rather than inferred.

