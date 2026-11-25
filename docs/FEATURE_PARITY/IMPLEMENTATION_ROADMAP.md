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

- 1418 `VERIFIED_COMPLETE`, 70 `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION`, 0 `IMPLEMENTED_UNVERIFIED`, 0 `BACKEND_ONLY`.
- Phase 4 UI gap closure (2026-11-22): Universal Search and Customer Inbox (`docs/evidence/phase4-browser-20261122.md`), then Campaign Studio, Sales pipeline and Feedback Studio (`docs/evidence/phase4-browser-three-views-20261122.md`). These correspond to audit gaps #1–#5 in `docs/PHASE_4_MODULE_AUDIT.md` and are now closed in code.

## Cycle 1 — priority P0 (111 features)

| Module area | Rows | Representative IDs |
| --- | --- | --- |
| Documents / Storage / Sharing / Analytics | 14 | PM-002, PM-012, PM-015, PM-028, PM-029, PM-030, PM-032, PM-033 |
| documents | 8 | PM-001, PM-005, PM-016, PM-017, PM-051, PM-054, PM-073, PM-088 |
| Support / Customer Inbox | 7 | CW-001, CW-002, CW-003, CW-004, CW-009, CW-011, CW-018 |
| modules/projects | 6 | PL-002, PL-004, PL-006, PL-008, PL-017, PL-157 |
| out_of_scope_boundary | 4 | FB-234, MS-093, PM-094, NV-084 |
| search | 4 | MS-002, MS-037, MS-039, MS-064 |
| Papermark / data-room governance (clean-room) | 4 | PM-050, PM-059, PM-061, PM-064 |
| permissions | 3 | PM-093, PM-095, PM-149 |
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
| feedback | 1 | FB-001 |
| parity_capabilities | 1 | PM-096 |
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
| Workflow / Outreach approval | 1 | SB-020 |
| Auth / Sessions | 1 | SB-060 |
| API security | 1 | SB-061 |
| Agent center / Permissions | 1 | SB-062 |
| Database | 1 | SB-069 |

Next actions (from Remaining work) for the highest-value rows:

| ID | Source | Feature | Next action / remaining work |
| --- | --- | --- | --- |
| FB-001 | Formbricks | Free and open source surveying platform (Open Source Qualtrics Alterna | None; this is a clean-room local feedback recorder with no distribution or external invitations. |
| FB-234 | Formbricks | Exclude all EE capabilities from the default install | None for this row. |
| MS-002 | Meilisearch | Full-text search | Keep the clean-room SQL equivalent; document that it is substring matching, not an engine index or relevance ranking |
| MS-037 | Meilisearch | Multi-search | One SQL query set substitutes for multi-index requests; document that indexes are logical result types |
| MS-039 | Meilisearch | RESTful search API | NOVARA exposes GET only through its own API; no engine-compatible route or key header is claimed |
| MS-064 | Meilisearch | Tenant tokens and multi-tenancy | Server-side workspace filtering substitutes for signed engine tokens; no token issuance is claimed |
| MS-093 | Meilisearch | Enterprise Edition entitlement guard and BUSL terms | None for this row. |
| PM-001 | Papermark | Open-source DocSend alternative | None for this clean-room metadata boundary; NOVARA never uploads, stores or serves file bytes by design. |
| PM-002 | Papermark | Document upload with presigned upload URL | None for the local acceptance criteria; no hosted S3/conversion/identity provider is claimed. |
| PM-005 | Papermark | Document metadata creation | Wire to a real upload flow; keep spoofed `workspace_id`/`uploaded_by` rejection |
| PM-012 | Papermark | PDF sharing and preview | None for the local acceptance criteria; no hosted S3/conversion/identity provider is claimed. |
| PM-015 | Papermark | Blob storage and S3-compatible backend | None for the local acceptance criteria; no hosted S3/conversion/identity provider is claimed. |

## Cycle 2 — priority P1 (218 features)

| Module area | Rows | Representative IDs |
| --- | --- | --- |
| documents | 26 | PM-004, PM-006, PM-008, PM-009, PM-011, PM-019, PM-022, PM-026 |
| none | 20 | GB-001, GB-002, GB-003, GB-004, GB-005, GB-006, GB-008, GB-009 |
| none found | 9 | PL-009, PL-010, PL-011, PL-012, PL-015, PL-022, PL-027, PL-030 |
| analytics | 8 | GB-110, GB-111, GB-112, GB-113, GB-114, GB-115, GB-116, PM-090 |
| search | 7 | MS-006, MS-011, MS-014, MS-015, MS-028, MS-062, MS-065 |
| Marketing skills reference library | 7 | MK-001, MK-005, MK-015, MK-017, MK-018, MK-039, MK-048 |
| parity_capabilities | 5 | PM-097, PM-102, PM-105, PM-107, MT-051 |
| external_dependency_boundary | 5 | CW-037, SB-002, SB-004, SB-007, SB-025 |
| Papermark / data-room governance (clean-room) | 4 | PM-057, PM-060, PM-062, PM-065 |
| Projects / Clean-room Extensions | 4 | PL-019, PL-028, PL-116, PL-117 |
| contacts | 4 | MT-007, MT-011, MT-035, MT-122 |
| support | 4 | CW-023, CW-048, CW-075, CW-108 |
| integrations | 3 | MS-063, GB-117, PM-117 |
| Platform / Auth | 3 | GB-064, CW-118, CW-133 |
| API | 3 | PM-141, PM-142, PM-146 |
| core/tasks | 3 | PL-005, PL-007, PL-026 |
| Automation / Workflow | 3 | NV-003, NV-008, NV-018 |
| Topics / Notifications | 3 | NV-004, NV-045, NV-046 |
| Outreach safety / Compliance | 3 | SB-030, SB-031, SB-079 |
| operations | 2 | MS-055, MS-058 |
| jobs | 2 | PM-123, MT-069 |
| projects | 2 | PL-021, PL-042 |
| core/events | 2 | PL-029, PL-079 |
| api_keys | 2 | PL-045, PL-070 |
| core/security | 2 | PL-049, PL-057 |
| Platform / Jobs | 2 | PL-071, CW-111 |
| Marketing / Channels | 2 | MT-045, MT-046 |
| Novara / final local capability catalogue (clean-room) | 2 | MT-108, NV-020 |
| Analytics / Reporting | 2 | CW-093, CW-095 |
| Feedback / CSAT | 2 | CW-100, CW-102 |
| Jobs / Workflow | 2 | NV-010, NV-011 |
| Notifications / Workflow | 2 | NV-012, NV-014 |
| Notifications / UI | 2 | NV-033, NV-034 |
| Operations / Audit | 2 | NV-048, NV-106 |
| Workflow / Outreach drafts | 2 | SB-018, SB-021 |
| Platform / API | 1 | GB-059 |
| Feature flags / REST API v2 | 1 | GB-060 |
| Platform / Workspaces | 1 | GB-063 |
| Feature flags / Document store | 1 | GB-087 |
| workspaces | 1 | PM-121 |
| security | 1 | PM-156 |
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
| marketing_local_capabilities | 1 | MT-066 |
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
| Automation / Rules | 1 | CW-051 |
| Support / Help Centre | 1 | CW-086 |
| Notifications / In-App | 1 | CW-106 |
| Platform / Testing | 1 | CW-142 |
| Platform / Data | 1 | CW-158 |
| Platform / Security | 1 | CW-166 |
| no_claim_evidence_boundary | 1 | NV-021 |
| Integrations / Adapters | 1 | NV-025 |
| Security / Notifications | 1 | NV-042 |
| Jobs / Notifications | 1 | NV-051 |
| Operations / Notifications | 1 | NV-052 |
| Jobs / Delivery | 1 | NV-081 |
| Notifications / Records | 1 | NV-085 |
| Notifications / Real-time | 1 | NV-089 |
| Notifications / Content | 1 | NV-099 |
| CRM / Leads | 1 | SB-014 |
| Workflow / Outreach approval | 1 | SB-024 |
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
| parity_capabilities | 96 | FB-007, FB-020, FB-065, FB-086, FB-093, FB-104, FB-107, FB-108 |
| Feedback / Surveys | 94 | FB-002, FB-003, FB-004, FB-005, FB-006, FB-008, FB-009, FB-010 |
| Novara / final local capability catalogue (clean-room) | 62 | FB-076, FB-078, GB-090, GB-091, GB-103, GB-118, PM-013, PM-070 |
| external_dependency_boundary | 46 | FB-031, FB-077, FB-102, FB-103, FB-105, FB-106, FB-111, FB-112 |
| Feature flags / Experimentation | 35 | GB-007, GB-012, GB-013, GB-014, GB-020, GB-021, GB-022, GB-023 |
| marketing_skills | 30 | MK-002, MK-003, MK-004, MK-007, MK-008, MK-010, MK-012, MK-013 |
| notifications | 20 | NV-006, NV-013, NV-017, NV-019, NV-026, NV-028, NV-031, NV-036 |
| search | 17 | MS-004, MS-007, MS-008, MS-012, MS-016, MS-021, MS-025, MS-026 |
| feedback | 16 | FB-024, FB-025, FB-029, FB-085, FB-096, FB-097, FB-098, FB-099 |
| Projects / Work-item planning | 12 | PL-013, PL-014, PL-016, PL-020, PL-023, PL-024, PL-025, PL-035 |
| Formbricks / clean-room SDK replacement boundary | 11 | FB-132, FB-133, FB-134, FB-135, FB-136, FB-137, FB-138, FB-139 |
| no_claim_evidence_boundary | 10 | FB-193, CW-044, CW-156, NV-049, NV-075, SB-039, SB-040, SB-041 |
| marketing_local_capabilities | 10 | MT-002, MT-034, MT-041, MT-049, MT-064, MT-067, MT-073, MT-077 |
| extended_claim_boundary | 9 | MS-005, MS-009, MS-010, MS-059, MS-098, PM-067, NV-053, NV-066 |
| Plane / work collaboration and API governance | 8 | PL-031, PL-032, PL-039, PL-048, PL-050, PL-051, PL-130, PL-132 |
| project_governance | 8 | PL-034, PL-095, PL-106, PL-119, PL-120, PL-128, PL-129, PL-140 |
| Support / Conversation operations | 8 | CW-006, CW-010, CW-020, CW-021, CW-025, CW-029, CW-052, CW-056 |
| Chatwoot / support reporting | 8 | CW-096, CW-097, CW-098, CW-099, CW-101, CW-104, CW-114, CW-117 |
| documents | 7 | PM-007, PM-010, PM-018, PM-076, PM-083, PM-084, PM-085 |
| Sales / Engagement governance | 7 | SB-008, SB-009, SB-010, SB-017, SB-022, SB-026, SB-055 |
| Papermark / share-link presentation and hardening (clean-room) | 6 | PM-023, PM-035, PM-036, PM-044, PM-046, PM-071 |
| out_of_scope_boundary | 5 | FB-155, FB-156, PL-110, PL-111, PL-112 |
| Plane / local background-task ledger (clean-room) | 5 | PL-076, PL-078, PL-081, PL-083, PL-084 |
| plane_workspace_tools | 5 | PL-089, PL-091, PL-092, PL-138, PL-139 |
| access_governance | 5 | PL-124, PL-125, CW-130, CW-139, NV-070 |
| meilisearch_claim_boundary | 4 | MS-052, MS-066, MS-081, MS-082 |
| Mautic / marketing content | 4 | MT-009, MT-029, MT-032, MT-048 |
| Marketing / Email engagement | 4 | MT-014, MT-017, MT-018, MT-020 |
| Projects / Wiki pages | 3 | PL-096, PL-098, PL-102 |
| GrowthBook / clean-room SDK compatibility boundary | 2 | GB-148, GB-149 |
| Feedback / Survey Responses | 1 | FB-087 |
| Feedback / Survey Detail | 1 | FB-088 |
| Feedback / Survey Audit Trail | 1 | FB-089 |
| Feedback / Survey Isolation | 1 | FB-090 |
| adapters | 1 | FB-143 |
| Feedback / Backup & Restore | 1 | FB-179 |
| NOVARA / no-default-dependency boundary | 1 | MS-067 |
| Papermark / data-room governance (clean-room) | 1 | PM-066 |
| web design | 1 | PM-154 |
| Plane / Email Checks | 1 | PL-056 |
| plane_claim_boundary | 1 | PL-151 |
| integrations | 1 | MT-078 |
| api | 1 | MT-082 |
| CRM / API | 1 | CW-077 |
| Chatwoot / help-centre governance (clean-room) | 1 | CW-087 |
| Platform / Data | 1 | NV-096 |
| Platform / Testing | 1 | NV-119 |
| Shared event spine | 1 | SB-011 |
| Sellbird / Company Records | 1 | SB-013 |

Next actions (from Remaining work) for the highest-value rows:

| ID | Source | Feature | Next action / remaining work |
| --- | --- | --- | --- |
| FB-002 | Formbricks | In-app surveys | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-003 | Formbricks | Website surveys | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-004 | Formbricks | Link surveys | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-005 | Formbricks | Email surveys | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-006 | Formbricks | Embedded surveys (iframe and email snippets) | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-007 | Formbricks | SurveyType enum (link, app) | None for this row. |
| FB-008 | Formbricks | displayOptions enum (displayOnce, displayMultiple, displaySome, respon | No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build. |
| FB-009 | Formbricks | Survey visibility modes (workspace, restricted) | No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build. |
| FB-010 | Formbricks | No-code survey editor | No remaining work for the recorded local acceptance criteria. Formbricks-hosted workers, survey email delivery, tracking pixels, hosted widgets, external SDKs, MCP servers, agent t |
| FB-011 | Formbricks | Best-practice templates | No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build. |
| FB-012 | Formbricks | NPS preset / template claim | No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build. |
| FB-013 | Formbricks | CSAT preset / template claim | No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build. |

## Cycle 4 — priority P3 (583 features)

| Module area | Rows | Representative IDs |
| --- | --- | --- |
| Novara / final local capability catalogue (clean-room) | 84 | GB-068, GB-069, GB-070, GB-080, GB-086, GB-092, GB-093, GB-094 |
| ee_absence_boundary | 82 | GB-108, GB-109, GB-174, GB-175, GB-176, GB-177, GB-178, GB-179 |
| no_claim_evidence_boundary | 70 | MS-101, GB-194, GB-205, GB-213, GB-234, GB-239, GB-250, PL-075 |
| parity_capabilities | 48 | FB-229, GB-040, GB-043, GB-044, GB-045, GB-051, GB-052, GB-053 |
| external_dependency_boundary | 43 | FB-226, FB-227, FB-228, MS-084, MS-085, MS-086, MS-087, MS-099 |
| out_of_scope_boundary | 40 | FB-205, FB-206, FB-207, FB-208, FB-209, FB-210, FB-211, FB-212 |
| search | 29 | MS-001, MS-013, MS-017, MS-018, MS-019, MS-020, MS-022, MS-023 |
| extended_claim_boundary | 17 | MS-050, MS-051, MS-096, PM-136, PM-155, CW-119, NV-041, NV-055 |
| GrowthBook / clean-room SDK compatibility boundary (extended) | 16 | GB-158, GB-159, GB-160, GB-161, GB-162, GB-163, GB-164, GB-165 |
| marketing_skills | 16 | MK-006, MK-009, MK-011, MK-020, MK-022, MK-023, MK-024, MK-025 |
| Experiments / Exposure adapters | 14 | GB-134, GB-135, GB-136, GB-137, GB-138, GB-139, GB-140, GB-141 |
| GrowthBook / advanced feature-flag governance | 14 | GB-183, GB-196, GB-206, GB-209, GB-210, GB-211, GB-224, GB-225 |
| meilisearch_claim_boundary | 12 | MS-054, MS-060, MS-068, MS-069, MS-070, MS-071, MS-072, MS-073 |
| NOVARA / no-default-dependency boundary | 8 | MS-097, PL-068, PL-149, PL-150, CW-122, NV-058, NV-059, NV-094 |
| GrowthBook / clean-room SDK compatibility boundary | 8 | GB-150, GB-151, GB-152, GB-153, GB-154, GB-155, GB-156, GB-157 |
| GrowthBook / advanced experimentation statistics | 8 | GB-187, GB-188, GB-189, GB-214, GB-215, GB-217, GB-222, GB-237 |
| marketing_local_capabilities | 8 | MT-043, MT-056, MT-063, MT-071, MT-124, MT-126, MT-127, MT-130 |
| plane_claim_boundary | 7 | PL-067, PL-109, PL-133, PL-134, PL-153, PL-154, PL-156 |
| Chatwoot / help-centre governance (clean-room) | 7 | CW-066, CW-067, CW-088, CW-089, CW-090, CW-091, CW-092 |
| Feature flags / Experimentation | 6 | GB-024, GB-027, GB-039, GB-041, GB-048, GB-101 |
| documents | 5 | PM-024, PM-025, PM-027, PM-077, PM-091 |
| plane_workspace_tools | 5 | PL-093, PL-107, PL-137, PL-142, PL-145 |
| Projects / Wiki pages | 5 | PL-097, PL-099, PL-100, PL-101, PL-103 |
| Marketing / Email engagement | 5 | MT-015, MT-021, MT-022, MT-023, MT-024 |
| Support / Conversation operations | 5 | CW-022, CW-032, CW-053, CW-054, CW-055 |
| Sales / Engagement governance | 5 | SB-012, SB-015, SB-019, SB-023, SB-028 |
| notifications | 4 | NV-009, NV-015, NV-027, NV-118 |
| Plane / local background-task ledger (clean-room) | 3 | PL-073, PL-082, PL-086 |
| Mautic / marketing content | 3 | MT-031, MT-036, MT-037 |
| Papermark / share-link presentation and hardening (clean-room) | 2 | PM-037, PM-043 |
| Papermark / data-room governance (clean-room) | 1 | PM-058 |
| none | 1 | MT-106 |
| Platform / Operations | 1 | CW-116 |
| Platform / Runtime | 1 | CW-155 |

Next actions (from Remaining work) for the highest-value rows:

| ID | Source | Feature | Next action / remaining work |
| --- | --- | --- | --- |
| FB-205 | Formbricks | Enterprise: AI translation of surveys | None for this row. |
| FB-206 | Formbricks | Enterprise: Enterprise analysis capability | None for this row. |
| FB-207 | Formbricks | Enterprise: Comprehensive audit logging | None for this row. |
| FB-208 | Formbricks | Enterprise: Enterprise authentication helpers | None for this row. |
| FB-209 | Formbricks | Enterprise: Enterprise billing | None for this row. |
| FB-210 | Formbricks | Enterprise: Enterprise contact extras / contacts API guard | None for this row. |
| FB-211 | Formbricks | Enterprise: Enterprise creative extras | None for this row. |
| FB-212 | Formbricks | Enterprise: Data retention controls | None for this row. |
| FB-213 | Formbricks | Enterprise: Feedback directory | None for this row. |
| FB-214 | Formbricks | Enterprise: Enterprise license enforcement | None for this row. |
| FB-215 | Formbricks | Enterprise: Enterprise mailing | None for this row. |
| FB-216 | Formbricks | Enterprise: Quota enforcement | None for this row. |

## Cycle exit criteria

1. Every P0/P1 row has either a passing named test plus browser evidence (`VERIFIED_COMPLETE`) or an explicit accounting status with a lawful alternative (restricted/blocked/replaced).
2. No row is reported complete from a menu item, table, 200 response, placeholder or local mock.
3. Governance holds: local/no-send behaviour, light theme only, no mandatory paid service, no outbound message without explicit approval.
4. The completion dashboard percentages are recomputed from the CSV after each cycle.

## Blocked lanes (cannot be closed by code alone)

- 0 rows need credentials, live provider verification, Docker/PostgreSQL or unavailable infrastructure. Keep them blocked and honest; do not claim succeeded delivery.
- 0 rows need a lawful clean-room design before any implementation; see `LICENSING_EXCEPTION_REGISTER.md`.
- NOVARA licence/trademark/domain decision (BLOCKERS B-03) remains open and gates distribution, not local implementation.
