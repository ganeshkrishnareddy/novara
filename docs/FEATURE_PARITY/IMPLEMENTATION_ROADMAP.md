# Implementation roadmap

Cycles are ordered by the permanent priority assigned to each feature ID. Counts come from `MASTER_FEATURE_MATRIX.csv`. A feature moves to a later status only when it passes its named acceptance criteria and test/browser evidence in `FEATURE_TEST_EVIDENCE.md`; a route or 200 response never closes a row.

## Priority backlog (all rows)

| Priority | Rows | Cycle | Meaning |
| --- | --- | --- | --- |
| P0 | 111 | Cycle 1 | Close first: core unified workflows and governance gaps. |
| P1 | 218 | Cycle 2 | Next: complete in-flight module slices and their UX. |
| P2 | 576 | Cycle 3 | After the unified experience is coherent. |
| P3 | 583 | Cycle 4 | Long tail, enterprise boundaries and advertised-only items. |

## Already in the codebase (do not rebuild)

- 596 `VERIFIED_COMPLETE`, 70 `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION`, 0 `IMPLEMENTED_UNVERIFIED`, 0 `BACKEND_ONLY`.
- Phase 4 UI gap closure (2026-11-22): Universal Search and Customer Inbox (`docs/evidence/phase4-browser-20261122.md`), then Campaign Studio, Sales pipeline and Feedback Studio (`docs/evidence/phase4-browser-three-views-20261122.md`). These correspond to audit gaps #1–#5 in `docs/PHASE_4_MODULE_AUDIT.md` and are now closed in code.

## Cycle 1 — priority P0 (111 features)

| Module area | Rows | Representative IDs |
| --- | --- | --- |
| Documents / Storage / Sharing / Analytics | 14 | PM-002, PM-012, PM-015, PM-028, PM-029, PM-030, PM-032, PM-033 |
| documents | 12 | PM-001, PM-005, PM-016, PM-017, PM-050, PM-051, PM-054, PM-059 |
| Support / Customer Inbox | 7 | CW-001, CW-002, CW-003, CW-004, CW-009, CW-011, CW-018 |
| modules/projects | 6 | PL-002, PL-004, PL-006, PL-008, PL-017, PL-157 |
| search | 5 | MS-002, MS-037, MS-039, MS-064, MS-093 |
| permissions | 5 | PM-093, PM-094, PM-095, PM-096, PM-149 |
| feedback | 2 | FB-001, FB-234 |
| workspaces | 2 | PM-092, PL-001 |
| auth | 2 | PM-115, MT-065 |
| database | 2 | PM-135, PM-151 |
| marketing | 2 | MT-025, MT-112 |
| none | 2 | MT-102, MT-105 |
| Platform / API | 2 | CW-112, NV-057 |
| Platform / Auth | 2 | CW-115, CW-131 |
| Automation / Workflow | 2 | NV-002, NV-005 |
| Notifications / In-app | 2 | NV-023, NV-035 |
| Identity / Access | 2 | NV-069, NV-072 |
| notifications | 1 | PM-116 |
| jobs | 1 | PM-124 |
| deployment | 1 | PM-137 |
| API | 1 | PM-152 |
| web | 1 | PM-153 |
| projects | 1 | PL-003 |
| modules/search | 1 | PL-038 |
| projects / permissions | 1 | PL-040 |
| adapters | 1 | PL-043 |
| core/auth | 1 | PL-053 |
| docs/research | 1 | PL-158 |
| Marketing / Segments | 1 | MT-008 |
| Marketing / Email Templates | 1 | MT-012 |
| Marketing / Broadcast Email | 1 | MT-013 |
| email_campaigns | 1 | MT-019 |
| Marketing / Campaign Types & Scheduling | 1 | MT-026 |
| Marketing / Campaign Builder | 1 | MT-027 |
| Marketing / Campaign Sources | 1 | MT-028 |
| api_resources | 1 | MT-072 |
| contacts | 1 | MT-113 |
| events | 1 | MT-115 |
| CRM / Contacts | 1 | CW-014 |
| Customer Support / Private Notes | 1 | CW-019 |
| Customer Support / Conversation Search | 1 | CW-030 |
| Platform / Events | 1 | CW-110 |
| Platform / Workspaces | 1 | CW-129 |
| Platform / Permissions | 1 | CW-137 |
| Notifications / Multi-channel Delivery | 1 | NV-001 |
| Notifications / Workflow Channel Steps | 1 | NV-007 |
| Identity / Notifications | 1 | NV-030 |
| Notifications / Layered Preferences | 1 | NV-032 |
| Notifications / Inbox Preferences UI | 1 | NV-039 |
| Workspace / Configuration | 1 | NV-068 |
| Platform / Data | 1 | NV-082 |
| Platform / Legal boundary | 1 | NV-084 |
| Workflow / Outreach approval | 1 | SB-020 |
| Auth / Sessions | 1 | SB-060 |
| API security | 1 | SB-061 |
| Agent center / Permissions | 1 | SB-062 |
| Database | 1 | SB-069 |

