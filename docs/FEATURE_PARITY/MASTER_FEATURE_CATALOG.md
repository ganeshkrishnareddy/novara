# NOVARA master feature catalog

Single authoritative catalogue of every discovered feature across the ten source projects. **1488 permanent feature IDs** are registered here; an ID is never reused or renumbered. Full 21-column detail for every row is in `MASTER_FEATURE_MATRIX.csv`; the per-source evidence and coverage notes are in `SOURCES/`.

Contract: `00_INVENTORY_CONTRACT.md`. Licensing decisions: `docs/research/LICENSE_COMPLIANCE.md`. Intent: `docs/VISION.md`. Do not read a platform/Generic implementation (auth, workspaces, roles) as a claim that an upstream enterprise feature was copied — see the compatibility boundary in `LICENSING_EXCEPTION_REGISTER.md`.

## Status legend

| Status | Meaning |
| --- | --- |
| VERIFIED_COMPLETE | User-facing behaviour, persistence, permissions, validation and named test/browser evidence. |
| IMPLEMENTED_UNVERIFIED | Code and tests exist locally; no browser/E2E evidence captured. |
| PARTIALLY_IMPLEMENTED | A real slice exists; the remainder is listed in Remaining work. |
| BACKEND_ONLY | API/model exists, no UI route. |
| FRONTEND_ONLY | UI without its own backend (reserved; do not claim a shared API call as this). |
| NOT_IMPLEMENTED | No real implementation found. |
| EXTERNAL_DEPENDENCY_BLOCKED | Needs credentials, provider verification, Docker/PostgreSQL or unavailable infra. |
| LICENSING_RESTRICTED | Cannot be copied (EE/proprietary/AGPL-incompatible); Remaining work gives the lawful alternative. |
| INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | NOVARA has a clean-room equivalent; compatibility boundary stated. |

## Source summary (counts from MASTER_FEATURE_MATRIX.csv)

| Source | Prefix | Inventory file | Rows | ID range | Licence basis |
| --- | --- | --- | --- | --- | --- |
| Formbricks | FB | SOURCES/01-formbricks.md | 234 | FB-001–FB-234 | AGPL-3.0 community + Formbricks EE; MIT SDKs |
| Meilisearch | MS | SOURCES/02-meilisearch.md | 103 | MS-001–MS-103 | MIT + OpenLDAP core; BUSL-1.1 EE |
| GrowthBook | GB | SOURCES/03-growthbook.md | 284 | GB-001–GB-284 | MIT community; GrowthBook Enterprise License |
| Papermark | PM | SOURCES/04-papermark.md | 156 | PM-001–PM-156 | AGPL-3.0 community; commercial EE |
| Plane | PL | SOURCES/05-plane.md | 158 | PL-001–PL-158 | AGPL-3.0-only (entire repo) |
| Mautic | MT | SOURCES/06-mautic.md | 133 | MT-001–MT-133 | GPL-3.0 community; Mautic trademark unlicensed |
| Chatwoot | CW | SOURCES/07-chatwoot.md | 168 | CW-001–CW-168 | MIT community; Chatwoot Enterprise License |
| Novu | NV | SOURCES/08-novu.md | 119 | NV-001–NV-119 | MIT community; proprietary enterprise packages |
| Marketing Skills | MK | SOURCES/09-marketingskills.md | 53 | MK-001–MK-053 | MIT (attribution required) |
| Sellbird | SB | SOURCES/10-sellbird.md | 80 | SB-001–SB-080 | AGPL-3.0-only v0.4.0+; MIT ≤0.3.x |

**Total: 1488 features.**

## Per-source catalogue

Each table lists permanent ID, source feature name, current status, mapped NOVARA module and priority. Remaining work and full evidence are in the CSV and the source inventory.

### Formbricks (FB) — 234 features

| ID | Exact source feature name | Current status | NOVARA module | Priority |
| --- | --- | --- | --- | --- |
| FB-001 | Free and open source surveying platform (Open Source Qualtrics Alternative) | VERIFIED_COMPLETE | feedback | P0 |
| FB-002 | In-app surveys | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-003 | Website surveys | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-004 | Link surveys | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-005 | Email surveys | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-006 | Embedded surveys (iframe and email snippets) | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-007 | SurveyType enum (link, app) | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-008 | displayOptions enum (displayOnce, displayMultiple, displaySome, respondMultiple) | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-009 | Survey visibility modes (workspace, restricted) | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-010 | No-code survey editor | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-011 | Best-practice templates | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-012 | NPS preset / template claim | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-013 | CSAT preset / template claim | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-014 | CES (Customer Effort Score) question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-015 | Multi-page survey flow / Flow Tab | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-016 | Logic jumps / Conditional Logic | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-017 | Show If | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-018 | Branching and endings | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-019 | Set Value and Expressions | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-020 | Validation Rules | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-021 | Question Codes and Answer Codes | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-022 | Hidden Fields | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-023 | Embedded Data | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-024 | Field Library | VERIFIED_COMPLETE | feedback | P2 |
| FB-025 | Reserved Fields | VERIFIED_COMPLETE | feedback | P2 |
| FB-026 | setEmbeddedData / clearEmbeddedData | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-027 | Recall Data | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-028 | Variables | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-029 | User Metadata | VERIFIED_COMPLETE | feedback | P2 |
| FB-030 | Partial Submissions | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-031 | Spam Protection (Google reCAPTCHA v3) | EXTERNAL_DEPENDENCY_BLOCKED | feedback | P2 |
| FB-032 | Multi-language Surveys | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-033 | Custom Styling (per survey) | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-034 | Custom CSS | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-035 | Styling Theme | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-036 | Email Branding | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-037 | Add Image / Video question content | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-038 | Hide Back Button | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-039 | Address question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-040 | Consent question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-041 | Contact Info question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-042 | Date question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-043 | File Upload question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-044 | Free Text question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-045 | Matrix question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-046 | Ranking question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-047 | Rating question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-048 | Schedule A Meeting question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-049 | Multi Select question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-050 | Picture Selection question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-051 | Single Select question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-052 | Signature question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-053 | Statement / Call to Action question | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-054 | Thank You Card | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-055 | In-app targeting without application code changes | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-056 | User Identification | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-057 | Attribute-based Targeting | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-058 | ActionClass model / Actions | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-059 | SurveyTrigger model | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-060 | Show Conditions | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-061 | Survey Display Logic | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-062 | Recontact Options | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-063 | Cooldown Period | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-064 | Survey % of Users | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-065 | Lifecycle Events | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-066 | Personal Links | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-067 | Single-Use Links | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-068 | Pretty URL | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-069 | Link Settings (title, description, preview image) | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-070 | Data Prefilling | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-071 | Source Tracking | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-072 | Start At Specific Block | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-073 | Verify Email before survey | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-074 | PIN Protected Surveys | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-075 | Custom Head Scripts | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-076 | Offline Support | NOT_IMPLEMENTED | feedback | P2 |
| FB-077 | Google Tag Manager deployment | EXTERNAL_DEPENDENCY_BLOCKED | feedback | P2 |
| FB-078 | Framework Guides and SDK compatibility | NOT_IMPLEMENTED | feedback | P2 |
| FB-079 | Host Page CSS interaction | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-080 | Email Follow-ups | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-081 | Limit Submissions | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-082 | Schedule a Survey | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-083 | Quota Management | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-084 | SurveyQuota / ResponseQuotaLink models | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-085 | Segments API / audience segmentation | VERIFIED_COMPLETE | feedback | P2 |
| FB-086 | Response model / response collection | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-087 | Response score validation (1-10) | VERIFIED_COMPLETE | Feedback / Survey Responses | P2 |
| FB-088 | Survey detail: response count and average score | VERIFIED_COMPLETE | Feedback / Survey Detail | P2 |
| FB-089 | Append-only survey event audit trail | VERIFIED_COMPLETE | Feedback / Survey Audit Trail | P2 |
| FB-090 | Workspace isolation on survey routes | VERIFIED_COMPLETE | Feedback / Survey Isolation | P2 |
| FB-091 | Display model / display tracking | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-092 | Tags model and response tagging | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-093 | Reading Survey Results (Summary and Responses table) | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-094 | Export Responses (CSV/Excel, Analysis export, SPSS) | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-095 | Response management (update, delete, mark finished) | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-096 | Dashboards and Charts (survey analysis) | VERIFIED_COMPLETE | feedback | P2 |
| FB-097 | Unify Feedback (Analyze) | VERIFIED_COMPLETE | feedback | P2 |
| FB-098 | Feedback Datasets | VERIFIED_COMPLETE | feedback | P2 |
| FB-099 | Feedback Sources | VERIFIED_COMPLETE | feedback | P2 |
| FB-100 | Feedback Records / feedbackRecords API | VERIFIED_COMPLETE | feedback | P2 |
| FB-101 | Unify Feedback API (unify-feedback resource) | VERIFIED_COMPLETE | feedback | P2 |
| FB-102 | AI Enrichment (sentiment, emotions, language) | EXTERNAL_DEPENDENCY_BLOCKED | agents | P2 |
| FB-103 | Topics and Subtopics (Preview) | EXTERNAL_DEPENDENCY_BLOCKED | analytics | P2 |
| FB-104 | Journey management (journey tagging, scorecards, detection signals, recurring patterns, owners) | NOT_IMPLEMENTED | feedback | P2 |
| FB-105 | Formbricks Hub | EXTERNAL_DEPENDENCY_BLOCKED | feedback | P2 |
| FB-106 | AI chart creation and AI helpers | EXTERNAL_DEPENDENCY_BLOCKED | analytics | P2 |
| FB-107 | Shared analytics model for response facts | PARTIALLY_IMPLEMENTED | analytics | P2 |
| FB-108 | Webhook model and webhook delivery | PARTIALLY_IMPLEMENTED | integrations | P2 |
| FB-109 | WebhookSource enum | NOT_IMPLEMENTED | integrations | P2 |
| FB-110 | Integration model | PARTIALLY_IMPLEMENTED | integrations | P2 |
| FB-111 | Third-party integrations (Cloud) | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-112 | Slack integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-113 | Notion integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-114 | Zapier integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-115 | n8n integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-116 | Google Sheets integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-117 | Activepieces integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-118 | Airtable integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-119 | Attio integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-120 | HubSpot integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-121 | Make integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-122 | Salesforce integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-123 | Wordpress integration | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| FB-124 | MCP endpoint / MCP server (Surveys, Creatives, Workflows) | PARTIALLY_IMPLEMENTED | agents | P2 |
| FB-125 | REST API (Public Client API and Management API) | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-126 | API keys with read/write/manage permissions | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-127 | OpenAPI generation and contract tests | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-128 | Next.js route-handler API (apps/web/app/api) | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | feedback | P2 |
| FB-129 | v3 API resource groups (surveys, responses, contacts, contact-attribute-keys, dashboards, workflows, creatives, segments, tags, action-classes, charts, feedbackRecords, unify-feedback, gateway, workspaces) | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-130 | Additional route groups (auth, billing, client, google-sheet, internal, mcp) | NOT_IMPLEMENTED | feedback | P2 |
| FB-131 | Integrate with Formbricks (SDKs, APIs, webhooks or MCP) | NOT_IMPLEMENTED | adapters | P2 |
| FB-132 | JavaScript client SDK (packages/js) | NOT_IMPLEMENTED | adapters | P2 |
| FB-133 | Android SDK (packages/android) | NOT_IMPLEMENTED | adapters | P2 |
| FB-134 | iOS SDK (packages/ios) | NOT_IMPLEMENTED | adapters | P2 |
| FB-135 | API package (packages/api) | NOT_IMPLEMENTED | adapters | P2 |
| FB-136 | Surveys package (packages/surveys) | NOT_IMPLEMENTED | adapters | P2 |
| FB-137 | Survey UI package (packages/survey-ui) | NOT_IMPLEMENTED | adapters | P2 |
| FB-138 | js-core MIT package | NOT_IMPLEMENTED | adapters | P2 |
| FB-139 | i18n-utils MIT package | NOT_IMPLEMENTED | adapters | P2 |
| FB-140 | logger MIT package | NOT_IMPLEMENTED | adapters | P2 |
| FB-141 | vite-plugins MIT package | NOT_IMPLEMENTED | adapters | P2 |
| FB-142 | Mobile SDKs (React Native, iOS, Android, Flutter) | NOT_IMPLEMENTED | adapters | P2 |
| FB-143 | MIT SDK reuse route (consume as dependencies, clean-room server) | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | adapters | P2 |
| FB-144 | Workspace model and workspaces API | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | feedback | P2 |
| FB-145 | Organization model | NOT_IMPLEMENTED | feedback | P2 |
| FB-146 | Membership model | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | feedback | P2 |
| FB-147 | OrganizationRole enum (owner, manager, member, billing, dashboard_viewer) | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-148 | dashboard_viewer role | NOT_IMPLEMENTED | analytics | P2 |
| FB-149 | Team collaboration / invite members | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-150 | SpiceDB fine-grained authorisation | EXTERNAL_DEPENDENCY_BLOCKED | feedback | P2 |
| FB-151 | Local accounts and sessions | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | feedback | P2 |
| FB-152 | JWKS | NOT_IMPLEMENTED | feedback | P2 |
| FB-153 | Two-factor authentication (community model present) | NOT_IMPLEMENTED | feedback | P2 |
| FB-154 | OAuth provider / social login | EXTERNAL_DEPENDENCY_BLOCKED | feedback | P2 |
| FB-155 | SAML / BoxyHQ | LICENSING_RESTRICTED | feedback | P2 |
| FB-156 | OIDC / Keycloak / Okta / Azure AD SSO | LICENSING_RESTRICTED | feedback | P2 |
| FB-157 | Billing | NOT_IMPLEMENTED | feedback | P2 |
| FB-158 | Shared workspace/role mapping to external API scope (read/write/manage) | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-159 | No second Formbricks login | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | feedback | P2 |
| FB-160 | packages/jobs background job queue | PARTIALLY_IMPLEMENTED | jobs | P2 |
| FB-161 | Recurring jobs and job schedules | PARTIALLY_IMPLEMENTED | jobs | P2 |
| FB-162 | Webhook/email auditing and erasure intents | NOT_IMPLEMENTED | feedback | P2 |
| FB-163 | Email delivery (packages/email, SMTP) | EXTERNAL_DEPENDENCY_BLOCKED | adapters | P2 |
| FB-164 | Object storage / file uploads (packages/storage, RustFS, S3) | EXTERNAL_DEPENDENCY_BLOCKED | documents | P2 |
| FB-165 | Valkey / Redis-compatible queue and cache | EXTERNAL_DEPENDENCY_BLOCKED | jobs | P2 |
| FB-166 | PostgreSQL persistence with Prisma | EXTERNAL_DEPENDENCY_BLOCKED | feedback | P2 |
| FB-167 | Prisma schema split (main, creatives, retention, workflows) | NOT_IMPLEMENTED | feedback | P2 |
| FB-168 | Versioned SQL migrations | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-169 | VLLM / local AI endpoint | EXTERNAL_DEPENDENCY_BLOCKED | agents | P2 |
| FB-170 | Cube analytics service | EXTERNAL_DEPENDENCY_BLOCKED | analytics | P2 |
| FB-171 | hub / hub-worker service | EXTERNAL_DEPENDENCY_BLOCKED | jobs | P2 |
| FB-172 | Self-hosting documentation set | EXTERNAL_DEPENDENCY_BLOCKED | operations | P2 |
| FB-173 | Docker image builds and release workflows | EXTERNAL_DEPENDENCY_BLOCKED | operations | P2 |
| FB-174 | Helm charts (formbricks, spicedb-operator) | EXTERNAL_DEPENDENCY_BLOCKED | operations | P2 |
| FB-175 | One-Click Setup / Docker Setup / Kubernetes deployment | EXTERNAL_DEPENDENCY_BLOCKED | operations | P2 |
| FB-176 | CDN, custom SSL and custom subpath | EXTERNAL_DEPENDENCY_BLOCKED | operations | P2 |
| FB-177 | Rate limiting and Envoy Gateway | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-178 | Monitoring, deployment check and cluster setup | EXTERNAL_DEPENDENCY_BLOCKED | operations | P2 |
| FB-179 | Backup and restore | VERIFIED_COMPLETE | Feedback / Backup & Restore | P2 |
| FB-180 | Migrating surveys and responses between instances | NOT_IMPLEMENTED | feedback | P2 |
| FB-181 | Observability (OpenTelemetry, Sentry, PostHog) | NOT_IMPLEMENTED | operations | P2 |
| FB-182 | Testing and CI quality gates | PARTIALLY_IMPLEMENTED | operations | P2 |
| FB-183 | Accessibility support | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-184 | Creatives package (feedback button and banner) | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-185 | Feedback Button creative | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-186 | Banner creative | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-187 | Creative scheduling and show conditions | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-188 | Creative performance measurement | NOT_IMPLEMENTED | analytics | P2 |
| FB-189 | Survey-triggered workflows (packages/workflows) | PARTIALLY_IMPLEMENTED | automation | P2 |
| FB-190 | Build a workflow | NOT_IMPLEMENTED | automation | P2 |
| FB-191 | Manage and monitor workflows | PARTIALLY_IMPLEMENTED | automation | P2 |
| FB-192 | Contact Form template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-193 | Headless Surveys guide | NOT_IMPLEMENTED | feedback | P2 |
| FB-194 | Docs Feedback template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-195 | Feature Chaser template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-196 | Feedback Box template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-197 | Improve Email Content template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-198 | App Interview Prompt template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-199 | Churn Survey template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-200 | Product-Market Fit Survey template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-201 | Quiz Time template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-202 | Improve Trial Conversion template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-203 | Panel Management template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-204 | Collect Google Reviews template | VERIFIED_COMPLETE | Feedback / Surveys | P2 |
| FB-205 | Enterprise: AI translation of surveys | LICENSING_RESTRICTED | feedback | P3 |
| FB-206 | Enterprise: Enterprise analysis capability | LICENSING_RESTRICTED | feedback | P3 |
| FB-207 | Enterprise: Comprehensive audit logging | LICENSING_RESTRICTED | feedback | P3 |
| FB-208 | Enterprise: Enterprise authentication helpers | LICENSING_RESTRICTED | feedback | P3 |
| FB-209 | Enterprise: Enterprise billing | LICENSING_RESTRICTED | feedback | P3 |
| FB-210 | Enterprise: Enterprise contact extras / contacts API guard | LICENSING_RESTRICTED | feedback | P3 |
| FB-211 | Enterprise: Enterprise creative extras | LICENSING_RESTRICTED | feedback | P3 |
| FB-212 | Enterprise: Data retention controls | LICENSING_RESTRICTED | feedback | P3 |
| FB-213 | Enterprise: Feedback directory | LICENSING_RESTRICTED | feedback | P3 |
| FB-214 | Enterprise: Enterprise license enforcement | LICENSING_RESTRICTED | feedback | P3 |
| FB-215 | Enterprise: Enterprise mailing | LICENSING_RESTRICTED | feedback | P3 |
| FB-216 | Enterprise: Quota enforcement | LICENSING_RESTRICTED | feedback | P3 |
| FB-217 | Enterprise: Enterprise role management | LICENSING_RESTRICTED | feedback | P3 |
| FB-218 | Enterprise: Enterprise SSO | LICENSING_RESTRICTED | feedback | P3 |
| FB-219 | Enterprise: Enterprise teams | LICENSING_RESTRICTED | feedback | P3 |
| FB-220 | Enterprise: Enterprise two-factor auth | LICENSING_RESTRICTED | feedback | P3 |
| FB-221 | Enterprise: Enterprise Unify Feedback extras | LICENSING_RESTRICTED | feedback | P3 |
| FB-222 | Enterprise: White-labelling | LICENSING_RESTRICTED | feedback | P3 |
| FB-223 | Enterprise: Enterprise workflow extras | LICENSING_RESTRICTED | feedback | P3 |
| FB-224 | Enterprise license check enforcement files | LICENSING_RESTRICTED | feedback | P3 |
| FB-225 | License activation documentation | LICENSING_RESTRICTED | operations | P3 |
| FB-226 | Hosted free plan | EXTERNAL_DEPENDENCY_BLOCKED | operations | P3 |
| FB-227 | Experience Suite | EXTERNAL_DEPENDENCY_BLOCKED | operations | P3 |
| FB-228 | Managed cloud | EXTERNAL_DEPENDENCY_BLOCKED | operations | P3 |
| FB-229 | Commercial third-party components (AWS SDKs, PostHog, Sentry, BoxyHQ SAML) | NOT_IMPLEMENTED | adapters | P3 |
| FB-230 | Clean-room survey runtime | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | feedback | P2 |
| FB-231 | One event spine for survey responses and display events | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-232 | External ID link table on the workspace record | NOT_IMPLEMENTED | feedback | P2 |
| FB-233 | In-app micro-survey module fit | PARTIALLY_IMPLEMENTED | feedback | P2 |
| FB-234 | Exclude all EE capabilities from the default install | LICENSING_RESTRICTED | feedback | P0 |