Next actions (from Remaining work) for the highest-value rows:

| ID | Source | Feature | Next action / remaining work |
| --- | --- | --- | --- |
| FB-001 | Formbricks | Free and open source surveying platform (Open Source Qualtrics Alterna | None; this is a clean-room local feedback recorder with no distribution or external invitations. |
| FB-234 | Formbricks | Exclude all EE capabilities from the default install | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| MS-002 | Meilisearch | Full-text search | Keep the clean-room SQL equivalent; document that it is substring matching, not an engine index or relevance ranking |
| MS-037 | Meilisearch | Multi-search | One SQL query set substitutes for multi-index requests; document that indexes are logical result types |
| MS-039 | Meilisearch | RESTful search API | NOVARA exposes GET only through its own API; no engine-compatible route or key header is claimed |
| MS-064 | Meilisearch | Tenant tokens and multi-tenancy | Server-side workspace filtering substitutes for signed engine tokens; no token issuance is claimed |
| MS-093 | Meilisearch | Enterprise Edition entitlement guard and BUSL terms | Exclude all files labelled Enterprise Edition and keep the adapter clean-room; no source copying |
| PM-001 | Papermark | Open-source DocSend alternative | None for this clean-room metadata boundary; NOVARA never uploads, stores or serves file bytes by design. |
| PM-002 | Papermark | Document upload with presigned upload URL | None for the local acceptance criteria; no hosted S3/conversion/identity provider is claimed. |
| PM-005 | Papermark | Document metadata creation | Wire to a real upload flow; keep spoofed `workspace_id`/`uploaded_by` rejection |
| PM-012 | Papermark | PDF sharing and preview | None for the local acceptance criteria; no hosted S3/conversion/identity provider is claimed. |
| PM-015 | Papermark | Blob storage and S3-compatible backend | None for the local acceptance criteria; no hosted S3/conversion/identity provider is claimed. |

## Cycle 2 — priority P1 (218 features)

| Module area | Rows | Representative IDs |
| --- | --- | --- |
| documents | 31 | PM-004, PM-006, PM-008, PM-009, PM-011, PM-019, PM-022, PM-026 |
| none | 21 | GB-001, GB-002, GB-003, GB-004, GB-005, GB-006, GB-008, GB-009 |
| none found | 10 | PL-009, PL-010, PL-011, PL-012, PL-015, PL-022, PL-027, PL-030 |
| analytics | 8 | GB-110, GB-111, GB-112, GB-113, GB-114, GB-115, GB-116, PM-090 |
| search | 7 | MS-006, MS-011, MS-014, MS-015, MS-028, MS-062, MS-065 |
| Marketing skills reference library | 7 | MK-001, MK-005, MK-015, MK-017, MK-018, MK-039, MK-048 |
| support | 5 | PM-097, CW-023, CW-048, CW-075, CW-108 |
| integrations | 4 | MS-063, GB-117, PM-117, MT-051 |
| Projects / Clean-room Extensions | 4 | PL-019, PL-028, PL-116, PL-117 |
| contacts | 4 | MT-007, MT-011, MT-035, MT-122 |
| Platform / Auth | 3 | GB-064, CW-118, CW-133 |
| API | 3 | PM-141, PM-142, PM-146 |
| core/tasks | 3 | PL-005, PL-007, PL-026 |
| Automation / Workflow | 3 | NV-003, NV-008, NV-018 |
| Topics / Notifications | 3 | NV-004, NV-045, NV-046 |
| Outreach safety / Compliance | 3 | SB-030, SB-031, SB-079 |
| operations | 2 | MS-055, MS-058 |
| security | 2 | PM-107, PM-156 |
| jobs | 2 | PM-123, MT-069 |
| projects | 2 | PL-021, PL-042 |
| core/events | 2 | PL-029, PL-079 |
| api_keys | 2 | PL-045, PL-070 |
| core/security | 2 | PL-049, PL-057 |
| Platform / Jobs | 2 | PL-071, CW-111 |
| Marketing / Channels | 2 | MT-045, MT-046 |
| Analytics / Reporting | 2 | CW-093, CW-095 |
| Feedback / CSAT | 2 | CW-100, CW-102 |
| Jobs / Workflow | 2 | NV-010, NV-011 |
| Notifications / Workflow | 2 | NV-012, NV-014 |
| Notifications / Multi-channel Delivery | 2 | NV-020, NV-021 |
| Notifications / UI | 2 | NV-033, NV-034 |
| Operations / Audit | 2 | NV-048, NV-106 |
| Workflow / Outreach drafts | 2 | SB-018, SB-021 |
| Platform / API | 1 | GB-059 |
| Feature flags / REST API v2 | 1 | GB-060 |
| Platform / Workspaces | 1 | GB-063 |
| Feature flags / Document store | 1 | GB-087 |
| notifications | 1 | PM-102 |
| workspaces | 1 | PM-121 |
| modules/projects | 1 | PL-018 |
| core/notifications | 1 | PL-033 |
| core/workspaces | 1 | PL-041 |
| core/api | 1 | PL-044 |
| core/auth | 1 | PL-055 |
| modules/jobs | 1 | PL-077 |
| project_intake | 1 | PL-088 |
| core/membership | 1 | PL-105 |
| Platform / Migrations | 1 | PL-147 |
| Platform / Database | 1 | PL-148 |
| marketing | 1 | MT-001 |
| modules | 1 | MT-003 |
| Marketing / Tokens | 1 | MT-016 |
| Marketing / Forms | 1 | MT-030 |
| leads | 1 | MT-033 |
| Marketing / SMS | 1 | MT-042 |
| marketing, analytics | 1 | MT-047 |
| events, integrations | 1 | MT-050 |
| core | 1 | MT-066 |
| events | 1 | MT-070 |
| database | 1 | MT-079 |
| tests | 1 | MT-089 |
| auth | 1 | MT-093 |
| Marketing / Compliance | 1 | MT-107 |
| auth, integrations | 1 | MT-114 |
| analytics, marketing | 1 | MT-117 |
| Support / Teams | 1 | CW-005 |
| Support / Routing | 1 | CW-008 |
| Support / Labels | 1 | CW-012 |
| Support / Custom Attributes | 1 | CW-013 |
| CRM / Notes | 1 | CW-016 |
| Activity / Timeline | 1 | CW-017 |
| Support / Automation | 1 | CW-024 |
| Support / Customer Inbox | 1 | CW-028 |
| visitor_conversations | 1 | CW-035 |
| Support / Channels | 1 | CW-037 |
| Automation / Rules | 1 | CW-051 |
| Support / Help Centre | 1 | CW-086 |
| Notifications / In-App | 1 | CW-106 |
| Platform / Testing | 1 | CW-142 |
| Platform / Data | 1 | CW-158 |
| Platform / Security | 1 | CW-166 |
| Integrations / Adapters | 1 | NV-025 |
| Security / Notifications | 1 | NV-042 |
| Jobs / Notifications | 1 | NV-051 |
| Operations / Notifications | 1 | NV-052 |
| Jobs / Delivery | 1 | NV-081 |
| Notifications / Records | 1 | NV-085 |
| Notifications / Real-time | 1 | NV-089 |
| Notifications / Content | 1 | NV-099 |
| CRM / Leads (manual only) | 1 | SB-002 |
| CRM / Contacts (manual only) | 1 | SB-004 |
| CRM / Leads | 1 | SB-014 |
| Workflow / Outreach approval | 1 | SB-024 |
| Adapters (local mock only) | 1 | SB-025 |
| Shared event spine / Operations | 1 | SB-035 |
| Agent center | 1 | SB-038 |
| Adapters / Security | 1 | SB-042 |
| Web client | 1 | SB-051 |

Next actions (from Remaining work) for the highest-value rows:

| ID | Source | Feature | Next action / remaining work |
| --- | --- | --- | --- |
| MS-006 | Meilisearch | Filtering | None; acceptance criteria met and evidenced. |
| MS-011 | Meilisearch | Built-in ranking rules | Replace engine relevance with explicit deterministic type/title ordering; document that no relevance score is computed |
| MS-014 | Meilisearch | Searchable attributes | Hardcoded per-type field sets substitute for per-index settings; document that fields are not runtime-configurable |
| MS-015 | Meilisearch | Displayed attributes / `attributesToRetrieve` | Fixed projection substitutes for configurable displayed attributes; no arbitrary field selection |
| MS-028 | Meilisearch | Pagination | None; acceptance criteria met and evidenced. |
| MS-055 | Meilisearch | Statistics endpoints | NOVARA counts are computed from real rows, never cached engine estimates; no engine stats endpoint is claimed |
| MS-058 | Meilisearch | Backups: snapshots and dumps | NOVARA backup and restore protects its own store, not an engine dump |
| MS-062 | Meilisearch | Master key bootstrap | None; acceptance criteria met and evidenced. |
| MS-063 | Meilisearch | API keys with action and index scopes | None; acceptance criteria met and evidenced. |
| MS-065 | Meilisearch | Sanitizing search results | None; acceptance criteria met and evidenced. |
| GB-001 | GrowthBook | Feature keys | None; acceptance criteria met and evidenced. |
| GB-002 | GrowthBook | Feature state and kill switch | None; acceptance criteria met and evidenced. |

## Cycle 3 — priority P2 (576 features)

| Module area | Rows | Representative IDs |
| --- | --- | --- |
| Feedback / Surveys | 94 | FB-002, FB-003, FB-004, FB-005, FB-006, FB-008, FB-009, FB-010 |
| feedback | 53 | FB-007, FB-020, FB-024, FB-025, FB-029, FB-031, FB-065, FB-076 |
| none found | 46 | PL-034, PL-046, PL-047, PL-052, PL-054, PL-058, PL-059, PL-060 |
| Feature flags / Experimentation | 35 | GB-007, GB-012, GB-013, GB-014, GB-020, GB-021, GB-022, GB-023 |
| documents | 33 | FB-164, PM-003, PM-007, PM-010, PM-013, PM-014, PM-018, PM-020 |
| search | 26 | MS-003, MS-004, MS-005, MS-007, MS-008, MS-009, MS-010, MS-012 |
| none | 23 | GB-033, GB-046, GB-047, GB-050, GB-054, GB-088, GB-089, GB-090 |
| integrations | 22 | FB-108, FB-109, FB-110, FB-111, FB-112, FB-113, FB-114, FB-115 |
| notifications | 21 | PM-140, NV-006, NV-013, NV-017, NV-019, NV-026, NV-028, NV-031 |
| adapters | 16 | FB-131, FB-132, FB-133, FB-134, FB-135, FB-136, FB-137, FB-138 |
| operations | 13 | FB-172, FB-173, FB-174, FB-175, FB-176, FB-178, FB-181, FB-182 |
| Projects / Work-item planning | 12 | PL-013, PL-014, PL-016, PL-020, PL-023, PL-024, PL-025, PL-035 |
| jobs | 8 | FB-160, FB-161, FB-165, FB-171, PM-129, PM-132, PM-133, MT-067 |
| Plane / work collaboration and API governance | 8 | PL-031, PL-032, PL-039, PL-048, PL-050, PL-051, PL-130, PL-132 |
| Support / Conversation operations | 8 | CW-006, CW-010, CW-020, CW-021, CW-025, CW-029, CW-052, CW-056 |
| Chatwoot / support reporting | 8 | CW-096, CW-097, CW-098, CW-099, CW-101, CW-104, CW-114, CW-117 |
| analytics | 7 | FB-103, FB-106, FB-107, FB-148, FB-170, FB-188, MS-098 |
| Sales / Engagement governance | 7 | SB-008, SB-009, SB-010, SB-017, SB-022, SB-026, SB-055 |
| Support / Channels | 6 | CW-036, CW-038, CW-044, CW-078, CW-121, CW-160 |
| agents | 5 | FB-102, FB-124, FB-169, PM-098, PM-131 |
| automation | 4 | FB-189, FB-190, FB-191, PM-099 |
| auth | 4 | PM-108, PM-111, PM-114, PM-145 |
| Mautic / marketing content | 4 | MT-009, MT-029, MT-032, MT-048 |
| Marketing / Email engagement | 4 | MT-014, MT-017, MT-018, MT-020 |
| Projects / Wiki pages | 3 | PL-096, PL-098, PL-102 |
| Platform / Configuration | 3 | CW-151, CW-163, NV-097 |
| Agent center (configuration only) | 3 | SB-039, SB-040, SB-041 |
| modules/jobs | 2 | PL-072, PL-087 |
| modules/automation | 2 | PL-080, PL-135 |
| Platform / Testing | 2 | CW-143, NV-119 |
| Platform / Data | 2 | CW-153, NV-096 |
| Notifications / Multi-channel Delivery | 2 | NV-022, NV-024 |
| Identity / Access | 2 | NV-070, NV-088 |
| Notifications / Content | 2 | NV-075, NV-100 |
| Feedback / Survey Responses | 1 | FB-087 |
| Feedback / Survey Detail | 1 | FB-088 |
| Feedback / Survey Audit Trail | 1 | FB-089 |
| Feedback / Survey Isolation | 1 | FB-090 |
| Feedback / Backup & Restore | 1 | FB-179 |
| web design | 1 | PM-154 |
| Plane / Email Checks | 1 | PL-056 |
| core/membership | 1 | PL-085 |
| core/account | 1 | PL-108 |
| core/dashboard | 1 | PL-144 |
| core/testing | 1 | PL-146 |
| contacts | 1 | MT-010 |
| marketing | 1 | MT-049 |
| api | 1 | MT-082 |
| web | 1 | MT-083 |
| events, marketing | 1 | MT-121 |
| portability | 1 | MT-123 |
| CRM / Companies | 1 | CW-015 |
| Support / Attachments | 1 | CW-031 |
| Support / API | 1 | CW-049 |
| Platform / Agents | 1 | CW-074 |
| CRM / Contacts | 1 | CW-076 |
| CRM / API | 1 | CW-077 |
| Platform / I18n | 1 | CW-083 |
| Support / Help Centre | 1 | CW-087 |
| Analytics / Reporting | 1 | CW-094 |
| Platform / Permissions | 1 | CW-130 |
| Platform / Auth | 1 | CW-132 |
| Platform / Compliance | 1 | CW-139 |
| Platform / Realtime | 1 | CW-141 |
| Search / Infrastructure | 1 | CW-156 |
| Platform / Security | 1 | CW-162 |
| Support / Notifications | 1 | NV-029 |
| Topics / UI | 1 | NV-047 |
| Notifications / Delivery Tracking | 1 | NV-049 |
| Operations / Analytics | 1 | NV-053 |
| Workspace / Configuration | 1 | NV-066 |
| Platform / Deployment | 1 | NV-080 |
| Platform / UI | 1 | NV-090 |
| Platform / API | 1 | NV-102 |
| Jobs / Workflow | 1 | NV-105 |
| Security / Agents | 1 | NV-113 |
| Marketing Skills → ad creative brief and review template | 1 | MK-002 |
| Marketing Skills → paid campaign plan/diagnosis workflow | 1 | MK-003 |
| Marketing Skills → AI search visibility audit workflow | 1 | MK-004 |
| Marketing Skills → channel attribution review workflow | 1 | MK-007 |
| Marketing Skills → retention playbook workflow | 1 | MK-008 |
| Marketing Skills → approved cold-outreach draft generator | 1 | MK-010 |
| Marketing Skills → dated competitor profile workflow | 1 | MK-012 |
| Marketing Skills → comparison-page audit template | 1 | MK-013 |
| Marketing Skills → editorial calendar / topic-cluster planner | 1 | MK-014 |
| Marketing Skills → point-edit copy tool | 1 | MK-016 |
| Marketing Skills → interview/synthesis workflow | 1 | MK-019 |
| Marketing Skills → lifecycle email sequence builder | 1 | MK-021 |
| Marketing Skills → launch checklist / GTM planner | 1 | MK-026 |
| Marketing Skills → backlink opportunity planner | 1 | MK-028 |
| Marketing Skills → idea backlog generator | 1 | MK-030 |
| Marketing Skills → scheduled marketing agent loop | 1 | MK-031 |
| Marketing Skills → go-to-market plan builder | 1 | MK-032 |
| Marketing Skills → persuasion ethics review template | 1 | MK-033 |
| Marketing Skills → activation checklist workflow | 1 | MK-035 |
| Marketing Skills → pricing and packaging workbook | 1 | MK-038 |
| Marketing Skills → scaled page-set evaluator | 1 | MK-040 |
| Marketing Skills → prospect research workflow | 1 | MK-041 |
| Marketing Skills → referral program planner | 1 | MK-043 |
| Marketing Skills → growth teardown workflow | 1 | MK-044 |
| Marketing Skills → lifecycle/stage/routing design workflow | 1 | MK-045 |
| Marketing Skills → battle card and sales collateral generator | 1 | MK-046 |
| Marketing Skills → JSON-LD validation workflow | 1 | MK-047 |
| Marketing Skills → signup flow audit workflow | 1 | MK-049 |
| Marketing Skills → site hierarchy and URL planner | 1 | MK-050 |
| Marketing Skills → organic social calendar and draft generator | 1 | MK-052 |
| CRM / Companies (manual record only) | 1 | SB-005 |
| Shared event spine | 1 | SB-011 |
| Sellbird / Company Records | 1 | SB-013 |
| Marketing / Campaigns | 1 | SB-016 |
| Integrations (configuration only) | 1 | SB-027 |
| Support (tickets are a different object) | 1 | SB-033 |
| Operations | 1 | SB-036 |
| Jobs / Operations | 1 | SB-047 |
| Jobs (stale recovery only) | 1 | SB-049 |
| Multiple NOVARA modules | 1 | SB-052 |
| Auth / Workspace bootstrap | 1 | SB-053 |
| Settings / Integrations | 1 | SB-054 |
| Database migrations | 1 | SB-070 |
| Agent center / Adapters | 1 | SB-080 |

Next actions (from Remaining work) for the highest-value rows:

| ID | Source | Feature | Next action / remaining work |
| --- | --- | --- | --- |
| FB-002 | Formbricks | In-app surveys | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-003 | Formbricks | Website surveys | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-004 | Formbricks | Link surveys | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-005 | Formbricks | Email surveys | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-006 | Formbricks | Embedded surveys (iframe and email snippets) | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-007 | Formbricks | SurveyType enum (link, app) | Add an explicit survey type discriminator with validation, migration, UI and named tests. |
| FB-008 | Formbricks | displayOptions enum (displayOnce, displayMultiple, displaySome, respon | No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build. |
| FB-009 | Formbricks | Survey visibility modes (workspace, restricted) | No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build. |
| FB-010 | Formbricks | No-code survey editor | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-011 | Formbricks | Best-practice templates | No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build. |
| FB-012 | Formbricks | NPS preset / template claim | No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build. |
| FB-013 | Formbricks | CSAT preset / template claim | No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build. |

## Cycle 4 — priority P3 (583 features)

| Module area | Rows | Representative IDs |
| --- | --- | --- |
| none | 210 | GB-040, GB-043, GB-044, GB-045, GB-051, GB-052, GB-053, GB-068 |
| search | 47 | MS-001, MS-013, MS-017, MS-018, MS-019, MS-020, MS-022, MS-023 |
| none found | 45 | PL-061, PL-065, PL-066, PL-067, PL-068, PL-073, PL-075, PL-082 |
| feedback | 20 | FB-205, FB-206, FB-207, FB-208, FB-209, FB-210, FB-211, FB-212 |
| Experiments / Exposure adapters | 14 | GB-134, GB-135, GB-136, GB-137, GB-138, GB-139, GB-140, GB-141 |
| GrowthBook / advanced feature-flag governance | 14 | GB-183, GB-196, GB-206, GB-209, GB-210, GB-211, GB-224, GB-225 |
| documents | 11 | PM-024, PM-025, PM-027, PM-037, PM-038, PM-043, PM-058, PM-077 |
| AI / Captain | 10 | CW-061, CW-062, CW-063, CW-064, CW-065, CW-066, CW-067, CW-068 |
| operations | 8 | FB-225, FB-226, FB-227, FB-228, MS-060, MS-085, MS-087, MS-092 |
| GrowthBook / advanced experimentation statistics | 8 | GB-187, GB-188, GB-189, GB-214, GB-215, GB-217, GB-222, GB-237 |
| Support / Channels | 8 | CW-039, CW-040, CW-041, CW-042, CW-043, CW-045, CW-082, CW-090 |
| Feature flags / Experimentation | 6 | GB-024, GB-027, GB-039, GB-041, GB-048, GB-101 |
| Notifications / UI | 6 | NV-037, NV-041, NV-043, NV-059, NV-079, NV-101 |
| Projects / Wiki pages | 5 | PL-097, PL-099, PL-100, PL-101, PL-103 |
| Marketing / Email engagement | 5 | MT-015, MT-021, MT-022, MT-023, MT-024 |
| Support / Conversation operations | 5 | CW-022, CW-032, CW-053, CW-054, CW-055 |
| Sales / Engagement governance | 5 | SB-012, SB-015, SB-019, SB-023, SB-028 |
| jobs | 4 | MS-050, MS-051, PM-130, PM-134 |
| Platform / Operations | 4 | CW-116, CW-127, CW-145, CW-165 |
| Platform / Auth | 4 | CW-119, CW-134, CW-135, CW-136 |
| Platform / Deployment | 4 | CW-146, CW-147, CW-148, CW-149 |
| notifications | 4 | NV-009, NV-015, NV-027, NV-118 |
| agents | 3 | MS-071, PM-101, PM-144 |
| auth | 3 | PM-109, PM-112, PM-113 |
| deployment | 3 | PM-136, PM-138, PM-139 |
| Mautic / marketing content | 3 | MT-031, MT-036, MT-037 |
| Support / SLA | 3 | CW-057, CW-058, CW-059 |
| Platform / Tooling | 3 | CW-150, NV-061, NV-117 |
| Platform / Commercial | 3 | CW-167, NV-077, NV-093 |
| Platform / Compliance | 3 | CW-168, NV-078, NV-116 |
| integrations | 2 | MS-068, PM-119 |
| core API | 2 | MS-086, MS-101 |
| analytics | 2 | PM-120, MT-130 |
| tooling | 2 | PM-143, PM-147 |
| tests | 2 | MT-090, MT-091 |
| Support / UX | 2 | CW-026, CW-027 |
| Support / Voice | 2 | CW-046, CW-047 |
| Support / Reporting | 2 | CW-060, CW-089 |
| Support / Chatbots | 2 | CW-072, CW-073 |
| Support / Campaigns | 2 | CW-079, CW-080 |
| Support / Help Centre | 2 | CW-088, CW-091 |
| Feedback / CSAT | 2 | CW-103, CW-105 |
| Platform / API | 2 | CW-113, NV-058 |
| Platform / Data | 2 | CW-154, CW-159 |
| Platform / Storage | 2 | CW-157, NV-083 |
| Agents / Notifications | 2 | NV-062, NV-065 |
| Support / UI | 2 | NV-064, NV-111 |
| Workspace / Configuration | 2 | NV-067, NV-076 |
| Agents / SDK | 2 | NV-110, NV-114 |
| Operations | 2 | SB-056, SB-058 |
| Database | 2 | SB-071, SB-072 |
| adapters | 1 | FB-229 |
| billing | 1 | PM-103 |
| platform | 1 | PM-122 |
| compliance | 1 | PM-155 |
| web | 1 | MT-129 |
| Support / Routing | 1 | CW-007 |
| Support / Delivery | 1 | CW-033 |
| Support / Extensions | 1 | CW-034 |
| Platform / Mobile | 1 | CW-050 |
| AI / Monitors | 1 | CW-070 |
| Support / White Label | 1 | CW-081 |
| Platform / I18n | 1 | CW-084 |
| Support / Translation | 1 | CW-085 |
| Support / API | 1 | CW-092 |
| Notifications / Push | 1 | CW-107 |
| Integrations / Hooks | 1 | CW-109 |
| Platform / SDK | 1 | CW-120 |
| Platform / Libraries | 1 | CW-122 |
| Integrations / Chat | 1 | CW-123 |
| Integrations / Billing | 1 | CW-124 |
| Integrations / Issues | 1 | CW-125 |
| Integrations / Commerce | 1 | CW-126 |
| Platform / CLI | 1 | CW-128 |
| Platform / Admin | 1 | CW-138 |
| Platform / Permissions | 1 | CW-140 |
| Platform / Testing | 1 | CW-144 |
| Platform / Configuration | 1 | CW-152 |
| Platform / Runtime | 1 | CW-155 |
| Platform / Delivery | 1 | CW-161 |
| Platform / Enterprise | 1 | CW-164 |
| Notifications / Integration | 1 | NV-016 |
| Notifications / Delivery Tracking | 1 | NV-050 |
| Integrations / Webhooks | 1 | NV-055 |
| Automation / Workflow | 1 | NV-060 |
| Agents / Support | 1 | NV-063 |
| Notifications / Content | 1 | NV-074 |
| Agents / MCP | 1 | NV-091 |
| Agents / Events | 1 | NV-092 |
| Notifications / SDK | 1 | NV-094 |
| Integrations / Adapters | 1 | NV-095 |
| Platform / Observability | 1 | NV-098 |
| Agents / API | 1 | NV-108 |
| Agents / Platform | 1 | NV-109 |
| Agents / UI | 1 | NV-112 |
| Operations / Agents | 1 | NV-115 |
| Marketing Skills → app listing audit template | 1 | MK-006 |
| Marketing Skills → partner campaign planner | 1 | MK-009 |
| Marketing Skills → community plan template | 1 | MK-011 |
| Marketing Skills → directory submission tracker | 1 | MK-020 |
| Marketing Skills → event plan template | 1 | MK-022 |
| Marketing Skills → free-tool idea evaluator | 1 | MK-023 |
| Marketing Skills → AI-assisted marketing image brief/generator | 1 | MK-024 |
| Marketing Skills → creator partnership planner | 1 | MK-025 |
| Marketing Skills → lead-magnet planner | 1 | MK-027 |
| Marketing Skills → multi-perspective decision agent | 1 | MK-029 |
| Marketing Skills → offer design template | 1 | MK-034 |
| Marketing Skills → in-app upgrade moment review | 1 | MK-036 |
| Marketing Skills → popup plan/review template | 1 | MK-037 |
| Marketing Skills → press pitch and response planner | 1 | MK-042 |
| Marketing Skills → SMS and WhatsApp draft/compliance review | 1 | MK-051 |
| Marketing Skills → AI-assisted video production plan | 1 | MK-053 |
| Feedback (surveys are a different object) | 1 | SB-034 |
| Agent center (governor only) | 1 | SB-045 |
| Agent center | 1 | SB-046 |
| Operations / Dashboard | 1 | SB-057 |
| API framework | 1 | SB-059 |
| Module registry | 1 | SB-065 |
| Deployment | 1 | SB-067 |
| Adapters (local mock only) | 1 | SB-077 |
| Test suite | 1 | SB-078 |

Next actions (from Remaining work) for the highest-value rows:

| ID | Source | Feature | Next action / remaining work |
| --- | --- | --- | --- |
| FB-205 | Formbricks | Enterprise: AI translation of surveys | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-206 | Formbricks | Enterprise: Enterprise analysis capability | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-207 | Formbricks | Enterprise: Comprehensive audit logging | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-208 | Formbricks | Enterprise: Enterprise authentication helpers | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-209 | Formbricks | Enterprise: Enterprise billing | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-210 | Formbricks | Enterprise: Enterprise contact extras / contacts API guard | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-211 | Formbricks | Enterprise: Enterprise creative extras | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-212 | Formbricks | Enterprise: Data retention controls | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-213 | Formbricks | Enterprise: Feedback directory | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-214 | Formbricks | Enterprise: Enterprise license enforcement | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-215 | Formbricks | Enterprise: Enterprise mailing | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |
| FB-216 | Formbricks | Enterprise: Quota enforcement | Exclude all EE code. Implement a lawful clean-room equivalent natively where in scope, otherwise record an explicit out-of-scope decision. No entitlement, no redistribution. |

## Cycle exit criteria

1. Every P0/P1 row has either a passing named test plus browser evidence (`VERIFIED_COMPLETE`) or an explicit accounting status with a lawful alternative (restricted/blocked/replaced).
2. No row is reported complete from a menu item, table, 200 response, placeholder or local mock.
3. Governance holds: local/no-send behaviour, light theme only, no mandatory paid service, no outbound message without explicit approval.
4. The completion dashboard percentages are recomputed from the CSV after each cycle.

## Blocked lanes (cannot be closed by code alone)

- 135 rows need credentials, live provider verification, Docker/PostgreSQL or unavailable infrastructure. Keep them blocked and honest; do not claim succeeded delivery.
- 210 rows need a lawful clean-room design before any implementation; see `LICENSING_EXCEPTION_REGISTER.md`.
- NOVARA licence/trademark/domain decision (BLOCKERS B-03) remains open and gates distribution, not local implementation.