### Meilisearch (MS) — 103 features

| ID | Exact source feature name | Current status | NOVARA module | Priority |
| --- | --- | --- | --- | --- |
| MS-001 | Hybrid search (semantic plus full-text) | VERIFIED_COMPLETE | search | P3 |
| MS-002 | Full-text search | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | search | P0 |
| MS-003 | Search-as-you-type | PARTIALLY_IMPLEMENTED | search | P2 |
| MS-004 | Typo tolerance | VERIFIED_COMPLETE | search | P2 |
| MS-005 | Prefix search | PARTIALLY_IMPLEMENTED | search | P2 |
| MS-006 | Filtering | VERIFIED_COMPLETE | search; core API | P1 |
| MS-007 | Faceted search and facet distributions | VERIFIED_COMPLETE | search | P2 |
| MS-008 | Facet search (facet value type-ahead) | VERIFIED_COMPLETE | search | P2 |
| MS-009 | Faceted navigation UI | PARTIALLY_IMPLEMENTED | search | P2 |
| MS-010 | Sorting / `sortableAttributes` | PARTIALLY_IMPLEMENTED | search | P2 |
| MS-011 | Built-in ranking rules | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | search | P1 |
| MS-012 | Custom ranking rules | VERIFIED_COMPLETE | search | P2 |
| MS-013 | Ranking score and score details | VERIFIED_COMPLETE | search | P3 |
| MS-014 | Searchable attributes | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | search | P1 |
| MS-015 | Displayed attributes / `attributesToRetrieve` | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | search | P1 |
| MS-016 | Synonyms | VERIFIED_COMPLETE | search | P2 |
| MS-017 | Stop words | VERIFIED_COMPLETE | search | P3 |
| MS-018 | Separator tokens | VERIFIED_COMPLETE | search | P3 |
| MS-019 | Non-separator tokens | VERIFIED_COMPLETE | search | P3 |
| MS-020 | Dictionary | VERIFIED_COMPLETE | search | P3 |
| MS-021 | Language support and tokenization | VERIFIED_COMPLETE | search | P2 |
| MS-022 | Localized attributes and query locales | VERIFIED_COMPLETE | search | P3 |
| MS-023 | Geosearch | VERIFIED_COMPLETE | search | P3 |
| MS-024 | Geo distance sorting | VERIFIED_COMPLETE | search | P3 |
| MS-025 | Highlighting | VERIFIED_COMPLETE | search | P2 |
| MS-026 | Cropping and snippets | VERIFIED_COMPLETE | search | P2 |
| MS-027 | Match positions | VERIFIED_COMPLETE | search | P3 |
| MS-028 | Pagination | VERIFIED_COMPLETE | search | P1 |
| MS-029 | Phrase search and term exclusion | VERIFIED_COMPLETE | search | P2 |
| MS-030 | Matching strategy | VERIFIED_COMPLETE | search | P3 |
| MS-031 | Placeholder search | VERIFIED_COMPLETE | search | P3 |
| MS-032 | Distinct attribute | VERIFIED_COMPLETE | search | P3 |
| MS-033 | Proximity precision | VERIFIED_COMPLETE | search | P3 |
| MS-034 | Search cutoff | VERIFIED_COMPLETE | search | P2 |
| MS-035 | Per-query searchable attributes | VERIFIED_COMPLETE | search | P3 |
| MS-036 | Suggestions and autocomplete connectors | VERIFIED_COMPLETE | search | P2 |
| MS-037 | Multi-search | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | search | P0 |
| MS-038 | Federated weights and per-index parameters | VERIFIED_COMPLETE | search | P2 |
| MS-039 | RESTful search API | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | search | P0 |
| MS-040 | Settings API | VERIFIED_COMPLETE | search | P2 |
| MS-041 | Index creation and management | VERIFIED_COMPLETE | search | P2 |
| MS-042 | Index swap | VERIFIED_COMPLETE | search | P3 |
| MS-043 | Index fields listing | VERIFIED_COMPLETE | search | P3 |
| MS-044 | Add or replace documents | VERIFIED_COMPLETE | search | P2 |
| MS-045 | Partial document update | VERIFIED_COMPLETE | search | P2 |
| MS-046 | Document deletion | VERIFIED_COMPLETE | search | P2 |
| MS-047 | Batch import and large datasets | VERIFIED_COMPLETE | search | P3 |
| MS-048 | Edit documents by function | VERIFIED_COMPLETE | search | P3 |
| MS-049 | Asynchronous tasks and task monitoring | PARTIALLY_IMPLEMENTED | search; jobs | P2 |
| MS-050 | Task cancellation, deletion and streaming | PARTIALLY_IMPLEMENTED | jobs | P3 |
| MS-051 | Batches and batch monitoring | PARTIALLY_IMPLEMENTED | jobs | P3 |
| MS-052 | Task webhooks | NOT_IMPLEMENTED | search; integrations | P2 |
| MS-053 | Index compaction and task queue compaction | VERIFIED_COMPLETE | search | P3 |
| MS-054 | Export to a remote Meilisearch instance | NOT_IMPLEMENTED | search | P3 |
| MS-055 | Statistics endpoints | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | operations; search | P1 |
| MS-056 | Health endpoint | PARTIALLY_IMPLEMENTED | operations | P2 |
| MS-057 | Version endpoint | VERIFIED_COMPLETE | search | P3 |
| MS-058 | Backups: snapshots and dumps | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | operations | P1 |
| MS-059 | Logs streaming and runtime log level | PARTIALLY_IMPLEMENTED | operations | P2 |
| MS-060 | Prometheus metrics endpoint | NOT_IMPLEMENTED | operations | P3 |
| MS-061 | Experimental feature toggles | VERIFIED_COMPLETE | search | P3 |
| MS-062 | Master key bootstrap | VERIFIED_COMPLETE | search; core API | P1 |
| MS-063 | API keys with action and index scopes | VERIFIED_COMPLETE | integrations; search | P1 |
| MS-064 | Tenant tokens and multi-tenancy | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | search; core API | P0 |
| MS-065 | Sanitizing search results | VERIFIED_COMPLETE | search | P1 |
| MS-066 | Role-based access control with joins | NOT_IMPLEMENTED | search; core API | P2 |
| MS-067 | Official client SDKs | NOT_IMPLEMENTED | adapters | P2 |
| MS-068 | Framework and platform connectors | NOT_IMPLEMENTED | integrations | P3 |
| MS-069 | MCP server | NOT_IMPLEMENTED | search; agents | P3 |
| MS-070 | Conversational search and Chats API | NOT_IMPLEMENTED | search; agents | P3 |
| MS-071 | Agentic search guardrails and source documents | NOT_IMPLEMENTED | agents; search | P3 |
| MS-072 | LangChain vector store integration | NOT_IMPLEMENTED | search; adapters | P3 |
| MS-073 | Personalized search | NOT_IMPLEMENTED | search; analytics | P3 |
| MS-074 | Similar documents and recommendations | VERIFIED_COMPLETE | search | P3 |
| MS-075 | Embedders and vector settings | VERIFIED_COMPLETE | search | P3 |
| MS-076 | User-provided embeddings and custom vectors | VERIFIED_COMPLETE | search | P3 |
| MS-077 | Composite and multiple embedders | VERIFIED_COMPLETE | search | P3 |
| MS-078 | Binary quantization | VERIFIED_COMPLETE | search | P3 |
| MS-079 | Multimodal and image search | NOT_IMPLEMENTED | search | P3 |
| MS-080 | Document relations and foreign keys | PARTIALLY_IMPLEMENTED | search | P2 |
| MS-081 | TLS, HTTP/2 and SSL certificates | NOT_IMPLEMENTED | operations | P2 |
| MS-082 | Telemetry opt-out | NOT_IMPLEMENTED | operations | P2 |
| MS-083 | Self-hosted installation and deployment | EXTERNAL_DEPENDENCY_BLOCKED | search | P2 |
| MS-084 | Meilisearch Cloud managed service | EXTERNAL_DEPENDENCY_BLOCKED | search | P3 |
| MS-085 | Cloud monitoring, resource scaling and version management | EXTERNAL_DEPENDENCY_BLOCKED | operations | P3 |
| MS-086 | Cloud teams, roles, SSO and IP allowlist | EXTERNAL_DEPENDENCY_BLOCKED | core API; integrations | P3 |
| MS-087 | Cloud automated backups | EXTERNAL_DEPENDENCY_BLOCKED | operations | P3 |
| MS-088 | Search Rules: pin, boost, deboost and hide documents | LICENSING_RESTRICTED | search | P3 |
| MS-089 | Inline dynamic search rules | LICENSING_RESTRICTED | search | P3 |
| MS-090 | Sharding | LICENSING_RESTRICTED | search | P3 |
| MS-091 | Replication, network topology and leader routing | LICENSING_RESTRICTED | search | P3 |
| MS-092 | S3-streaming snapshots | LICENSING_RESTRICTED | operations | P3 |
| MS-093 | Enterprise Edition entitlement guard and BUSL terms | LICENSING_RESTRICTED | search | P0 |
| MS-094 | Meilisearch Importer CLI | NOT_IMPLEMENTED | search | P3 |
| MS-095 | Search preview UI and demos | VERIFIED_COMPLETE | search | P3 |
| MS-096 | CI benchmark, fuzz and SDK test workflows | PARTIALLY_IMPLEMENTED | search | P3 |
| MS-097 | LMDB storage connector and OpenLDAP license | NOT_IMPLEMENTED | search | P3 |
| MS-098 | Search analytics and usage events | PARTIALLY_IMPLEMENTED | analytics; search | P2 |
| MS-099 | Environment-driven configuration | EXTERNAL_DEPENDENCY_BLOCKED | search | P3 |
| MS-100 | Vendored async-openai external crates | NOT_IMPLEMENTED | search | P3 |
| MS-101 | OpenAPI specification generation and CI sync | PARTIALLY_IMPLEMENTED | core API | P3 |
| MS-102 | Meili CLI | NOT_IMPLEMENTED | search | P3 |
| MS-103 | Render templates | VERIFIED_COMPLETE | search | P3 |

### GrowthBook (GB) — 284 features

| ID | Exact source feature name | Current status | NOVARA module | Priority |
| --- | --- | --- | --- | --- |
| GB-001 | Feature keys | VERIFIED_COMPLETE | none | P1 |
| GB-002 | Feature state and kill switch | VERIFIED_COMPLETE | none | P1 |
| GB-003 | Default values | VERIFIED_COMPLETE | none | P1 |
| GB-004 | Feature CRUD | VERIFIED_COMPLETE | none | P1 |
| GB-005 | Built-in environments | VERIFIED_COMPLETE | none | P1 |
| GB-006 | Per-environment feature state | VERIFIED_COMPLETE | none | P1 |
| GB-007 | Projects | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-008 | Ordered feature rules | VERIFIED_COMPLETE | none | P1 |
| GB-009 | Targeting conditions | VERIFIED_COMPLETE | none | P1 |
| GB-010 | User attributes | VERIFIED_COMPLETE | none | P1 |
| GB-011 | Percentage rollouts | VERIFIED_COMPLETE | none | P1 |
| GB-012 | Saved groups | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-013 | Archiving and history | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-014 | Draft revisions and publishing | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-015 | Feature flag experiments | VERIFIED_COMPLETE | none | P1 |
| GB-016 | Experiment configuration | VERIFIED_COMPLETE | none | P1 |
| GB-017 | A/B tests | VERIFIED_COMPLETE | none | P1 |
| GB-018 | Variations | VERIFIED_COMPLETE | none | P1 |
| GB-019 | Experiment results table | VERIFIED_COMPLETE | none | P1 |
| GB-020 | Bayesian statistics engine | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-021 | Frequentist statistics engine | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-022 | SRM detection | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-023 | Result health checks | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-024 | Custom experiment reports | VERIFIED_COMPLETE | Feature flags / Experimentation | P3 |
| GB-025 | Dimensions | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-026 | Segments | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-027 | Discovery queries | VERIFIED_COMPLETE | Feature flags / Experimentation | P3 |
| GB-028 | Fact tables | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-029 | Metric definitions | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-030 | Proportion metrics | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-031 | Mean metrics | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-032 | Ratio metrics | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-033 | SQL explorer | NOT_IMPLEMENTED | none | P2 |
| GB-034 | Assignment queries | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-035 | Identifier types and join tables | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-036 | Experiment exposure tracking callback | VERIFIED_COMPLETE | none | P1 |
| GB-037 | Funnel analysis | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-038 | Power analysis | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-039 | A/A testing | VERIFIED_COMPLETE | Feature flags / Experimentation | P3 |
| GB-040 | Importing external experiments | NOT_IMPLEMENTED | none | P3 |
| GB-041 | Experiment time series | VERIFIED_COMPLETE | Feature flags / Experimentation | P3 |
| GB-042 | Multiple testing corrections | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-043 | Aggregate data statistics engine | NOT_IMPLEMENTED | none | P3 |
| GB-044 | Query optimization | NOT_IMPLEMENTED | none | P3 |
| GB-045 | SQL templates | NOT_IMPLEMENTED | none | P3 |
| GB-046 | Data source configuration | NOT_IMPLEMENTED | none | P2 |
| GB-047 | Custom data source | NOT_IMPLEMENTED | none | P2 |
| GB-048 | Stale feature flag detection | VERIFIED_COMPLETE | Feature flags / Experimentation | P3 |
| GB-049 | Feature evaluation diagnostics | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-050 | Remote saved groups | NOT_IMPLEMENTED | none | P2 |
| GB-051 | Remote groups with proxy | NOT_IMPLEMENTED | none | P3 |
| GB-052 | Custom remote group lookups | NOT_IMPLEMENTED | none | P3 |
| GB-053 | Saved group revisions API | NOT_IMPLEMENTED | none | P3 |
| GB-054 | SDK connection revisions | NOT_IMPLEMENTED | none | P2 |
| GB-055 | SDK payload endpoint | VERIFIED_COMPLETE | none | P1 |
| GB-056 | Local SDK evaluation | VERIFIED_COMPLETE | none | P1 |
| GB-057 | Remote configuration | VERIFIED_COMPLETE | none | P1 |
| GB-058 | SDK connections | VERIFIED_COMPLETE | none | P1 |
| GB-059 | REST API v1 | VERIFIED_COMPLETE | Platform / API | P1 |
| GB-060 | REST API v2 | VERIFIED_COMPLETE | Feature flags / REST API v2 | P1 |
| GB-061 | OpenAPI specification | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-062 | Forty REST route modules | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-063 | Organisations | VERIFIED_COMPLETE | Platform / Workspaces | P1 |
| GB-064 | Local email and password accounts | VERIFIED_COMPLETE | Platform / Auth | P1 |
| GB-065 | Personal access tokens | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-066 | API keys | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-067 | Default RBAC roles | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-068 | Air-gapped licence keys | NOT_IMPLEMENTED | none | P3 |
| GB-069 | 14-day licence expiration grace | NOT_IMPLEMENTED | none | P3 |
| GB-070 | Licence server egress | NOT_IMPLEMENTED | none | P3 |
| GB-071 | Event webhooks | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-072 | SDK webhooks | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-073 | Global SDK webhooks | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-074 | Slack notifier | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-075 | CDN cache purge | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-076 | Self-hosted proxy server | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-077 | MCP server | NOT_IMPLEMENTED | none | P3 |
| GB-078 | Agent Skills | NOT_IMPLEMENTED | none | P3 |
| GB-079 | API keys for agents | NOT_IMPLEMENTED | none | P3 |
| GB-080 | dbt sync | NOT_IMPLEMENTED | none | P3 |
| GB-081 | Agenda job queue | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-082 | Experiment result refresh jobs | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-083 | Metric refresh jobs | VERIFIED_COMPLETE | Feature flags / Experimentation | P2 |
| GB-084 | Generic scheduled job processing | NOT_IMPLEMENTED | none | P3 |
| GB-085 | OpenTelemetry instrumentation | NOT_IMPLEMENTED | none | P3 |
| GB-086 | Sentry error reporting | NOT_IMPLEMENTED | none | P3 |
| GB-087 | MongoDB primary store | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Feature flags / Document store | P1 |
| GB-088 | Mongoose model layer | NOT_IMPLEMENTED | none | P2 |
| GB-089 | Just-in-time document upgrades | NOT_IMPLEMENTED | none | P2 |
| GB-090 | Docker Compose self-hosting | NOT_IMPLEMENTED | none | P2 |
| GB-091 | Single container image | NOT_IMPLEMENTED | none | P2 |
| GB-092 | Hardened distroless image | NOT_IMPLEMENTED | none | P3 |
| GB-093 | Kubernetes and Helm deployment | NOT_IMPLEMENTED | none | P3 |
| GB-094 | FerretDB alternative store | NOT_IMPLEMENTED | none | P3 |
| GB-095 | Config.yml | NOT_IMPLEMENTED | none | P3 |
| GB-096 | CI verification suite | NOT_IMPLEMENTED | none | P2 |
| GB-097 | Command palette | NOT_IMPLEMENTED | none | P3 |
| GB-098 | DevTools browser extension | NOT_IMPLEMENTED | none | P3 |
| GB-099 | VS Code extension | NOT_IMPLEMENTED | none | P3 |
| GB-100 | CLI | NOT_IMPLEMENTED | none | P3 |
| GB-101 | Carryover bias guidance | VERIFIED_COMPLETE | Feature flags / Experimentation | P3 |
| GB-102 | Constants | NOT_IMPLEMENTED | none | P3 |
| GB-103 | Visual experiments in JavaScript SDK | NOT_IMPLEMENTED | none | P2 |
| GB-104 | Managed warehouse | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-105 | Security compliance claims | NOT_IMPLEMENTED | none | P3 |
| GB-106 | Public IP allowlist | NOT_IMPLEMENTED | none | P3 |
| GB-107 | Automated backup and restore tooling | NOT_IMPLEMENTED | none | P3 |
| GB-108 | Insights dashboards | LICENSING_RESTRICTED | none | P3 |
| GB-109 | Executive reports | LICENSING_RESTRICTED | none | P3 |
| GB-110 | Experiment CRUD | VERIFIED_COMPLETE | analytics | P1 |
| GB-111 | Experiment status changes | VERIFIED_COMPLETE | analytics | P1 |
| GB-112 | Experiment result recording | VERIFIED_COMPLETE | analytics | P1 |
| GB-113 | Funnel summary analytics | VERIFIED_COMPLETE | analytics | P1 |
| GB-114 | Event volume analytics | VERIFIED_COMPLETE | analytics | P1 |
| GB-115 | Experiment audit events | VERIFIED_COMPLETE | analytics | P1 |
| GB-116 | Analytics validation and workspace isolation | VERIFIED_COMPLETE | analytics | P1 |
| GB-117 | GrowthBook integration catalog entry | VERIFIED_COMPLETE | integrations | P1 |
| GB-118 | Flags adapter seam | PARTIALLY_IMPLEMENTED | adapters | P2 |
| GB-119 | Athena | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-120 | BigQuery | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-121 | ClickHouse | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-122 | Databricks | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-123 | Google Analytics | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-124 | Mixpanel | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-125 | MSSQL or SQL Server | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-126 | MySQL or MariaDB | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-127 | PostgreSQL | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-128 | PrestoDB or Trino | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-129 | Amazon Redshift | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-130 | Snowflake | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-131 | Generic SQL integration | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-132 | Vertica | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-133 | Adobe Experience Platform Query Service | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| GB-134 | Amplitude | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-135 | CleverTap | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-136 | Custom | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-137 | Firebase | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-138 | Freshpaint | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-139 | FullStory | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-140 | Heap | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-141 | Jitsu | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-142 | Keen IO | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-143 | Langfuse | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-144 | mParticle | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-145 | Arize Phoenix | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-146 | Segment | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-147 | Snowplow | VERIFIED_COMPLETE | Experiments / Exposure adapters | P3 |
| GB-148 | JavaScript SDK | NOT_IMPLEMENTED | none | P2 |
| GB-149 | React SDK | NOT_IMPLEMENTED | none | P2 |
| GB-150 | Next.js SDK | NOT_IMPLEMENTED | none | P3 |
| GB-151 | Vue SDK | NOT_IMPLEMENTED | none | P3 |
| GB-152 | Node.js SDK | NOT_IMPLEMENTED | none | P3 |
| GB-153 | Python SDK | NOT_IMPLEMENTED | none | P3 |
| GB-154 | Ruby SDK | NOT_IMPLEMENTED | none | P3 |
| GB-155 | PHP SDK | NOT_IMPLEMENTED | none | P3 |
| GB-156 | Java SDK | NOT_IMPLEMENTED | none | P3 |
| GB-157 | Go SDK | NOT_IMPLEMENTED | none | P3 |
| GB-158 | C# SDK | NOT_IMPLEMENTED | none | P3 |
| GB-159 | Elixir SDK | NOT_IMPLEMENTED | none | P3 |
| GB-160 | Rust SDK | NOT_IMPLEMENTED | none | P3 |
| GB-161 | Kotlin JVM SDK | NOT_IMPLEMENTED | none | P3 |
| GB-162 | Kotlin Android SDK | NOT_IMPLEMENTED | none | P3 |
| GB-163 | Swift SDK | NOT_IMPLEMENTED | none | P3 |
| GB-164 | Flutter SDK | NOT_IMPLEMENTED | none | P3 |
| GB-165 | React Native SDK | NOT_IMPLEMENTED | none | P3 |
| GB-166 | Roku SDK | NOT_IMPLEMENTED | none | P3 |
| GB-167 | HTML script tag | NOT_IMPLEMENTED | none | P3 |
| GB-168 | OpenFeature provider | NOT_IMPLEMENTED | none | P3 |
| GB-169 | Cloudflare Workers SDK | NOT_IMPLEMENTED | none | P3 |
| GB-170 | Fastly Compute SDK | NOT_IMPLEMENTED | none | P3 |
| GB-171 | Lambda@Edge SDK | NOT_IMPLEMENTED | none | P3 |
| GB-172 | Vercel Flags SDK | NOT_IMPLEMENTED | none | P3 |
| GB-173 | Build your own SDK spec | NOT_IMPLEMENTED | none | P3 |
| GB-174 | ai-suggestions | LICENSING_RESTRICTED | none | P3 |
| GB-175 | ai-byok | LICENSING_RESTRICTED | none | P3 |
| GB-176 | scim | LICENSING_RESTRICTED | none | P3 |
| GB-177 | sso | LICENSING_RESTRICTED | none | P3 |
| GB-178 | advanced-permissions | LICENSING_RESTRICTED | none | P3 |
| GB-179 | role-management | LICENSING_RESTRICTED | none | P3 |
| GB-180 | unlimited-projects | LICENSING_RESTRICTED | none | P3 |
| GB-181 | custom-environments | LICENSING_RESTRICTED | none | P3 |
| GB-182 | encrypt-features-endpoint | LICENSING_RESTRICTED | none | P3 |
| GB-183 | schedule-feature-flag | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-184 | events-forwarder | LICENSING_RESTRICTED | none | P3 |
| GB-185 | custom-metadata | LICENSING_RESTRICTED | none | P3 |
| GB-186 | override-metrics | LICENSING_RESTRICTED | none | P3 |
| GB-187 | regression-adjustment | VERIFIED_COMPLETE | GrowthBook / advanced experimentation statistics | P3 |
| GB-188 | post-stratification | VERIFIED_COMPLETE | GrowthBook / advanced experimentation statistics | P3 |
| GB-189 | sequential-testing | VERIFIED_COMPLETE | GrowthBook / advanced experimentation statistics | P3 |
| GB-190 | pipeline-mode | LICENSING_RESTRICTED | none | P3 |
| GB-191 | audit-logging | LICENSING_RESTRICTED | none | P3 |
| GB-192 | visual-editor | LICENSING_RESTRICTED | none | P3 |
| GB-193 | archetypes | LICENSING_RESTRICTED | none | P3 |
| GB-194 | simulate | LICENSING_RESTRICTED | none | P3 |
| GB-195 | cloud-proxy | LICENSING_RESTRICTED | none | P3 |
| GB-196 | hash-secure-attributes | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-197 | livechat | LICENSING_RESTRICTED | none | P3 |
| GB-198 | json-validation | LICENSING_RESTRICTED | none | P3 |
| GB-199 | remote-evaluation | LICENSING_RESTRICTED | none | P3 |
| GB-200 | multi-org | LICENSING_RESTRICTED | none | P3 |
| GB-201 | custom-launch-checklist | LICENSING_RESTRICTED | none | P3 |
| GB-202 | multi-metric-queries | LICENSING_RESTRICTED | none | P3 |
| GB-203 | no-access-role | LICENSING_RESTRICTED | none | P3 |
| GB-204 | project-admin-role | LICENSING_RESTRICTED | none | P3 |
| GB-205 | teams | LICENSING_RESTRICTED | none | P3 |
| GB-206 | sticky-bucketing | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-207 | require-approvals | LICENSING_RESTRICTED | none | P3 |
| GB-208 | code-references | LICENSING_RESTRICTED | none | P3 |
| GB-209 | prerequisites | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-210 | prerequisite-targeting | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-211 | redirects | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-212 | multiple-sdk-webhooks | LICENSING_RESTRICTED | none | P3 |
| GB-213 | custom-roles | LICENSING_RESTRICTED | none | P3 |
| GB-214 | quantile-metrics | VERIFIED_COMPLETE | GrowthBook / advanced experimentation statistics | P3 |
| GB-215 | retention-metrics | VERIFIED_COMPLETE | GrowthBook / advanced experimentation statistics | P3 |
| GB-216 | funnel-metrics | LICENSING_RESTRICTED | none | P3 |
| GB-217 | compound-metrics | VERIFIED_COMPLETE | GrowthBook / advanced experimentation statistics | P3 |
| GB-218 | custom-markdown | LICENSING_RESTRICTED | none | P3 |
| GB-219 | experiment-impact | LICENSING_RESTRICTED | none | P3 |
| GB-220 | metric-populations | LICENSING_RESTRICTED | none | P3 |
| GB-221 | large-saved-groups | LICENSING_RESTRICTED | none | P3 |
| GB-222 | multi-armed-bandits | VERIFIED_COMPLETE | GrowthBook / advanced experimentation statistics | P3 |
| GB-223 | metric-groups | LICENSING_RESTRICTED | none | P3 |
| GB-224 | environment-inheritance | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-225 | templates | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-226 | historical-power | LICENSING_RESTRICTED | none | P3 |
| GB-227 | decision-framework | LICENSING_RESTRICTED | none | P3 |
| GB-228 | unlimited-cdn-usage | LICENSING_RESTRICTED | none | P3 |
| GB-229 | unlimited-managed-warehouse-usage | LICENSING_RESTRICTED | none | P3 |
| GB-230 | unlimited-event-forwarder-usage | LICENSING_RESTRICTED | none | P3 |
| GB-231 | safe-rollout | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-232 | require-project-for-features-setting | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-233 | require-project-for-sdk-connections-setting | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-234 | holdouts | LICENSING_RESTRICTED | none | P3 |
| GB-235 | saveSqlExplorerQueries | LICENSING_RESTRICTED | none | P3 |
| GB-236 | metric-effects | LICENSING_RESTRICTED | none | P3 |
| GB-237 | metric-correlations | VERIFIED_COMPLETE | GrowthBook / advanced experimentation statistics | P3 |
| GB-238 | learnings | LICENSING_RESTRICTED | none | P3 |
| GB-239 | dashboards | LICENSING_RESTRICTED | none | P3 |
| GB-240 | product-analytics-dashboards | LICENSING_RESTRICTED | none | P3 |
| GB-241 | precomputed-dimensions | LICENSING_RESTRICTED | none | P3 |
| GB-242 | custom-hooks | LICENSING_RESTRICTED | none | P3 |
| GB-243 | metric-slices | LICENSING_RESTRICTED | none | P3 |
| GB-244 | manage-official-resources | LICENSING_RESTRICTED | none | P3 |
| GB-245 | incremental-refresh | LICENSING_RESTRICTED | none | P3 |
| GB-246 | adv-presentations | LICENSING_RESTRICTED | none | P3 |
| GB-247 | ramp-schedules | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-248 | scheduled-revisions | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-249 | feature-configs | VERIFIED_COMPLETE | GrowthBook / advanced feature-flag governance | P3 |
| GB-250 | releases | LICENSING_RESTRICTED | none | P3 |
| GB-251 | contextual-bandits | LICENSING_RESTRICTED | none | P3 |
| GB-252 | interleaving | LICENSING_RESTRICTED | none | P3 |
| GB-253 | cluster-experiments | LICENSING_RESTRICTED | none | P3 |
| GB-254 | human-in-the-loop | LICENSING_RESTRICTED | none | P3 |
| GB-255 | AI Mode | LICENSING_RESTRICTED | none | P3 |
| GB-256 | Manual Mode | LICENSING_RESTRICTED | none | P3 |
| GB-257 | Visual editor images | LICENSING_RESTRICTED | none | P3 |
| GB-258 | Design to Variant | LICENSING_RESTRICTED | none | P3 |
| GB-259 | Visual experiment anti-flicker | LICENSING_RESTRICTED | none | P3 |
| GB-260 | Visual experiment preview and QA | LICENSING_RESTRICTED | none | P3 |
| GB-261 | Bandit configuration | LICENSING_RESTRICTED | none | P3 |
| GB-262 | Bandit results | LICENSING_RESTRICTED | none | P3 |
| GB-263 | Contextual bandit configuration | LICENSING_RESTRICTED | none | P3 |
| GB-264 | Contextual bandit API | LICENSING_RESTRICTED | none | P3 |
| GB-265 | Interleaving setup | LICENSING_RESTRICTED | none | P3 |
| GB-266 | Interleaving results | LICENSING_RESTRICTED | none | P3 |
| GB-267 | Vercel native integration | LICENSING_RESTRICTED | none | P3 |
| GB-268 | Framer plugin | LICENSING_RESTRICTED | none | P3 |
| GB-269 | Shopify integration | LICENSING_RESTRICTED | none | P3 |
| GB-270 | Webflow integration | LICENSING_RESTRICTED | none | P3 |
| GB-271 | WordPress integration | LICENSING_RESTRICTED | none | P3 |
| GB-272 | AI integrations | LICENSING_RESTRICTED | none | P3 |
| GB-273 | LLM tracing experiments | LICENSING_RESTRICTED | none | P3 |
| GB-274 | GitHub metric version control | LICENSING_RESTRICTED | none | P3 |
| GB-275 | Microsoft Clarity heatmaps | LICENSING_RESTRICTED | none | P3 |
| GB-276 | Jira integration | LICENSING_RESTRICTED | none | P3 |
| GB-277 | Discord integration | LICENSING_RESTRICTED | none | P3 |
| GB-278 | Datadog integration | LICENSING_RESTRICTED | none | P3 |
| GB-279 | Slack AI assistant | LICENSING_RESTRICTED | none | P3 |
| GB-280 | Self-hosted Slack setup | LICENSING_RESTRICTED | none | P3 |
| GB-281 | Legacy Slack webhooks | LICENSING_RESTRICTED | none | P3 |
| GB-282 | Webhooks event reference | NOT_IMPLEMENTED | none | P3 |
| GB-283 | Product analytics explorer | NOT_IMPLEMENTED | none | P3 |
| GB-284 | GrowthBook Slack app | NOT_IMPLEMENTED | none | P3 |

### Papermark (PM) — 156 features

| ID | Exact source feature name | Current status | NOVARA module | Priority |
| --- | --- | --- | --- | --- |
| PM-001 | Open-source DocSend alternative | VERIFIED_COMPLETE | documents | P0 |
| PM-002 | Document upload with presigned upload URL | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-003 | External URL and Notion documents | NOT_IMPLEMENTED | documents | P2 |
| PM-004 | Team document library | VERIFIED_COMPLETE | documents | P1 |
| PM-005 | Document metadata creation | VERIFIED_COMPLETE | documents | P0 |
| PM-006 | Document detail | VERIFIED_COMPLETE | documents | P1 |
| PM-007 | Update document metadata | VERIFIED_COMPLETE | documents | P2 |
| PM-008 | Delete document | VERIFIED_COMPLETE | documents | P1 |
| PM-009 | Document versions | VERIFIED_COMPLETE | documents | P1 |
| PM-010 | Promote/repoint document version | VERIFIED_COMPLETE | documents | P2 |
| PM-011 | Document pages | VERIFIED_COMPLETE | documents | P1 |
| PM-012 | PDF sharing and preview | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-013 | Supported file formats | NOT_IMPLEMENTED | documents | P2 |
| PM-014 | Large uploads / no file size limit | NOT_IMPLEMENTED | documents | P2 |
| PM-015 | Blob storage and S3-compatible backend | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-016 | Opaque storage reference | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | documents | P0 |
| PM-017 | Document/room lifecycle events | VERIFIED_COMPLETE | documents + events | P0 |
| PM-018 | Document name search | VERIFIED_COMPLETE | documents | P2 |
| PM-019 | Team library folders | VERIFIED_COMPLETE | documents | P1 |
| PM-020 | Nested folder operations | NOT_IMPLEMENTED | documents | P2 |
| PM-021 | Folder delete and cascade guard | NOT_IMPLEMENTED | documents | P2 |
| PM-022 | Collections | VERIFIED_COMPLETE | documents | P1 |
| PM-023 | Multi-file sharing | NOT_IMPLEMENTED | documents | P2 |
| PM-024 | Reactions | VERIFIED_COMPLETE | documents | P3 |
| PM-025 | Feedback | VERIFIED_COMPLETE | documents | P3 |
| PM-026 | Agreements / NDA records | VERIFIED_COMPLETE | documents | P1 |
| PM-027 | Annotations | VERIFIED_COMPLETE | documents | P3 |
| PM-028 | Shareable links | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-029 | Link management | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-030 | Link password protection | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-031 | Email verification gate | VERIFIED_COMPLETE | documents | P1 |
| PM-032 | Link expiry | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-033 | Download restrictions / view-only | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-034 | Email allowlist / allow-block lists | VERIFIED_COMPLETE | documents | P1 |
| PM-035 | Custom domain and slug on links | NOT_IMPLEMENTED | documents | P2 |
| PM-036 | Domain verification route | NOT_IMPLEMENTED | documents | P2 |
| PM-037 | Open Graph preview route | NOT_IMPLEMENTED | documents | P3 |
| PM-038 | CSP report route | NOT_IMPLEMENTED | documents + security | P3 |
| PM-039 | Restricted tokens and link sessions | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-040 | Document password encryption key | VERIFIED_COMPLETE | documents + security | P1 |
| PM-041 | Update file without resending | VERIFIED_COMPLETE | documents | P1 |
| PM-042 | Instant access revocation | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-043 | Custom password screen message | NOT_IMPLEMENTED | documents | P3 |
| PM-044 | Screenshot protection | NOT_IMPLEMENTED | documents | P2 |
| PM-045 | Dynamic watermarking | VERIFIED_COMPLETE | documents + security | P1 |
| PM-046 | Watermark variables and style | NOT_IMPLEMENTED | documents | P2 |
| PM-047 | One-click NDA gate | VERIFIED_COMPLETE | documents | P1 |
| PM-048 | NDA electronic signature and signed PDF | NOT_IMPLEMENTED | documents | P2 |
| PM-049 | NDA acceptance tracking and dashboard | NOT_IMPLEMENTED | documents + analytics | P2 |
| PM-050 | Data Rooms (Enterprise Edition feature) | LICENSING_RESTRICTED | documents | P0 |
| PM-051 | Data room metadata CRUD | VERIFIED_COMPLETE | documents | P0 |
| PM-052 | Multiple data rooms per workspace | VERIFIED_COMPLETE | documents | P1 |
| PM-053 | Unique room name per workspace | VERIFIED_COMPLETE | documents | P1 |
| PM-054 | Guarded room deletion | VERIFIED_COMPLETE | documents | P0 |
| PM-055 | Attach and detach room documents | VERIFIED_COMPLETE | documents | P1 |
| PM-056 | Move document between rooms/folders | NOT_IMPLEMENTED | documents | P2 |
| PM-057 | Data room folders | LICENSING_RESTRICTED | documents | P1 |
| PM-058 | Room item ordering | LICENSING_RESTRICTED | documents | P3 |
| PM-059 | Viewer groups | LICENSING_RESTRICTED | documents | P0 |
| PM-060 | Group membership by email and domain | LICENSING_RESTRICTED | documents | P1 |
| PM-061 | Per-item group view/download permissions | LICENSING_RESTRICTED | documents | P0 |
| PM-062 | Per-link file permissions | LICENSING_RESTRICTED | documents | P1 |
| PM-063 | PermissionGroup model | VERIFIED_COMPLETE | documents | P1 |
| PM-064 | Room-scoped entitlement checks | LICENSING_RESTRICTED | documents + permissions | P0 |
| PM-065 | Data room invitations | LICENSING_RESTRICTED | documents + workspaces | P1 |
| PM-066 | Data room freeze | LICENSING_RESTRICTED | documents | P2 |
| PM-067 | Data room digest emails | NOT_IMPLEMENTED | documents + jobs | P2 |
| PM-068 | Unlimited visitors, rooms and storage | NOT_IMPLEMENTED | documents | P2 |
| PM-069 | File requests / request uploads | NOT_IMPLEMENTED | documents | P2 |
| PM-070 | Full white-label branding | LICENSING_RESTRICTED | documents + branding | P2 |
| PM-071 | Room and link branding configuration | NOT_IMPLEMENTED | documents + branding | P2 |
| PM-072 | Viewer and visit capture | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-073 | View/download events on event spine | VERIFIED_COMPLETE | documents + events | P0 |
| PM-074 | Page-by-page analytics | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-075 | Time on page | VERIFIED_COMPLETE | documents + analytics | P1 |
| PM-076 | Scroll depth and completion | VERIFIED_COMPLETE | documents | P2 |
| PM-077 | Video view analytics | VERIFIED_COMPLETE | documents | P3 |
| PM-078 | Total views and unique visitors | VERIFIED_COMPLETE | documents + analytics | P1 |
| PM-079 | View duration and timing | VERIFIED_COMPLETE | documents + analytics | P1 |
| PM-080 | Verified visitor identification | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-081 | Real-time view notification | VERIFIED_COMPLETE | documents + notifications | P1 |
| PM-082 | Download status and download events | VERIFIED_COMPLETE | documents + analytics | P1 |
| PM-083 | Visitor location | VERIFIED_COMPLETE | documents | P2 |
| PM-084 | Device, OS and platform analytics | VERIFIED_COMPLETE | documents | P2 |
| PM-085 | Exclude internal visits | VERIFIED_COMPLETE | documents | P2 |
| PM-086 | View history retention | NOT_IMPLEMENTED | documents + analytics | P2 |
| PM-087 | Visitor history API | VERIFIED_COMPLETE | documents + analytics | P1 |
| PM-088 | Access log / append-only audit log | VERIFIED_COMPLETE | documents + events | P0 |
| PM-089 | Data room analytics rollup | VERIFIED_COMPLETE | documents + analytics | P1 |
| PM-090 | Analytics aggregation service | VERIFIED_COMPLETE | analytics | P1 |
| PM-091 | Click tracking route | VERIFIED_COMPLETE | documents | P3 |
| PM-092 | Team collaboration and workspace members | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | workspaces | P0 |
| PM-093 | Team roles ADMIN/MANAGER/MEMBER | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | permissions | P0 |
| PM-094 | DATAROOM_MEMBER role | LICENSING_RESTRICTED | permissions + documents | P0 |
| PM-095 | Fine-grained permission verbs | VERIFIED_COMPLETE | permissions + documents | P0 |
| PM-096 | Advanced Permissions (Enterprise Edition) | LICENSING_RESTRICTED | permissions + documents | P0 |
| PM-097 | Q&A conversations (Enterprise Edition) | LICENSING_RESTRICTED | support + documents | P1 |
| PM-098 | AI chat and AI store (Enterprise Edition) | LICENSING_RESTRICTED | agents + documents | P2 |
| PM-099 | AI workflows (Enterprise Edition) | LICENSING_RESTRICTED | automation | P2 |
| PM-100 | AI redaction | LICENSING_RESTRICTED | documents + agents | P2 |
| PM-101 | AI review personas | NOT_IMPLEMENTED | agents + documents | P3 |
| PM-102 | Access notifications (Enterprise Edition) | LICENSING_RESTRICTED | notifications | P1 |
| PM-103 | Billing and Stripe (Enterprise Edition) | LICENSING_RESTRICTED | billing | P3 |
| PM-104 | Conversions (Enterprise Edition) | LICENSING_RESTRICTED | documents + analytics | P2 |
| PM-105 | Storage (Enterprise Edition) | LICENSING_RESTRICTED | documents | P1 |
| PM-106 | Templates (Enterprise Edition) | LICENSING_RESTRICTED | documents | P3 |
| PM-107 | Security (Enterprise Edition) | LICENSING_RESTRICTED | security | P1 |
| PM-108 | SAML SSO via BoxyHQ Jackson | LICENSING_RESTRICTED | auth | P2 |
| PM-109 | SCIM provisioning | LICENSING_RESTRICTED | auth + workspaces | P3 |
| PM-110 | FAQ endpoints (Enterprise Edition) | LICENSING_RESTRICTED | documents + support | P3 |
| PM-111 | Google OAuth login | NOT_IMPLEMENTED | auth | P2 |
| PM-112 | LinkedIn OAuth login | NOT_IMPLEMENTED | auth | P3 |
| PM-113 | Hanko passkeys | NOT_IMPLEMENTED | auth | P3 |
| PM-114 | Email magic links | NOT_IMPLEMENTED | auth | P2 |
| PM-115 | Session and adapter model | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | auth | P0 |
| PM-116 | Notification and activity surface | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | notifications + events | P0 |
| PM-117 | Signed outgoing webhooks | VERIFIED_COMPLETE | integrations + documents | P1 |
| PM-118 | Incoming webhooks | NOT_IMPLEMENTED | integrations | P2 |
| PM-119 | Slack OAuth integration | NOT_IMPLEMENTED | integrations | P3 |
| PM-120 | Feature flags endpoint | NOT_IMPLEMENTED | analytics + config | P3 |
| PM-121 | Account and team settings API group | VERIFIED_COMPLETE | workspaces + auth | P1 |
| PM-122 | Internal API group | NOT_IMPLEMENTED | platform | P3 |
| PM-123 | Jobs API group | VERIFIED_COMPLETE | jobs + storage | P1 |
| PM-124 | Trigger.dev v4 job runner | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | jobs | P0 |
| PM-125 | File conversion and PDF/image/video processing | VERIFIED_COMPLETE | Documents / Storage / Sharing / Analytics | P0 |
| PM-126 | Bulk downloads | NOT_IMPLEMENTED | documents + jobs | P2 |
| PM-127 | Visit exports | NOT_IMPLEMENTED | documents + analytics + jobs | P2 |
| PM-128 | Dataroom notification queue | LICENSING_RESTRICTED | documents + jobs | P2 |
| PM-129 | Cleanup jobs | NOT_IMPLEMENTED | jobs + documents | P2 |
| PM-130 | Billing reminder jobs | LICENSING_RESTRICTED | jobs + billing | P3 |
| PM-131 | AI indexing job | LICENSING_RESTRICTED | agents + jobs | P2 |
| PM-132 | Upstash QStash and Redis queues/locks | EXTERNAL_DEPENDENCY_BLOCKED | jobs + deployment | P2 |
| PM-133 | Cron routes | NOT_IMPLEMENTED | jobs | P2 |
| PM-134 | Redis-backed job store | EXTERNAL_DEPENDENCY_BLOCKED | jobs | P3 |
| PM-135 | PostgreSQL persistence and migrations | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | database | P0 |
| PM-136 | Vercel Postgres and Blob defaults | NOT_IMPLEMENTED | deployment | P3 |
| PM-137 | Self-hosting / open-source deployment | VERIFIED_COMPLETE | deployment | P0 |
| PM-138 | Vercel deployment and domain automation | EXTERNAL_DEPENDENCY_BLOCKED | deployment | P3 |
| PM-139 | Tinybird deployment dependency | EXTERNAL_DEPENDENCY_BLOCKED | deployment + analytics | P3 |
| PM-140 | Resend email delivery | EXTERNAL_DEPENDENCY_BLOCKED | notifications + deployment | P2 |
| PM-141 | OpenAPI generation and published spec | VERIFIED_COMPLETE | API + documents | P1 |
| PM-142 | Public REST API with bearer tokens | VERIFIED_COMPLETE | API | P1 |
| PM-143 | CLI | NOT_IMPLEMENTED | tooling | P3 |
| PM-144 | MCP server with 57 tools | NOT_IMPLEMENTED | agents + API | P3 |
| PM-145 | Scoped tokens, OAuth 2.1 and scopes | NOT_IMPLEMENTED | auth + API | P2 |
| PM-146 | API rate limits and error envelope | VERIFIED_COMPLETE | API + security | P1 |
| PM-147 | Published client SDK | NOT_IMPLEMENTED | tooling | P3 |
| PM-148 | Webhook payload schemas | NOT_IMPLEMENTED | integrations | P2 |
| PM-149 | RBAC helper library | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | permissions | P0 |
| PM-150 | File conversion and PDF tooling library | VERIFIED_COMPLETE | documents + tooling | P1 |
| PM-151 | Prisma ORM and migration workflow | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | database | P0 |
| PM-152 | Zod validation library | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | API | P0 |
| PM-153 | Next.js and React frontend | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | web | P0 |
| PM-154 | UI component system | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | web design | P2 |
| PM-155 | Security certifications and data residency | NOT_IMPLEMENTED | compliance | P3 |
| PM-156 | Encryption in transit and at rest | VERIFIED_COMPLETE | security + documents | P1 |

### Plane (PL) — 158 features

| ID | Exact source feature name | Current status | NOVARA module | Priority |
| --- | --- | --- | --- | --- |
| PL-001 | Workspaces | VERIFIED_COMPLETE | workspaces | P0 |
| PL-002 | Projects | VERIFIED_COMPLETE | modules/projects | P0 |
| PL-003 | Project members | VERIFIED_COMPLETE | projects | P0 |
| PL-004 | Work Items / Issues | VERIFIED_COMPLETE | modules/projects; core/tasks | P0 |
| PL-005 | Work item descriptions | VERIFIED_COMPLETE | core/tasks; modules/projects | P1 |
| PL-006 | Assignment / assignees | VERIFIED_COMPLETE | modules/projects; core/tasks | P0 |
| PL-007 | Priorities | VERIFIED_COMPLETE | core/tasks | P1 |
| PL-008 | States | VERIFIED_COMPLETE | modules/projects | P0 |
| PL-009 | Labels | VERIFIED_COMPLETE | none found | P1 |
| PL-010 | Cycles | VERIFIED_COMPLETE | none found | P1 |
| PL-011 | Modules | VERIFIED_COMPLETE | none found | P1 |
| PL-012 | Sub-work items | VERIFIED_COMPLETE | none found | P1 |
| PL-013 | Relations | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-014 | Dependencies | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-015 | Parent-child links | VERIFIED_COMPLETE | none found | P1 |
| PL-016 | Estimates | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-017 | Due dates | VERIFIED_COMPLETE | modules/projects | P0 |
| PL-018 | Start dates | VERIFIED_COMPLETE | modules/projects | P1 |
| PL-019 | Milestones | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Projects / Clean-room Extensions | P1 |
| PL-020 | Roadmaps | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-021 | List layout | VERIFIED_COMPLETE | projects + web tasks | P1 |
| PL-022 | Board layout / Kanban | VERIFIED_COMPLETE | none found | P1 |
| PL-023 | Calendar layout | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-024 | Timeline layout | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-025 | Table layout | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-026 | Filters | VERIFIED_COMPLETE | core/tasks | P1 |
| PL-027 | Saved views | VERIFIED_COMPLETE | none found | P1 |
| PL-028 | Custom work item properties | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Projects / Clean-room Extensions | P1 |
| PL-029 | Issue activity | VERIFIED_COMPLETE | core/events | P1 |
| PL-030 | Comments | VERIFIED_COMPLETE | none found | P1 |
| PL-031 | Attachments / file assets | VERIFIED_COMPLETE | Plane / work collaboration and API governance | P2 |
| PL-032 | Mentions | VERIFIED_COMPLETE | Plane / work collaboration and API governance | P2 |
| PL-033 | Notifications | VERIFIED_COMPLETE | core/notifications; modules/jobs | P1 |
| PL-034 | Project updates | LICENSING_RESTRICTED | none found | P2 |
| PL-035 | Work item updates | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-036 | Templates | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-037 | Recurring work items | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-038 | Search | VERIFIED_COMPLETE | modules/search | P0 |
| PL-039 | Team collaboration | VERIFIED_COMPLETE | Plane / work collaboration and API governance | P2 |
| PL-040 | Permissions / RBAC | VERIFIED_COMPLETE | projects / permissions | P0 |
| PL-041 | Workspace admin | VERIFIED_COMPLETE | core/workspaces | P1 |
| PL-042 | Project progress / delivery analytics | VERIFIED_COMPLETE | projects + web tasks | P1 |
| PL-043 | Public REST API | VERIFIED_COMPLETE | adapters | P0 |
| PL-044 | API URL prefixes | VERIFIED_COMPLETE | core/api | P1 |
| PL-045 | API keys / personal access tokens | VERIFIED_COMPLETE | api_keys + web settings | P1 |
| PL-046 | OAuth bearer tokens | NOT_IMPLEMENTED | none found | P2 |
| PL-047 | OAuth Bridge | NOT_IMPLEMENTED | none found | P2 |
| PL-048 | Cursor pagination | VERIFIED_COMPLETE | Plane / work collaboration and API governance | P2 |
| PL-049 | Rate limiting | VERIFIED_COMPLETE | core/security | P1 |
| PL-050 | fields and expand query parameters | VERIFIED_COMPLETE | Plane / work collaboration and API governance | P2 |
| PL-051 | OpenAPI schema, Swagger UI and ReDoc | VERIFIED_COMPLETE | Plane / work collaboration and API governance | P2 |
| PL-052 | Webhooks | NOT_IMPLEMENTED | none found | P2 |
| PL-053 | Email/password authentication | VERIFIED_COMPLETE | core/auth | P0 |
| PL-054 | Magic link authentication | NOT_IMPLEMENTED | none found | P2 |
| PL-055 | Password reset, change and set | VERIFIED_COMPLETE | core/auth | P1 |
| PL-056 | Email checks | VERIFIED_COMPLETE | Plane / Email Checks | P2 |
| PL-057 | CSRF token | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | core/security | P1 |
| PL-058 | Google OAuth | NOT_IMPLEMENTED | none found | P2 |
| PL-059 | GitHub OAuth | NOT_IMPLEMENTED | none found | P2 |
| PL-060 | GitLab OAuth | NOT_IMPLEMENTED | none found | P2 |
| PL-061 | Gitea OAuth | NOT_IMPLEMENTED | none found | P3 |
| PL-062 | GitHub integration | LICENSING_RESTRICTED | none found | P2 |
| PL-063 | GitLab integration | LICENSING_RESTRICTED | none found | P2 |
| PL-064 | Slack integration | LICENSING_RESTRICTED | none found | P2 |
| PL-065 | Sentry integration | LICENSING_RESTRICTED | none found | P3 |
| PL-066 | Draw.io integration | LICENSING_RESTRICTED | none found | P3 |
| PL-067 | Optional OpenAI SDK | NOT_IMPLEMENTED | none found | P3 |
| PL-068 | Slack SDK dependency | NOT_IMPLEMENTED | none found | P3 |
| PL-069 | OAuth provider framework | NOT_IMPLEMENTED | none found | P2 |
| PL-070 | API token permission scoping | VERIFIED_COMPLETE | api_keys + web settings | P1 |
| PL-071 | Celery worker | VERIFIED_COMPLETE | Platform / Jobs | P1 |
| PL-072 | Celery beat scheduler | PARTIALLY_IMPLEMENTED | modules/jobs | P2 |
| PL-073 | Celery results backend | NOT_IMPLEMENTED | none found | P3 |
| PL-074 | Django Channels realtime | NOT_IMPLEMENTED | none found | P2 |
| PL-075 | Live service | NOT_IMPLEMENTED | none found | P3 |
| PL-076 | Email notification task | NOT_IMPLEMENTED | none found | P2 |
| PL-077 | Notification task | VERIFIED_COMPLETE | modules/jobs | P1 |
| PL-078 | Webhook task | NOT_IMPLEMENTED | none found | P2 |
| PL-079 | Issue activities task | VERIFIED_COMPLETE | core/events | P1 |
| PL-080 | Issue automation task | PARTIALLY_IMPLEMENTED | modules/automation | P2 |
| PL-081 | Export task | NOT_IMPLEMENTED | none found | P2 |
| PL-082 | Analytics plot export | NOT_IMPLEMENTED | none found | P3 |
| PL-083 | Page version task | NOT_IMPLEMENTED | none found | P2 |
| PL-084 | File asset task | NOT_IMPLEMENTED | none found | P2 |
| PL-085 | Project invitation task | PARTIALLY_IMPLEMENTED | core/membership | P2 |
| PL-086 | Workspace seed task | NOT_IMPLEMENTED | none found | P3 |
| PL-087 | Cleanup and deletion tasks | PARTIALLY_IMPLEMENTED | modules/jobs | P2 |
| PL-088 | Intake / intake issues | VERIFIED_COMPLETE | project_intake | P1 |
| PL-089 | Intake forms | NOT_IMPLEMENTED | none found | P2 |
| PL-090 | Intake email | NOT_IMPLEMENTED | none found | P2 |
| PL-091 | User assets | NOT_IMPLEMENTED | none found | P2 |
| PL-092 | Workspace assets | NOT_IMPLEMENTED | none found | P2 |
| PL-093 | Stickies | NOT_IMPLEMENTED | none found | P3 |
| PL-094 | Pages | VERIFIED_COMPLETE | none found | P1 |
| PL-095 | Workspace Wiki | LICENSING_RESTRICTED | none found | P2 |
| PL-096 | Page version history | VERIFIED_COMPLETE | Projects / Wiki pages | P2 |
| PL-097 | Page analytics | VERIFIED_COMPLETE | Projects / Wiki pages | P3 |
| PL-098 | Page publish and export | VERIFIED_COMPLETE | Projects / Wiki pages | P2 |
| PL-099 | Page labels | VERIFIED_COMPLETE | Projects / Wiki pages | P3 |
| PL-100 | Nested pages | VERIFIED_COMPLETE | Projects / Wiki pages | P3 |
| PL-101 | Page collections | VERIFIED_COMPLETE | Projects / Wiki pages | P3 |
| PL-102 | Editor blocks | VERIFIED_COMPLETE | Projects / Wiki pages | P2 |
| PL-103 | Live co-editing and inline comments | VERIFIED_COMPLETE | Projects / Wiki pages | P3 |
| PL-104 | Project invitations | NOT_IMPLEMENTED | none found | P2 |
| PL-105 | Workspace invitations | VERIFIED_COMPLETE | core/membership | P1 |
| PL-106 | Teamspaces | LICENSING_RESTRICTED | none found | P2 |
| PL-107 | Themes | NOT_IMPLEMENTED | none found | P3 |
| PL-108 | User preferences | PARTIALLY_IMPLEMENTED | core/account | P2 |
| PL-109 | Instance edition and license model | NOT_IMPLEMENTED | none found | P3 |
| PL-110 | Pro tier entitlements | LICENSING_RESTRICTED | none found | P2 |
| PL-111 | Business tier entitlements | LICENSING_RESTRICTED | none found | P2 |
| PL-112 | Enterprise Grid tier entitlements | LICENSING_RESTRICTED | none found | P2 |
| PL-113 | SAML SSO | LICENSING_RESTRICTED | none found | P2 |
| PL-114 | OIDC SSO | LICENSING_RESTRICTED | none found | P2 |
| PL-115 | LDAP | LICENSING_RESTRICTED | none found | P3 |
| PL-116 | Granular access control | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Projects / Clean-room Extensions | P1 |
| PL-117 | Audit logs | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Projects / Clean-room Extensions | P1 |
| PL-118 | Custom SLAs | LICENSING_RESTRICTED | none found | P3 |
| PL-119 | Multiple workflows | LICENSING_RESTRICTED | none found | P2 |
| PL-120 | Approvals | LICENSING_RESTRICTED | none found | P2 |
| PL-121 | AI credits | LICENSING_RESTRICTED | none found | P3 |
| PL-122 | AI agents | LICENSING_RESTRICTED | none found | P3 |
| PL-123 | Custom relations | LICENSING_RESTRICTED | none found | P3 |
| PL-124 | Custom roles | LICENSING_RESTRICTED | none found | P2 |
| PL-125 | Permission schemes | LICENSING_RESTRICTED | none found | P2 |
| PL-126 | Sensitive data scanning | NOT_IMPLEMENTED | none found | P3 |
| PL-127 | Billing, seats and license management | LICENSING_RESTRICTED | none found | P3 |
| PL-128 | Private dashboards | LICENSING_RESTRICTED | none found | P2 |
| PL-129 | Published dashboards | LICENSING_RESTRICTED | none found | P2 |
| PL-130 | Work item security | VERIFIED_COMPLETE | Plane / work collaboration and API governance | P2 |
| PL-131 | MCP server and connectors | NOT_IMPLEMENTED | none found | P3 |
| PL-132 | Importers | VERIFIED_COMPLETE | Plane / work collaboration and API governance | P2 |
| PL-133 | Desktop app | NOT_IMPLEMENTED | none found | P3 |
| PL-134 | Mobile app | NOT_IMPLEMENTED | none found | P3 |
| PL-135 | Custom automations and Plane runner | NOT_IMPLEMENTED | modules/automation | P2 |
| PL-136 | Time tracking and worklogs | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-137 | Plane Query Language (PQL) | NOT_IMPLEMENTED | none found | P3 |
| PL-138 | Customers and customer requests | NOT_IMPLEMENTED | none found | P2 |
| PL-139 | Releases and project releases | NOT_IMPLEMENTED | none found | P2 |
| PL-140 | Epics | LICENSING_RESTRICTED | none found | P2 |
| PL-141 | Subscribers | VERIFIED_COMPLETE | Projects / Work-item planning | P2 |
| PL-142 | Reactions and votes | NOT_IMPLEMENTED | none found | P3 |
| PL-143 | Keyboard shortcuts and Power-K | NOT_IMPLEMENTED | none found | P3 |
| PL-144 | Your Work / personalized home | PARTIALLY_IMPLEMENTED | core/dashboard | P2 |
| PL-145 | Workspace governance and navigation customization | NOT_IMPLEMENTED | none found | P3 |
| PL-146 | Unit-test and CI discipline | PARTIALLY_IMPLEMENTED | core/testing | P2 |
| PL-147 | Migration workflow | VERIFIED_COMPLETE | Platform / Migrations | P1 |
| PL-148 | PostgreSQL persistence | VERIFIED_COMPLETE | Platform / Database | P1 |
| PL-149 | Redis cache and Channels backend | NOT_IMPLEMENTED | none found | P3 |
| PL-150 | RabbitMQ message broker | NOT_IMPLEMENTED | none found | P3 |
| PL-151 | MinIO/S3 object storage | NOT_IMPLEMENTED | none found | P2 |
| PL-152 | Reverse proxy and certificate settings | NOT_IMPLEMENTED | none found | P3 |
| PL-153 | Docker Compose deployment | NOT_IMPLEMENTED | none found | P3 |
| PL-154 | Kubernetes/Helm deployment | NOT_IMPLEMENTED | none found | P3 |
| PL-155 | Plane Cloud and all-in-one image | NOT_IMPLEMENTED | none found | P3 |
| PL-156 | Internal @plane/* monorepo packages | NOT_IMPLEMENTED | none found | P3 |
| PL-157 | Clean-room work-management substitution | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | modules/projects; core/events | P0 |
| PL-158 | Licence and attribution boundary | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | docs/research | P0 |

### Mautic (MT) — 133 features

| ID | Exact source feature name | Current status | NOVARA module | Priority |
| --- | --- | --- | --- | --- |
| MT-001 | Open-source marketing automation platform | VERIFIED_COMPLETE | marketing | P1 |
| MT-002 | Privacy-focused marketing automation | NOT_IMPLEMENTED | none | P2 |
| MT-003 | Extendable architecture and plugin system | VERIFIED_COMPLETE | modules | P1 |
| MT-004 | DPG governance since 2024 | NOT_IMPLEMENTED | none | P3 |
| MT-005 | Self-host free forever with all features | NOT_IMPLEMENTED | none | P3 |
| MT-006 | Production packaged release from mautic.org/download | NOT_IMPLEMENTED | none | P3 |
| MT-007 | LeadBundle - contacts | VERIFIED_COMPLETE | contacts | P1 |
| MT-008 | LeadBundle - segments | VERIFIED_COMPLETE | Marketing / Segments | P0 |
| MT-009 | Contact types - visitors and known contacts | VERIFIED_COMPLETE | Mautic / marketing content | P2 |
| MT-010 | Contact quick add and management | PARTIALLY_IMPLEMENTED | contacts | P2 |
| MT-011 | Custom contact fields | VERIFIED_COMPLETE | contacts | P1 |
| MT-012 | EmailBundle - template emails | VERIFIED_COMPLETE | Marketing / Email Templates | P0 |
| MT-013 | EmailBundle - segment broadcast emails | VERIFIED_COMPLETE | Marketing / Broadcast Email | P0 |
| MT-014 | Email HTML and text formats | VERIFIED_COMPLETE | Marketing / Email engagement | P2 |
| MT-015 | Email translations and A/B variants | VERIFIED_COMPLETE | Marketing / Email engagement | P3 |
| MT-016 | Email tokens and personalization | VERIFIED_COMPLETE | Marketing / Tokens | P1 |
| MT-017 | Email open tracking pixel | VERIFIED_COMPLETE | Marketing / Email engagement | P2 |
| MT-018 | Email link and click tracking | VERIFIED_COMPLETE | Marketing / Email engagement | P2 |
| MT-019 | Email unsubscribe and preference centre tokens | VERIFIED_COMPLETE | email_campaigns | P0 |
| MT-020 | Email bounce management | VERIFIED_COMPLETE | Marketing / Email engagement | P2 |
| MT-021 | Email reply monitoring | VERIFIED_COMPLETE | Marketing / Email engagement | P3 |
| MT-022 | Mailer as owner and user signatures | VERIFIED_COMPLETE | Marketing / Email engagement | P3 |
| MT-023 | Base64 encoded images in emails | VERIFIED_COMPLETE | Marketing / Email engagement | P3 |
| MT-024 | Online version of email | VERIFIED_COMPLETE | Marketing / Email engagement | P3 |
| MT-025 | CampaignBundle - journeys and campaigns | VERIFIED_COMPLETE | marketing | P0 |
| MT-026 | Campaign types and scheduling | VERIFIED_COMPLETE | Marketing / Campaign Types & Scheduling | P0 |
| MT-027 | Campaign builder drag and drop | VERIFIED_COMPLETE | Marketing / Campaign Builder | P0 |
| MT-028 | Campaign contact sources | VERIFIED_COMPLETE | Marketing / Campaign Sources | P0 |
| MT-029 | PageBundle - landing pages | VERIFIED_COMPLETE | Mautic / marketing content | P2 |
| MT-030 | FormBundle - campaign and standalone forms | VERIFIED_COMPLETE | Marketing / Forms | P1 |
| MT-031 | Progressive profiling via forms | VERIFIED_COMPLETE | Mautic / marketing content | P3 |
| MT-032 | Form submit actions | VERIFIED_COMPLETE | Mautic / marketing content | P2 |
| MT-033 | PointBundle - lead scoring | VERIFIED_COMPLETE | leads | P1 |
| MT-034 | Point triggers and actions | NOT_IMPLEMENTED | none | P2 |
| MT-035 | StageBundle - lifecycle stages | VERIFIED_COMPLETE | contacts | P1 |
| MT-036 | DynamicContentBundle | VERIFIED_COMPLETE | Mautic / marketing content | P3 |
| MT-037 | AssetBundle | VERIFIED_COMPLETE | Mautic / marketing content | P3 |
| MT-038 | Cloud storage plugin | NOT_IMPLEMENTED | none | P3 |
| MT-039 | NotificationBundle | NOT_IMPLEMENTED | none | P3 |
| MT-040 | SmsBundle | NOT_IMPLEMENTED | none | P2 |
| MT-041 | SMS template and segment messages | NOT_IMPLEMENTED | none | P2 |
| MT-042 | SMS unsubscribes and DNC | VERIFIED_COMPLETE | Marketing / SMS | P1 |
| MT-043 | SMS reply pattern decisions | NOT_IMPLEMENTED | none | P3 |
| MT-044 | Twilio SMS transport plugin | EXTERNAL_DEPENDENCY_BLOCKED | none | P2 |
| MT-045 | Marketing Messages multi-channel delivery | VERIFIED_COMPLETE | Marketing / Channels | P1 |
| MT-046 | Channel frequency rules and pause | VERIFIED_COMPLETE | Marketing / Channels | P1 |
| MT-047 | ReportBundle | VERIFIED_COMPLETE | marketing, analytics | P1 |
| MT-048 | DashboardBundle | VERIFIED_COMPLETE | Mautic / marketing content | P2 |
| MT-049 | StatsBundle | PARTIALLY_IMPLEMENTED | marketing | P2 |
| MT-050 | WebhookBundle | VERIFIED_COMPLETE | events, integrations | P1 |
| MT-051 | IntegrationsBundle | PARTIALLY_IMPLEMENTED | integrations | P1 |
| MT-052 | CRM integration plugin | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| MT-053 | Email marketing integration plugins | EXTERNAL_DEPENDENCY_BLOCKED | integrations | P2 |
| MT-054 | Social integration plugin | NOT_IMPLEMENTED | none | P3 |
| MT-055 | Clearbit and FullContact enrichment plugins | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| MT-056 | Zapier integration plugin | NOT_IMPLEMENTED | none | P3 |
| MT-057 | Gmail integration plugin | NOT_IMPLEMENTED | none | P3 |
| MT-058 | Outlook integration plugin | NOT_IMPLEMENTED | none | P3 |
| MT-059 | Focus plugin | NOT_IMPLEMENTED | none | P3 |
| MT-060 | Tag Manager plugin | NOT_IMPLEMENTED | none | P3 |
| MT-061 | MarketplaceBundle | NOT_IMPLEMENTED | none | P3 |
| MT-062 | GrapesJS builder plugin | NOT_IMPLEMENTED | none | P2 |
| MT-063 | Themes directory | NOT_IMPLEMENTED | none | P3 |
| MT-064 | ConfigBundle | PARTIALLY_IMPLEMENTED | operations | P2 |
| MT-065 | UserBundle - roles and permissions | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | auth | P0 |
| MT-066 | CoreBundle | PARTIALLY_IMPLEMENTED | core | P1 |
| MT-067 | MessengerBundle - Symfony Messenger | NOT_IMPLEMENTED | jobs | P2 |
| MT-068 | QueueBundle/Config path | NOT_IMPLEMENTED | none | P3 |
| MT-069 | Cron console commands | VERIFIED_COMPLETE | jobs | P1 |
| MT-070 | Event-driven extension classes | VERIFIED_COMPLETE | events | P1 |
| MT-071 | ApiEvents extension events | NOT_IMPLEMENTED | none | P3 |
| MT-072 | REST API contexts and CRUD | VERIFIED_COMPLETE | api_resources | P0 |
| MT-073 | API Platform ApiResource metadata | NOT_IMPLEMENTED | none | P2 |
| MT-074 | OAuth 1.0a API authentication | NOT_IMPLEMENTED | none | P3 |
| MT-075 | OAuth 2 API authentication | NOT_IMPLEMENTED | none | P2 |
| MT-076 | Basic Auth API authentication | NOT_IMPLEMENTED | none | P3 |
| MT-077 | API enablement and credential creation | NOT_IMPLEMENTED | none | P2 |
| MT-078 | mautic/api-library MIT PHP client | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | integrations | P2 |
| MT-079 | Doctrine ORM entity metadata mapping | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | database | P1 |
| MT-080 | Doctrine migrations with table prefix | NOT_IMPLEMENTED | none | P2 |
| MT-081 | MySQL 8.4+ and MariaDB 10.11+ support | NOT_IMPLEMENTED | none | P3 |
| MT-082 | PHP 8.2+ and Symfony 7.4 backend stack | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | api | P2 |
| MT-083 | npm, webpack and importmap frontend build | PARTIALLY_IMPLEMENTED | web | P2 |
| MT-084 | DDEV developer environment | NOT_IMPLEMENTED | none | P3 |
| MT-085 | Composer install and bin/console install | NOT_IMPLEMENTED | none | P3 |
| MT-086 | Zip and web installer flow | NOT_IMPLEMENTED | none | P3 |
| MT-087 | Web server support Apache, Nginx and IIS | NOT_IMPLEMENTED | none | P3 |
| MT-088 | Shared hosting not recommended | NOT_IMPLEMENTED | none | P3 |
| MT-089 | PHPUnit test suite | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | tests | P1 |
| MT-090 | PHPStan static analysis and baseline | PARTIALLY_IMPLEMENTED | tests | P3 |
| MT-091 | Codeception and Codecov configuration | PARTIALLY_IMPLEMENTED | tests | P3 |
| MT-092 | CI workflows for tests, e2e, coverage and api-library | NOT_IMPLEMENTED | none | P3 |
| MT-093 | Role scoped API expressions | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | auth | P1 |
| MT-094 | Managed Enterprise SSO | NOT_IMPLEMENTED | none | P3 |
| MT-095 | No separate enterprise source edition | NOT_IMPLEMENTED | none | P3 |
| MT-096 | Managed Mautic Essential plan | NOT_IMPLEMENTED | none | P3 |
| MT-097 | Managed Mautic Professional plan | NOT_IMPLEMENTED | none | P3 |
| MT-098 | Managed Mautic Enterprise plan | NOT_IMPLEMENTED | none | P3 |
| MT-099 | Higher sending limits | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| MT-100 | Custom plugins on managed plans | NOT_IMPLEMENTED | none | P3 |
| MT-101 | Dedicated infrastructure and support | NOT_IMPLEMENTED | none | P3 |
| MT-102 | GPL-3.0-or-later core license | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | none | P0 |
| MT-103 | Mautic trademark | NOT_IMPLEMENTED | none | P3 |
| MT-104 | Third-party notices | NOT_IMPLEMENTED | none | P3 |
| MT-105 | GPL redistribution obligations | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | none | P0 |
| MT-106 | No AGPL network source offer | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | none | P3 |
| MT-107 | Legal review before derivative distribution | VERIFIED_COMPLETE | Marketing / Compliance | P1 |
| MT-108 | SMTP and email delivery dependency and cost | EXTERNAL_DEPENDENCY_BLOCKED | none | P1 |
| MT-109 | Optional Messenger transport dependency | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| MT-110 | Object or CDN storage dependency | EXTERNAL_DEPENDENCY_BLOCKED | none | P3 |
| MT-111 | No core licence fee with separate support costs | NOT_IMPLEMENTED | none | P3 |
| MT-112 | Clean-room NOVARA marketing module recommendation | VERIFIED_COMPLETE | marketing | P0 |
| MT-113 | Contact identity with external IDs | VERIFIED_COMPLETE | contacts | P0 |
| MT-114 | Role scope translation to NOVARA RBAC | VERIFIED_COMPLETE | auth, integrations | P1 |
| MT-115 | NOVARA-native lifecycle events | VERIFIED_COMPLETE | events | P0 |
| MT-116 | Consume Mautic webhooks and API as external inputs | NOT_IMPLEMENTED | integrations | P2 |
| MT-117 | Funnel, engagement and attribution analytics | VERIFIED_COMPLETE | analytics, marketing | P1 |
| MT-118 | Developer documentation needs major update | NOT_IMPLEMENTED | none | P3 |
| MT-119 | Source-tree install alpha warning | NOT_IMPLEMENTED | none | P3 |
| MT-120 | 7.x coverage percentage not verified | NOT_IMPLEMENTED | none | P3 |
| MT-121 | Stats hit notifications in Messenger | PARTIALLY_IMPLEMENTED | events, marketing | P2 |
| MT-122 | Contact anonymization command | VERIFIED_COMPLETE | contacts | P1 |
| MT-123 | Import and export commands | PARTIALLY_IMPLEMENTED | portability | P2 |
| MT-124 | IP and do-not-sell maintenance commands | NOT_IMPLEMENTED | none | P3 |
| MT-125 | Transifex maintenance command | NOT_IMPLEMENTED | none | P3 |
| MT-126 | Token replacement event extension | PARTIALLY_IMPLEMENTED | none | P3 |
| MT-127 | Search event extension | PARTIALLY_IMPLEMENTED | search | P3 |
| MT-128 | Upgrade event extension | NOT_IMPLEMENTED | none | P3 |
| MT-129 | Menu and route event extension | PARTIALLY_IMPLEMENTED | web | P3 |
| MT-130 | Stats event extension | PARTIALLY_IMPLEMENTED | analytics | P3 |
| MT-131 | Maintenance event extension | NOT_IMPLEMENTED | none | P3 |
| MT-132 | Builder event extension | NOT_IMPLEMENTED | none | P3 |
| MT-133 | Import and export event extension | NOT_IMPLEMENTED | none | P3 |

### Chatwoot (CW) — 168 features

| ID | Exact source feature name | Current status | NOVARA module | Priority |
| --- | --- | --- | --- | --- |
| CW-001 | Shared Inbox | VERIFIED_COMPLETE | Support / Customer Inbox | P0 |
| CW-002 | Conversations | VERIFIED_COMPLETE | Support / Customer Inbox | P0 |
| CW-003 | Messages / public replies | VERIFIED_COMPLETE | Support / Customer Inbox | P0 |
| CW-004 | Conversation assignment | VERIFIED_COMPLETE | Support / Customer Inbox | P0 |
| CW-005 | Teams | VERIFIED_COMPLETE | Support / Teams | P1 |
| CW-006 | Agent availability / presence | VERIFIED_COMPLETE | Support / Conversation operations | P2 |
| CW-007 | Agent Capacity | LICENSING_RESTRICTED | Support / Routing | P3 |
| CW-008 | Auto-assignment / round-robin | VERIFIED_COMPLETE | Support / Routing | P1 |
| CW-009 | Conversation statuses | VERIFIED_COMPLETE | Support / Customer Inbox | P0 |
| CW-010 | Snoozed conversations | VERIFIED_COMPLETE | Support / Conversation operations | P2 |
| CW-011 | Conversation priority | VERIFIED_COMPLETE | Support / Customer Inbox | P0 |
| CW-012 | Labels | VERIFIED_COMPLETE | Support / Labels | P1 |
| CW-013 | Custom attributes | VERIFIED_COMPLETE | Support / Custom Attributes | P1 |
| CW-014 | Contact profiles | VERIFIED_COMPLETE | CRM / Contacts | P0 |
| CW-015 | Companies | PARTIALLY_IMPLEMENTED | CRM / Companies | P2 |
| CW-016 | Contact notes | VERIFIED_COMPLETE | CRM / Notes | P1 |
| CW-017 | Conversation history / customer timeline | VERIFIED_COMPLETE | Activity / Timeline | P1 |
| CW-018 | Customer identification / pre-chat identity | VERIFIED_COMPLETE | Support / Customer Inbox | P0 |
| CW-019 | Private notes | VERIFIED_COMPLETE | Customer Support / Private Notes | P0 |
| CW-020 | @Mentions in internal discussions | VERIFIED_COMPLETE | Support / Conversation operations | P2 |
| CW-021 | Collision detection | VERIFIED_COMPLETE | Support / Conversation operations | P2 |
| CW-022 | Read receipts | VERIFIED_COMPLETE | Support / Conversation operations | P3 |
| CW-023 | Canned responses / saved replies | VERIFIED_COMPLETE | support + web inbox | P1 |
| CW-024 | Macros | VERIFIED_COMPLETE | Support / Automation | P1 |
| CW-025 | Bulk actions | VERIFIED_COMPLETE | Support / Conversation operations | P2 |
| CW-026 | Keyboard shortcuts | NOT_IMPLEMENTED | Support / UX | P3 |
| CW-027 | Command bar | NOT_IMPLEMENTED | Support / UX | P3 |
| CW-028 | Conversation filters | VERIFIED_COMPLETE | Support / Customer Inbox | P1 |
| CW-029 | Saved filter folders | VERIFIED_COMPLETE | Support / Conversation operations | P2 |
| CW-030 | Conversation search | VERIFIED_COMPLETE | Customer Support / Conversation Search | P0 |
| CW-031 | Conversation attachments | NOT_IMPLEMENTED | Support / Attachments | P2 |
| CW-032 | Mute conversation | VERIFIED_COMPLETE | Support / Conversation operations | P3 |
| CW-033 | Email conversation transcript | EXTERNAL_DEPENDENCY_BLOCKED | Support / Delivery | P3 |
| CW-034 | Dashboard apps | NOT_IMPLEMENTED | Support / Extensions | P3 |
| CW-035 | Website live chat widget | VERIFIED_COMPLETE | visitor_conversations + support | P1 |
| CW-036 | Widget customization | NOT_IMPLEMENTED | Support / Channels | P2 |
| CW-037 | Email channel | EXTERNAL_DEPENDENCY_BLOCKED | Support / Channels | P1 |
| CW-038 | WhatsApp Business channel | EXTERNAL_DEPENDENCY_BLOCKED | Support / Channels | P2 |
| CW-039 | Facebook Messenger channel | EXTERNAL_DEPENDENCY_BLOCKED | Support / Channels | P3 |
| CW-040 | Instagram DMs channel | EXTERNAL_DEPENDENCY_BLOCKED | Support / Channels | P3 |
| CW-041 | X (Twitter) DMs and mentions | EXTERNAL_DEPENDENCY_BLOCKED | Support / Channels | P3 |
| CW-042 | Telegram channel | EXTERNAL_DEPENDENCY_BLOCKED | Support / Channels | P3 |
| CW-043 | LINE channel | EXTERNAL_DEPENDENCY_BLOCKED | Support / Channels | P3 |
| CW-044 | SMS channel | EXTERNAL_DEPENDENCY_BLOCKED | Support / Channels | P2 |
| CW-045 | TikTok DMs channel | EXTERNAL_DEPENDENCY_BLOCKED | Support / Channels | P3 |
| CW-046 | Voice channel | LICENSING_RESTRICTED | Support / Voice | P3 |
| CW-047 | Cloudflare RealtimeKit video calls | EXTERNAL_DEPENDENCY_BLOCKED | Support / Voice | P3 |
| CW-048 | Multi-inbox routing | VERIFIED_COMPLETE | support | P1 |
| CW-049 | Client / public inbox API | NOT_IMPLEMENTED | Support / API | P2 |
| CW-050 | Mobile agent apps | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Mobile | P3 |
| CW-051 | Automation rules | VERIFIED_COMPLETE | Automation / Rules | P1 |
| CW-052 | Business hours | VERIFIED_COMPLETE | Support / Conversation operations | P2 |
| CW-053 | Business hours date overrides | VERIFIED_COMPLETE | Support / Conversation operations | P3 |
| CW-054 | Business hours holidays | VERIFIED_COMPLETE | Support / Conversation operations | P3 |
| CW-055 | Business hours multiple slots | VERIFIED_COMPLETE | Support / Conversation operations | P3 |
| CW-056 | Away messages | VERIFIED_COMPLETE | Support / Conversation operations | P2 |
| CW-057 | SLA policies | LICENSING_RESTRICTED | Support / SLA | P3 |
| CW-058 | SLA timers and status indicators | LICENSING_RESTRICTED | Support / SLA | P3 |
| CW-059 | SLA breach alerts | LICENSING_RESTRICTED | Support / SLA | P3 |
| CW-060 | SLA reports | LICENSING_RESTRICTED | Support / Reporting | P3 |
| CW-061 | Captain Assistant | LICENSING_RESTRICTED | AI / Captain | P3 |
| CW-062 | Captain Copilot | LICENSING_RESTRICTED | AI / Captain | P3 |
| CW-063 | Captain Memories | LICENSING_RESTRICTED | AI / Captain | P3 |
| CW-064 | Captain Reply suggestions | LICENSING_RESTRICTED | AI / Captain | P3 |
| CW-065 | Captain Summarization | LICENSING_RESTRICTED | AI / Captain | P3 |
| CW-066 | Captain Content gap | LICENSING_RESTRICTED | AI / Captain | P3 |
| CW-067 | Captain documents / FAQ ingestion | LICENSING_RESTRICTED | AI / Captain | P3 |
| CW-068 | Captain Triage | LICENSING_RESTRICTED | AI / Captain | P3 |
| CW-069 | Captain Scenarios | LICENSING_RESTRICTED | AI / Captain | P3 |
| CW-070 | Captain Monitors / Convergence | LICENSING_RESTRICTED | AI / Monitors | P3 |
| CW-071 | Captain copilot / MCP tools | LICENSING_RESTRICTED | AI / Captain | P3 |
| CW-072 | Dialogflow chatbot | EXTERNAL_DEPENDENCY_BLOCKED | Support / Chatbots | P3 |
| CW-073 | Rasa chatbot | EXTERNAL_DEPENDENCY_BLOCKED | Support / Chatbots | P3 |
| CW-074 | Agent bots | NOT_IMPLEMENTED | Platform / Agents | P2 |
| CW-075 | Contact segments / customer segmentation | VERIFIED_COMPLETE | support + web inbox | P1 |
| CW-076 | CSV import of contacts | NOT_IMPLEMENTED | CRM / Contacts | P2 |
| CW-077 | Contacts API | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | CRM / API | P2 |
| CW-078 | Pre-chat forms | NOT_IMPLEMENTED | Support / Channels | P2 |
| CW-079 | Campaigns | NOT_IMPLEMENTED | Support / Campaigns | P3 |
| CW-080 | WhatsApp campaigns | EXTERNAL_DEPENDENCY_BLOCKED | Support / Campaigns | P3 |
| CW-081 | Custom domain / white labelling | LICENSING_RESTRICTED | Support / White Label | P3 |
| CW-082 | Email templates | NOT_IMPLEMENTED | Support / Channels | P3 |
| CW-083 | Multilingual support / 50+ languages | NOT_IMPLEMENTED | Platform / I18n | P2 |
| CW-084 | RTL support | NOT_IMPLEMENTED | Platform / I18n | P3 |
| CW-085 | Auto-translate | EXTERNAL_DEPENDENCY_BLOCKED | Support / Translation | P3 |
| CW-086 | Help centre / portals | VERIFIED_COMPLETE | Support / Help Centre | P1 |
| CW-087 | Knowledge base articles | NOT_IMPLEMENTED | Support / Help Centre | P2 |
| CW-088 | Multiple help-centre portals | NOT_IMPLEMENTED | Support / Help Centre | P3 |
| CW-089 | Knowledge-base search analytics | NOT_IMPLEMENTED | Support / Reporting | P3 |
| CW-090 | Help centre in chat widget | NOT_IMPLEMENTED | Support / Channels | P3 |
| CW-091 | Private help-centre pages (coming soon) | NOT_IMPLEMENTED | Support / Help Centre | P3 |
| CW-092 | Help centre API | NOT_IMPLEMENTED | Support / API | P3 |
| CW-093 | Dashboards / analytics overview | VERIFIED_COMPLETE | Analytics / Reporting | P1 |
| CW-094 | Live View | NOT_IMPLEMENTED | Analytics / Reporting | P2 |
| CW-095 | Conversation reports | VERIFIED_COMPLETE | Analytics / Reporting | P1 |
| CW-096 | Agent reports | VERIFIED_COMPLETE | Chatwoot / support reporting | P2 |
| CW-097 | Team reports | VERIFIED_COMPLETE | Chatwoot / support reporting | P2 |
| CW-098 | Inbox reports | VERIFIED_COMPLETE | Chatwoot / support reporting | P2 |
| CW-099 | Label reports | VERIFIED_COMPLETE | Chatwoot / support reporting | P2 |
| CW-100 | CSAT reports | VERIFIED_COMPLETE | Feedback / CSAT | P1 |
| CW-101 | Export reports | VERIFIED_COMPLETE | Chatwoot / support reporting | P2 |
| CW-102 | CSAT surveys | VERIFIED_COMPLETE | Feedback / CSAT | P1 |
| CW-103 | WhatsApp CSAT templates | EXTERNAL_DEPENDENCY_BLOCKED | Feedback / CSAT | P3 |
| CW-104 | CSAT survey rules | VERIFIED_COMPLETE | Chatwoot / support reporting | P2 |
| CW-105 | CSAT review notes | NOT_IMPLEMENTED | Feedback / CSAT | P3 |
| CW-106 | In-app notifications | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Notifications / In-App | P1 |
| CW-107 | Push notifications | EXTERNAL_DEPENDENCY_BLOCKED | Notifications / Push | P3 |
| CW-108 | Webhooks | VERIFIED_COMPLETE | support + integrations | P1 |
| CW-109 | Integration hooks | NOT_IMPLEMENTED | Integrations / Hooks | P3 |
| CW-110 | Domain events / pub-sub | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Events | P0 |
| CW-111 | Background and scheduled jobs | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Jobs | P1 |
| CW-112 | Application API | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / API | P0 |
| CW-113 | Platform API | NOT_IMPLEMENTED | Platform / API | P3 |
| CW-114 | Survey responses API | VERIFIED_COMPLETE | Chatwoot / support reporting | P2 |
| CW-115 | Auth API | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Auth | P0 |
| CW-116 | Health endpoint | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Operations | P3 |
| CW-117 | OpenAPI 3.1 specification | VERIFIED_COMPLETE | Chatwoot / support reporting | P2 |
| CW-118 | Scoped bearer tokens | VERIFIED_COMPLETE | Platform / Auth | P1 |
| CW-119 | Legacy api_access_token header | NOT_IMPLEMENTED | Platform / Auth | P3 |
| CW-120 | JavaScript SDK | NOT_IMPLEMENTED | Platform / SDK | P3 |
| CW-121 | Widget bundle | NOT_IMPLEMENTED | Support / Channels | P2 |
| CW-122 | `@chatwoot/*` utility packages | NOT_IMPLEMENTED | Platform / Libraries | P3 |
| CW-123 | Slack integration | EXTERNAL_DEPENDENCY_BLOCKED | Integrations / Chat | P3 |
| CW-124 | Stripe integration | EXTERNAL_DEPENDENCY_BLOCKED | Integrations / Billing | P3 |
| CW-125 | Linear integration | EXTERNAL_DEPENDENCY_BLOCKED | Integrations / Issues | P3 |
| CW-126 | Shopify integration | EXTERNAL_DEPENDENCY_BLOCKED | Integrations / Commerce | P3 |
| CW-127 | APM / monitoring integrations | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Operations | P3 |
| CW-128 | Chatwoot CLI for coding agents | NOT_IMPLEMENTED | Platform / CLI | P3 |
| CW-129 | Accounts and account memberships | VERIFIED_COMPLETE | Platform / Workspaces | P0 |
| CW-130 | Custom roles and granular permissions | LICENSING_RESTRICTED | Platform / Permissions | P2 |
| CW-131 | Devise secure password authentication | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Auth | P0 |
| CW-132 | Two-factor authentication | NOT_IMPLEMENTED | Platform / Auth | P2 |
| CW-133 | JWT session tokens | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Auth | P1 |
| CW-134 | SAML single sign-on | LICENSING_RESTRICTED | Platform / Auth | P3 |
| CW-135 | Google OAuth login | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Auth | P3 |
| CW-136 | Optional GitHub OAuth strategy | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Auth | P3 |
| CW-137 | Pundit authorization policies | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Permissions | P0 |
| CW-138 | Super admin console | NOT_IMPLEMENTED | Platform / Admin | P3 |
| CW-139 | Audit logging | LICENSING_RESTRICTED | Platform / Compliance | P2 |
| CW-140 | Platform app permissibles | NOT_IMPLEMENTED | Platform / Permissions | P3 |
| CW-141 | ActionCable realtime transport | NOT_IMPLEMENTED | Platform / Realtime | P2 |
| CW-142 | RSpec backend test suite | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Testing | P1 |
| CW-143 | Vitest frontend test suite | NOT_IMPLEMENTED | Platform / Testing | P2 |
| CW-144 | Coverage instrumentation | NOT_IMPLEMENTED | Platform / Testing | P3 |
| CW-145 | CircleCI pipeline | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Operations | P3 |
| CW-146 | Heroku one-click deployment | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Deployment | P3 |
| CW-147 | DigitalOcean one-click Kubernetes deployment | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Deployment | P3 |
| CW-148 | Docker Compose deployment | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Deployment | P3 |
| CW-149 | Helm chart deployment | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Deployment | P3 |
| CW-150 | Development container and deployment manifests | NOT_IMPLEMENTED | Platform / Tooling | P3 |
| CW-151 | Environment configuration | PARTIALLY_IMPLEMENTED | Platform / Configuration | P2 |
| CW-152 | API-only server mode | NOT_IMPLEMENTED | Platform / Configuration | P3 |
| CW-153 | PostgreSQL persistence | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Data | P2 |
| CW-154 | Redis cache and queue backend | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Data | P3 |
| CW-155 | Puma web server | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Runtime | P3 |
| CW-156 | OpenSearch and Searchkick advanced search backend | EXTERNAL_DEPENDENCY_BLOCKED | Search / Infrastructure | P2 |
| CW-157 | S3, Azure and GCS object storage | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Storage | P3 |
| CW-158 | Schema load and Rails migrations | VERIFIED_COMPLETE | Platform / Data | P1 |
| CW-159 | Seed data | NOT_IMPLEMENTED | Platform / Data | P3 |
| CW-160 | Inbound email service adapters | EXTERNAL_DEPENDENCY_BLOCKED | Support / Channels | P2 |
| CW-161 | CDN asset hosting | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Delivery | P3 |
| CW-162 | MFA encryption keys | NOT_IMPLEMENTED | Platform / Security | P2 |
| CW-163 | Channel and AI provider keys | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Configuration | P2 |
| CW-164 | Enterprise application layer | LICENSING_RESTRICTED | Platform / Enterprise | P3 |
| CW-165 | Process liveness and CloudWatch telemetry | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Operations | P3 |
| CW-166 | Authenticated and rate-limited inbound webhooks | VERIFIED_COMPLETE | Platform / Security | P1 |
| CW-167 | Priority support and paid self-hosted subscription | LICENSING_RESTRICTED | Platform / Commercial | P3 |
| CW-168 | Enterprise compliance suite (unverified boundary) | LICENSING_RESTRICTED | Platform / Compliance | P3 |

### Novu (NV) — 119 features

| ID | Exact source feature name | Current status | NOVARA module | Priority |
| --- | --- | --- | --- | --- |
| NV-001 | Unified notification infrastructure (`one API` for Inbox, Email, SMS, Push, Chat) | VERIFIED_COMPLETE | Notifications / Multi-channel Delivery | P0 |
| NV-002 | Event trigger API (`apps/api/src/app/events/trigger-event`) | VERIFIED_COMPLETE | Automation / Workflow | P0 |
| NV-003 | Bulk trigger API | VERIFIED_COMPLETE | Automation / Workflow | P1 |
| NV-004 | Topic trigger and fan-out | VERIFIED_COMPLETE | Topics / Notifications | P1 |
| NV-005 | Workflow builder / workflow management | VERIFIED_COMPLETE | Automation / Workflow | P0 |
| NV-006 | Workflows v1 and v2 API controllers | VERIFIED_COMPLETE | notifications | P2 |
| NV-007 | Notification channel steps (email, SMS, push, in-app, chat) | VERIFIED_COMPLETE | Notifications / Workflow Channel Steps | P0 |
| NV-008 | Step conditions / conditional execution | VERIFIED_COMPLETE | Automation / Workflow | P1 |
| NV-009 | Code steps | VERIFIED_COMPLETE | notifications | P3 |
| NV-010 | Delay step (fixed, scheduled, dynamic) | VERIFIED_COMPLETE | Jobs / Workflow | P1 |
| NV-011 | Scheduled delay / scheduled notification | VERIFIED_COMPLETE | Jobs / Workflow | P1 |
| NV-012 | Digest step / event batching | VERIFIED_COMPLETE | Notifications / Workflow | P1 |
| NV-013 | Scheduled digest | VERIFIED_COMPLETE | notifications | P2 |
| NV-014 | Throttle step | VERIFIED_COMPLETE | Notifications / Workflow | P1 |
| NV-015 | HTTP request step | VERIFIED_COMPLETE | notifications | P3 |
| NV-016 | Tool channel steps (PagerDuty, Opsgenie, Grafana, Tool Webhook) | NOT_IMPLEMENTED | Notifications / Integration | P3 |
| NV-017 | Workflow templates / template catalogue | VERIFIED_COMPLETE | notifications | P2 |
| NV-018 | Payload schema and validation | VERIFIED_COMPLETE | Automation / Workflow | P1 |
| NV-019 | Severity and critical workflows | VERIFIED_COMPLETE | notifications | P2 |
| NV-020 | Email notifications | EXTERNAL_DEPENDENCY_BLOCKED | Notifications / Multi-channel Delivery | P1 |
| NV-021 | SMS notifications | EXTERNAL_DEPENDENCY_BLOCKED | Notifications / Multi-channel Delivery | P1 |
| NV-022 | Push notifications | NOT_IMPLEMENTED | Notifications / Multi-channel Delivery | P2 |
| NV-023 | In-app notifications | VERIFIED_COMPLETE | Notifications / In-app | P0 |
| NV-024 | Chat notifications (Slack, Teams, Telegram, WhatsApp and others) | EXTERNAL_DEPENDENCY_BLOCKED | Notifications / Multi-channel Delivery | P2 |
| NV-025 | Provider integration catalog (`packages/providers/src/lib`) | VERIFIED_COMPLETE | Integrations / Adapters | P1 |
| NV-026 | Integration conditions / provider routing | VERIFIED_COMPLETE | notifications | P2 |
| NV-027 | Demo integrations and sending limits | VERIFIED_COMPLETE | notifications | P3 |
| NV-028 | Trigger overrides | VERIFIED_COMPLETE | notifications | P2 |
| NV-029 | Inbound email / inbound parse | NOT_IMPLEMENTED | Support / Notifications | P2 |
| NV-030 | Subscriber management (`subscribers-v1/v2`) | VERIFIED_COMPLETE | Identity / Notifications | P0 |
| NV-031 | Subscriber credentials / channel endpoints | VERIFIED_COMPLETE | notifications | P2 |
| NV-032 | Subscriber preferences (workflow, channel and global levels) | VERIFIED_COMPLETE | Notifications / Layered Preferences | P0 |
| NV-033 | `<Inbox />` composable notification component | VERIFIED_COMPLETE | Notifications / UI | P1 |
| NV-034 | Bell icon and real-time unread counts | VERIFIED_COMPLETE | Notifications / UI | P1 |
| NV-035 | Notification feed, seen and read state | VERIFIED_COMPLETE | Notifications / In-app | P0 |
| NV-036 | Inbox tabs and filters | VERIFIED_COMPLETE | notifications | P2 |
| NV-037 | Inbox snooze | LICENSING_RESTRICTED | Notifications / UI | P3 |
| NV-038 | Subscriber delivery schedule / quiet hours | VERIFIED_COMPLETE | notifications | P2 |
| NV-039 | Inbox preferences view | VERIFIED_COMPLETE | Notifications / Inbox Preferences UI | P0 |
| NV-040 | Inbox data object, conditional display and rich HTML | VERIFIED_COMPLETE | notifications | P2 |
| NV-041 | Headless Inbox and custom layouts | NOT_IMPLEMENTED | Notifications / UI | P3 |
| NV-042 | HMAC-encrypted subscriber sessions | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Security / Notifications | P1 |
| NV-043 | Inbox localization | NOT_IMPLEMENTED | Notifications / UI | P3 |
| NV-044 | Notification click behaviour and actions | VERIFIED_COMPLETE | notifications | P2 |
| NV-045 | Topics | VERIFIED_COMPLETE | Topics / Notifications | P1 |
| NV-046 | Topic subscriptions with JSON Logic and context scope | VERIFIED_COMPLETE | Topics / Notifications | P1 |
| NV-047 | `<Subscription />` component and headless hooks | NOT_IMPLEMENTED | Topics / UI | P2 |
| NV-048 | Activity Feed / workflow run debug timeline | VERIFIED_COMPLETE | Operations / Audit | P1 |
| NV-049 | Email activity tracking (delivered, opened, clicked, bounced) | LICENSING_RESTRICTED | Notifications / Delivery Tracking | P2 |
| NV-050 | Push activity tracking | EXTERNAL_DEPENDENCY_BLOCKED | Notifications / Delivery Tracking | P3 |
| NV-051 | Delivery retry policy (provider, bridge, webhook layers) | VERIFIED_COMPLETE | Jobs / Notifications | P1 |
| NV-052 | Failed message handling and `messages.failed` events | VERIFIED_COMPLETE | Operations / Notifications | P1 |
| NV-053 | Usage and delivery analytics | PARTIALLY_IMPLEMENTED | Operations / Analytics | P2 |
| NV-054 | Outbound webhooks | VERIFIED_COMPLETE | notifications | P2 |
| NV-055 | Webhook connectors (BigQuery, S3, Segment and similar) | NOT_IMPLEMENTED | Integrations / Webhooks | P3 |
| NV-056 | Webhook signature verification, retries and replay | VERIFIED_COMPLETE | notifications | P2 |
| NV-057 | REST API and generated OpenAPI document | VERIFIED_COMPLETE | Platform / API | P0 |
| NV-058 | Server SDKs (`@novu/api`, Python, Go, PHP, .NET, Java) | NOT_IMPLEMENTED | Platform / API | P3 |
| NV-059 | Client SDKs (`@novu/js`, `@novu/react`, `@novu/react-native`) | NOT_IMPLEMENTED | Notifications / UI | P3 |
| NV-060 | Code-first workflows (`@novu/framework`, bridge endpoint, Studio/CLI) | NOT_IMPLEMENTED | Automation / Workflow | P3 |
| NV-061 | Novu CLI (`@novu/novu`) | NOT_IMPLEMENTED | Platform / Tooling | P3 |
| NV-062 | MCP server and agent toolkit (`apps/mcp-server`, `packages/agent-toolkit`) | NOT_IMPLEMENTED | Agents / Notifications | P3 |
| NV-063 | Agent Communication Infrastructure (ACI) | NOT_IMPLEMENTED | Agents / Support | P3 |
| NV-064 | Web Chat channel | NOT_IMPLEMENTED | Support / UI | P3 |
| NV-065 | Workflow-assigned agents | NOT_IMPLEMENTED | Agents / Notifications | P3 |
| NV-066 | Environments (Development, Production, custom) | PARTIALLY_IMPLEMENTED | Workspace / Configuration | P2 |
| NV-067 | Environment variables (`env.*` in templates) | LICENSING_RESTRICTED | Workspace / Configuration | P3 |
| NV-068 | Organizations and workspace configuration | VERIFIED_COMPLETE | Workspace / Configuration | P0 |
| NV-069 | Team members and organization roles (community model) | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Identity / Access | P0 |
| NV-070 | Dashboard RBAC on Team and Enterprise plans | LICENSING_RESTRICTED | Identity / Access | P2 |
| NV-071 | API keys (`ApiKeyStrategy`, rotation) | VERIFIED_COMPLETE | notifications | P2 |
| NV-072 | Community authentication (email/password, JWT, subscriber tokens) | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Identity / Access | P0 |
| NV-073 | Contexts and multi-tenant notification scoping | VERIFIED_COMPLETE | notifications | P2 |
| NV-074 | Workflow and layout translations | LICENSING_RESTRICTED | Notifications / Content | P3 |
| NV-075 | No-code editors, layouts and block email editor (`libs/maily-*`) | NOT_IMPLEMENTED | Notifications / Content | P2 |
| NV-076 | Custom domains | LICENSING_RESTRICTED | Workspace / Configuration | P3 |
| NV-077 | Billing and plan limits | LICENSING_RESTRICTED | Platform / Commercial | P3 |
| NV-078 | Compliance certifications, DPA, HIPAA BAA, SOC 2 and ISO 27001 | LICENSING_RESTRICTED | Platform / Compliance | P3 |
| NV-079 | Remove Novu branding | LICENSING_RESTRICTED | Notifications / UI | P3 |
| NV-080 | Self-hosting stack (MongoDB, Redis, S3, multi-service Docker Compose) | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Deployment | P2 |
| NV-081 | BullMQ queues, workers and health indicators | VERIFIED_COMPLETE | Jobs / Delivery | P1 |
| NV-082 | MongoDB persistence via Mongoose with runtime index creation | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Data | P0 |
| NV-083 | S3-compatible object storage | NOT_IMPLEMENTED | Platform / Storage | P3 |
| NV-084 | Enterprise proprietary packages (`enterprise/packages/auth`, `billing`, `dal`, `shared-services`, `translation`) and `*ee*` UI paths | LICENSING_RESTRICTED | Platform / Legal boundary | P0 |
| NV-085 | Message records API (`messages`) | VERIFIED_COMPLETE | Notifications / Records | P1 |
| NV-086 | Notification feeds API (`feeds`) | VERIFIED_COMPLETE | notifications | P2 |
| NV-087 | Layouts / layout management (`layouts`) | VERIFIED_COMPLETE | notifications | P2 |
| NV-088 | User management API (`user` controller) | PARTIALLY_IMPLEMENTED | Identity / Access | P2 |
| NV-089 | WebSocket delivery service (`apps/ws`) | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Notifications / Real-time | P1 |
| NV-090 | Dashboard and human-dashboard React apps | PARTIALLY_IMPLEMENTED | Platform / UI | P2 |
| NV-091 | Agent inbox MCP bridge (`apps/agent-inbox-mcp`) | NOT_IMPLEMENTED | Agents / MCP | P3 |
| NV-092 | Agent event protocol (`packages/agent-event-protocol`) | NOT_IMPLEMENTED | Agents / Events | P3 |
| NV-093 | Managed Novu Cloud service | LICENSING_RESTRICTED | Platform / Commercial | P3 |
| NV-094 | `@novu/nextjs` SDK | NOT_IMPLEMENTED | Notifications / SDK | P3 |
| NV-095 | `@novu/stateless` provider utilities | NOT_IMPLEMENTED | Integrations / Adapters | P3 |
| NV-096 | Ad-hoc data/encryption migration scripts | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Data | P2 |
| NV-097 | Idempotency and rate limiting configuration flags | PARTIALLY_IMPLEMENTED | Platform / Configuration | P2 |
| NV-098 | Observability integrations (Sentry, New Relic) | EXTERNAL_DEPENDENCY_BLOCKED | Platform / Observability | P3 |
| NV-099 | Personalize content (`{{variables}}` and LiquidJS filters) | VERIFIED_COMPLETE | Notifications / Content | P1 |
| NV-100 | Channels template editors | NOT_IMPLEMENTED | Notifications / Content | P2 |
| NV-101 | Inbox styling, theming and custom chrome | PARTIALLY_IMPLEMENTED | Notifications / UI | P3 |
| NV-102 | API error model and cursor pagination | PARTIALLY_IMPLEMENTED | Platform / API | P2 |
| NV-103 | Platform limits and quotas | VERIFIED_COMPLETE | notifications | P2 |
| NV-104 | Broadcast event API | VERIFIED_COMPLETE | notifications | P2 |
| NV-105 | Cancel triggered event API | PARTIALLY_IMPLEMENTED | Jobs / Workflow | P2 |
| NV-106 | Notification event list and retrieve API | VERIFIED_COMPLETE | Operations / Audit | P1 |
| NV-107 | Subscriber search and bulk create | VERIFIED_COMPLETE | notifications | P2 |
| NV-108 | Agent management API and bridge registration | NOT_IMPLEMENTED | Agents / API | P3 |
| NV-109 | Managed Agent runtime | LICENSING_RESTRICTED | Agents / Platform | P3 |
| NV-110 | AI framework adapters (`@novu/framework/ai-sdk`, `langchain`, Mastra, Claude) | NOT_IMPLEMENTED | Agents / SDK | P3 |
| NV-111 | Web Chat messages and conversation timeline | NOT_IMPLEMENTED | Support / UI | P3 |
| NV-112 | Web Chat tool approval and generative UI | NOT_IMPLEMENTED | Agents / UI | P3 |
| NV-113 | Web Chat HMAC security | NOT_IMPLEMENTED | Security / Agents | P2 |
| NV-114 | Custom code agent bridge and handlers | NOT_IMPLEMENTED | Agents / SDK | P3 |
| NV-115 | Agent conversation observability | PARTIALLY_IMPLEMENTED | Operations / Agents | P3 |
| NV-116 | Data residency and regional API endpoints | LICENSING_RESTRICTED | Platform / Compliance | P3 |
| NV-117 | Novu Agent Skills | NOT_IMPLEMENTED | Platform / Tooling | P3 |
| NV-118 | Community feature flags | VERIFIED_COMPLETE | notifications | P3 |
| NV-119 | Source test suite and coverage tooling (389 Jest/Mocha/Vitest specs) | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Platform / Testing | P2 |

### Marketing Skills (MK) — 53 features

| ID | Exact source feature name | Current status | NOVARA module | Priority |
| --- | --- | --- | --- | --- |
| MK-001 | ab-testing | VERIFIED_COMPLETE | Marketing skills reference library | P1 |
| MK-002 | ad-creative | NOT_IMPLEMENTED | Marketing Skills → ad creative brief and review template; Campaign Studio | P2 |
| MK-003 | ads | NOT_IMPLEMENTED | Marketing Skills → paid campaign plan/diagnosis workflow; adjacent Campaign Studio (`modules/marketing.py`) | P2 |
| MK-004 | ai-seo | NOT_IMPLEMENTED | Marketing Skills → AI search visibility audit workflow; SEO workspace | P2 |
| MK-005 | analytics | VERIFIED_COMPLETE | Marketing skills reference library | P1 |
| MK-006 | aso | NOT_IMPLEMENTED | Marketing Skills → app listing audit template; Distribution workspace | P3 |
| MK-007 | attribution | NOT_IMPLEMENTED | Marketing Skills → channel attribution review workflow; adjacent Campaign Studio and Analytics & Experiments | P2 |
| MK-008 | churn-prevention | NOT_IMPLEMENTED | Marketing Skills → retention playbook workflow; adjacent Feedback and Customer Inbox modules | P2 |
| MK-009 | co-marketing | NOT_IMPLEMENTED | Marketing Skills → partner campaign planner; Campaign Studio | P3 |
| MK-010 | cold-email | NOT_IMPLEMENTED | Marketing Skills → approved cold-outreach draft generator; adjacent Sales Autopilot approval gate | P2 |
| MK-011 | community-marketing | NOT_IMPLEMENTED | Marketing Skills → community plan template; Growth workspace | P3 |
| MK-012 | competitor-profiling | NOT_IMPLEMENTED | Marketing Skills → dated competitor profile workflow; Marketing Intelligence / Sales research | P2 |
| MK-013 | competitors | NOT_IMPLEMENTED | Marketing Skills → comparison-page audit template; Content workspace | P2 |
| MK-014 | content-strategy | NOT_IMPLEMENTED | Marketing Skills → editorial calendar / topic-cluster planner; Content workspace | P2 |
| MK-015 | conversion-tracking | VERIFIED_COMPLETE | Marketing skills reference library | P1 |
| MK-016 | copy-editing | NOT_IMPLEMENTED | Marketing Skills → point-edit copy tool; Content workspace | P2 |
| MK-017 | copywriting | VERIFIED_COMPLETE | Marketing skills reference library | P1 |
| MK-018 | cro | VERIFIED_COMPLETE | Marketing skills reference library | P1 |
| MK-019 | customer-research | NOT_IMPLEMENTED | Marketing Skills → interview/synthesis workflow; adjacent Feedback and CRM modules | P2 |
| MK-020 | directory-submissions | NOT_IMPLEMENTED | Marketing Skills → directory submission tracker; Launch workspace | P3 |
| MK-021 | emails | NOT_IMPLEMENTED | Marketing Skills → lifecycle email sequence builder; Campaign Studio | P2 |
| MK-022 | events | NOT_IMPLEMENTED | Marketing Skills → event plan template; Marketing operations | P3 |
| MK-023 | free-tools | NOT_IMPLEMENTED | Marketing Skills → free-tool idea evaluator; Growth workspace | P3 |
| MK-024 | image | NOT_IMPLEMENTED | Marketing Skills → AI-assisted marketing image brief/generator; Content workspace | P3 |
| MK-025 | influencer-marketing | NOT_IMPLEMENTED | Marketing Skills → creator partnership planner; Marketing operations | P3 |
| MK-026 | launch | NOT_IMPLEMENTED | Marketing Skills → launch checklist / GTM planner; Launch workspace | P2 |
| MK-027 | lead-magnets | NOT_IMPLEMENTED | Marketing Skills → lead-magnet planner; Campaign Studio | P3 |
| MK-028 | link-building | NOT_IMPLEMENTED | Marketing Skills → backlink opportunity planner; SEO workspace | P2 |
| MK-029 | marketing-council | NOT_IMPLEMENTED | Marketing Skills → multi-perspective decision agent; AI agent center | P3 |
| MK-030 | marketing-ideas | NOT_IMPLEMENTED | Marketing Skills → idea backlog generator; Marketing operations | P2 |
| MK-031 | marketing-loops | NOT_IMPLEMENTED | Marketing Skills → scheduled marketing agent loop; adjacent Jobs and Agent Center modules | P2 |
| MK-032 | marketing-plan | NOT_IMPLEMENTED | Marketing Skills → go-to-market plan builder; Marketing operations | P2 |
| MK-033 | marketing-psychology | NOT_IMPLEMENTED | Marketing Skills → persuasion ethics review template; CRO / Content | P2 |
| MK-034 | offers | NOT_IMPLEMENTED | Marketing Skills → offer design template; Pricing / Sales workspace | P3 |
| MK-035 | onboarding | NOT_IMPLEMENTED | Marketing Skills → activation checklist workflow; Product / Customer Inbox | P2 |
| MK-036 | paywalls | NOT_IMPLEMENTED | Marketing Skills → in-app upgrade moment review; Pricing workspace | P3 |
| MK-037 | popups | NOT_IMPLEMENTED | Marketing Skills → popup plan/review template; CRO workspace | P3 |
| MK-038 | pricing | NOT_IMPLEMENTED | Marketing Skills → pricing and packaging workbook; Pricing workspace | P2 |
| MK-039 | product-marketing | VERIFIED_COMPLETE | Marketing skills reference library | P1 |
| MK-040 | programmatic-seo | NOT_IMPLEMENTED | Marketing Skills → scaled page-set evaluator; SEO workspace | P2 |
| MK-041 | prospecting | NOT_IMPLEMENTED | Marketing Skills → prospect research workflow; adjacent Sales Autopilot (clean-room, no Sellbird AGPL code) | P2 |
| MK-042 | public-relations | NOT_IMPLEMENTED | Marketing Skills → press pitch and response planner; Marketing operations | P3 |
| MK-043 | referrals | NOT_IMPLEMENTED | Marketing Skills → referral program planner; Growth workspace | P2 |
| MK-044 | reverse-engineer-marketing | NOT_IMPLEMENTED | Marketing Skills → growth teardown workflow; Marketing Intelligence | P2 |
| MK-045 | revops | NOT_IMPLEMENTED | Marketing Skills → lifecycle/stage/routing design workflow; adjacent CRM, Marketing and Sales modules | P2 |
| MK-046 | sales-enablement | NOT_IMPLEMENTED | Marketing Skills → battle card and sales collateral generator; Sales workspace | P2 |
| MK-047 | schema | NOT_IMPLEMENTED | Marketing Skills → JSON-LD validation workflow; SEO workspace | P2 |
| MK-048 | seo-audit | VERIFIED_COMPLETE | Marketing skills reference library | P1 |
| MK-049 | signup | NOT_IMPLEMENTED | Marketing Skills → signup flow audit workflow; Product / CRO | P2 |
| MK-050 | site-architecture | NOT_IMPLEMENTED | Marketing Skills → site hierarchy and URL planner; SEO / Content workspace | P2 |
| MK-051 | sms | NOT_IMPLEMENTED | Marketing Skills → SMS and WhatsApp draft/compliance review; Campaign Studio | P3 |
| MK-052 | social | NOT_IMPLEMENTED | Marketing Skills → organic social calendar and draft generator; Content workspace / Self-marketing | P2 |
| MK-053 | video | NOT_IMPLEMENTED | Marketing Skills → AI-assisted video production plan; Content workspace | P3 |

### Sellbird (SB) — 80 features

| ID | Exact source feature name | Current status | NOVARA module | Priority |
| --- | --- | --- | --- | --- |
| SB-001 | Discovery providers | EXTERNAL_DEPENDENCY_BLOCKED | none found | P2 |
| SB-002 | Company discovery run | EXTERNAL_DEPENDENCY_BLOCKED | CRM / Leads (manual only) | P1 |
| SB-003 | Discovery cost estimation | NOT_IMPLEMENTED | none found | P2 |
| SB-004 | Decision-maker discovery | EXTERNAL_DEPENDENCY_BLOCKED | CRM / Contacts (manual only) | P1 |
| SB-005 | Website profiling | EXTERNAL_DEPENDENCY_BLOCKED | CRM / Companies (manual record only) | P2 |
| SB-006 | Email pattern finding | EXTERNAL_DEPENDENCY_BLOCKED | none found | P2 |
| SB-007 | Email verification | EXTERNAL_DEPENDENCY_BLOCKED | none found | P1 |
| SB-008 | 29-signal catalog | VERIFIED_COMPLETE | Sales / Engagement governance | P2 |
| SB-009 | 26 free signals | VERIFIED_COMPLETE | Sales / Engagement governance | P2 |
| SB-010 | Paid signals require explicit confirmation | VERIFIED_COMPLETE | Sales / Engagement governance | P2 |
| SB-011 | Observation-row signal model | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Shared event spine | P2 |
| SB-012 | Governed signal vocabulary and `signal_codes` | VERIFIED_COMPLETE | Sales / Engagement governance | P3 |
| SB-013 | Company records / `companies_list` | VERIFIED_COMPLETE | Sellbird / Company Records | P2 |
| SB-014 | Prospect records / `prospects_list` | VERIFIED_COMPLETE | CRM / Leads | P1 |
| SB-015 | Cohort builder | VERIFIED_COMPLETE | Sales / Engagement governance | P3 |
| SB-016 | Campaign records / `campaigns_list` | PARTIALLY_IMPLEMENTED | Marketing / Campaigns | P2 |
| SB-017 | Campaign and sequence drafting | VERIFIED_COMPLETE | Sales / Engagement governance | P2 |
| SB-018 | Personalised cold email writing | VERIFIED_COMPLETE | Workflow / Outreach drafts | P1 |
| SB-019 | Offer suggestion | VERIFIED_COMPLETE | Sales / Engagement governance | P3 |
| SB-020 | Outbox approval | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Workflow / Outreach approval | P0 |
| SB-021 | Outbox review and `outbox_list` | VERIFIED_COMPLETE | Workflow / Outreach drafts | P1 |
| SB-022 | Durable Outbox send queue and status ladder | VERIFIED_COMPLETE | Sales / Engagement governance | P2 |
| SB-023 | Autopilot opt-in | VERIFIED_COMPLETE | Sales / Engagement governance | P3 |
| SB-024 | Deterministic pre-send gate | VERIFIED_COMPLETE | Workflow / Outreach approval | P1 |
| SB-025 | Sending via mail providers | EXTERNAL_DEPENDENCY_BLOCKED | Adapters (local mock only) | P1 |
| SB-026 | Sending status and pause | VERIFIED_COMPLETE | Sales / Engagement governance | P2 |
| SB-027 | Multiple mailboxes and mailbox connections | EXTERNAL_DEPENDENCY_BLOCKED | Integrations (configuration only) | P2 |
| SB-028 | Send rules and header extension points | VERIFIED_COMPLETE | Sales / Engagement governance | P3 |
| SB-029 | Reply classification and `processed_replies` | EXTERNAL_DEPENDENCY_BLOCKED | none found | P2 |
| SB-030 | Opt-out handling | VERIFIED_COMPLETE | Outreach safety / Compliance | P1 |
| SB-031 | Suppression / do-not-contact | VERIFIED_COMPLETE | Outreach safety / Compliance | P1 |
| SB-032 | Bounce handling and bounce kill switch | EXTERNAL_DEPENDENCY_BLOCKED | none found | P2 |
| SB-033 | Conversation tracking / `conversations_list` | NOT_IMPLEMENTED | Support (tickets are a different object) | P2 |
| SB-034 | Feedback records | NOT_IMPLEMENTED | Feedback (surveys are a different object) | P3 |
| SB-035 | Action logging / activity feed | VERIFIED_COMPLETE | Shared event spine / Operations | P1 |
| SB-036 | Usage and quota tracking | PARTIALLY_IMPLEMENTED | Operations | P2 |
| SB-037 | CSV export | NOT_IMPLEMENTED | none found | P3 |
| SB-038 | Multi-agent pipeline | VERIFIED_COMPLETE | Agent center | P1 |
| SB-039 | Scout agent role | NOT_IMPLEMENTED | Agent center (configuration only) | P2 |
| SB-040 | Writer agent role | NOT_IMPLEMENTED | Agent center (configuration only) | P2 |
| SB-041 | Handler agent role | NOT_IMPLEMENTED | Agent center (configuration only) | P2 |
| SB-042 | Sender agent role | VERIFIED_COMPLETE | Adapters / Security | P1 |
| SB-043 | LinkedIn-related agent roles | NOT_IMPLEMENTED | none found | P3 |
| SB-044 | Editable Markdown agent skills | NOT_IMPLEMENTED | none found | P3 |
| SB-045 | Brain model layer using operator Claude/Codex CLI | EXTERNAL_DEPENDENCY_BLOCKED | Agent center (governor only) | P3 |
| SB-046 | Agent route extension points | NOT_IMPLEMENTED | Agent center | P3 |
| SB-047 | Heartbeat loop | PARTIALLY_IMPLEMENTED | Jobs / Operations | P2 |
| SB-048 | Quiet hours and interruptible sleep | NOT_IMPLEMENTED | none found | P3 |
| SB-049 | PID/lock file preventing duplicate loops | NOT_IMPLEMENTED | Jobs (stale recovery only) | P2 |
| SB-050 | Extension tick steps with timeout | NOT_IMPLEMENTED | none found | P3 |
| SB-051 | FastAPI dashboard with static web UI | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Web client | P1 |
| SB-052 | Dashboard API surface | PARTIALLY_IMPLEMENTED | Multiple NOVARA modules | P2 |
| SB-053 | Setup status | NOT_IMPLEMENTED | Auth / Workspace bootstrap | P2 |
| SB-054 | Settings and settings table | PARTIALLY_IMPLEMENTED | Settings / Integrations | P2 |
| SB-055 | Sending mode configuration | VERIFIED_COMPLETE | Sales / Engagement governance | P2 |
| SB-056 | Process start/stop and logs | PARTIALLY_IMPLEMENTED | Operations | P3 |
| SB-057 | Today view | NOT_IMPLEMENTED | Operations / Dashboard | P3 |
| SB-058 | Stats and instance information | PARTIALLY_IMPLEMENTED | Operations | P3 |
| SB-059 | Dashboard docs disabled | NOT_IMPLEMENTED | API framework | P3 |
| SB-060 | Dashboard bearer token authentication | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Auth / Sessions | P0 |
| SB-061 | Loopback bind, Host and origin checks, security headers | VERIFIED_COMPLETE | API security | P0 |
| SB-062 | Separate agent token with read/pause-only MCP permissions | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Agent center / Permissions | P0 |
| SB-063 | MCP server toolset | NOT_IMPLEMENTED | none found | P3 |
| SB-064 | SSRF-safe public HTTP | EXTERNAL_DEPENDENCY_BLOCKED | none found | P2 |
| SB-065 | Extension entry-point registry | PARTIALLY_IMPLEMENTED | Module registry | P3 |
| SB-066 | CLI commands | NOT_IMPLEMENTED | none found | P3 |
| SB-067 | Docker deployment | EXTERNAL_DEPENDENCY_BLOCKED | Deployment | P3 |
| SB-068 | Desktop tray support | NOT_IMPLEMENTED | none found | P3 |
| SB-069 | Local SQLite persistence at `data/sellbird.db` | INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION | Database | P0 |
| SB-070 | Linear idempotent migrations via `PRAGMA user_version` | PARTIALLY_IMPLEMENTED | Database migrations | P2 |
| SB-071 | WAL journal mode and busy timeout | NOT_IMPLEMENTED | Database | P3 |
| SB-072 | Pluggable storage backend boundary | NOT_IMPLEMENTED | Database | P3 |
| SB-073 | Hosted managed domains | EXTERNAL_DEPENDENCY_BLOCKED | none found | P3 |
| SB-074 | Hosted managed inboxes | EXTERNAL_DEPENDENCY_BLOCKED | none found | P3 |
| SB-075 | Hosted warmup | EXTERNAL_DEPENDENCY_BLOCKED | none found | P3 |
| SB-076 | Hosted DNS management | EXTERNAL_DEPENDENCY_BLOCKED | none found | P3 |
| SB-077 | Hosted managed sending | EXTERNAL_DEPENDENCY_BLOCKED | Adapters (local mock only) | P3 |
| SB-078 | Cross-platform CI and packaging verification | EXTERNAL_DEPENDENCY_BLOCKED | Test suite | P3 |
| SB-079 | Compliance footer on outbound email | VERIFIED_COMPLETE | Outreach safety / Compliance | P1 |
| SB-080 | Prompt-injection and provider isolation safeguards | NOT_IMPLEMENTED | Agent center / Adapters | P2 |
