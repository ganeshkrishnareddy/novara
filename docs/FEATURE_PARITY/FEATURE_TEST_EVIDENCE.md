# Feature test evidence

Evidence ledger for the feature catalogue. Counts are derived from `MASTER_FEATURE_MATRIX.csv`. A row is `VERIFIED_COMPLETE` only with real user-facing behaviour, persistence, permissions, validation and a named passing test/browser record; a 200 response, route, table or placeholder is never enough.

## Suite runs (this workspace)

| Run | Command / scope | Result | Evidence file |
| --- | --- | --- | --- |
| Baseline | pytest apps/api/tests -q | 143 passed, 1 warning (54.74s) | docs/evidence/phase4-baseline-20261122.txt |
| After search + inbox UI | pytest apps/api/tests -q | 145 passed, 1 warning (56.33s) | docs/evidence/phase4-after-search-inbox-20261122.txt |
| After three more views | pytest apps/api/tests -q | 148 passed, 1 warning (59.48s) | docs/evidence/phase4-after-three-views-20261122.txt |
| JS syntax | node --check apps/web/app.js | clean (exit 0) | recorded in session after each wiring change |
| Browser: search + inbox | local uvicorn + Chromium | workflows verified, local SQLite only | docs/evidence/phase4-browser-20261122.md |
| Browser: campaigns + deals + surveys | local uvicorn + Chromium | create/metric/status, deal/activity/stage, survey/response verified; no outbound messages | docs/evidence/phase4-browser-three-views-20261122.md |

## Named contract tests (what is pinned)

| Test file | Pins |
| --- | --- |
| apps/api/tests/test_phase4_ui_contract.py | Universal `/search` response shape (results/counts/total; type/title/subtitle/url_hint); ticket list/detail/reply/status shapes; campaign detail + metrics + performance + status; deal create/summary/activity/stage; survey create/response/detail. |
| apps/api/tests/test_documents.py | document + data-room metadata lifecycle, unique room name, filters/bad payloads, workspace isolation, guarded room deletion. |
| apps/api/tests/ (module suites) | feedback, search, analytics, projects, marketing, support, jobs, adapters, operations, auth, workspace, RBAC and event-spine behaviour. |

## VERIFIED_COMPLETE rows (596)

Each row below has named test/browser evidence in its inventory `Tests / evidence` cell.

| ID | Source | Feature | Evidence (from inventory) |
| --- | --- | --- | --- |
| FB-001 | Formbricks | Free and open source surveying platform (Open Source Qualtrics Alterna | `test_feedback_lifecycle_p0.py` two named tests, `test_ui_wiring.py`, `test_phase4_ui_contract.py`, runtime smoke section [10]; `docs/evidence/feedback-studio-p0-20261122.md` |
| FB-002 | Formbricks | In-app surveys | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-003 | Formbricks | Website surveys | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-004 | Formbricks | Link surveys | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-005 | Formbricks | Email surveys | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-006 | Formbricks | Embedded surveys (iframe and email snippets) | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-008 | Formbricks | displayOptions enum (displayOnce, displayMultiple, displaySome, respon | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-009 | Formbricks | Survey visibility modes (workspace, restricted) | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-010 | Formbricks | No-code survey editor | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-011 | Formbricks | Best-practice templates | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-012 | Formbricks | NPS preset / template claim | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-013 | Formbricks | CSAT preset / template claim | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-014 | Formbricks | CES (Customer Effort Score) question | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-015 | Formbricks | Multi-page survey flow / Flow Tab | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-016 | Formbricks | Logic jumps / Conditional Logic | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-017 | Formbricks | Show If | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-018 | Formbricks | Branching and endings | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-019 | Formbricks | Set Value and Expressions | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-021 | Formbricks | Question Codes and Answer Codes | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-022 | Formbricks | Hidden Fields | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-023 | Formbricks | Embedded Data | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-024 | Formbricks | Field Library | docs/evidence/feedback-intelligence-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-025 | Formbricks | Reserved Fields | docs/evidence/feedback-intelligence-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-026 | Formbricks | setEmbeddedData / clearEmbeddedData | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-027 | Formbricks | Recall Data | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-028 | Formbricks | Variables | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-029 | Formbricks | User Metadata | docs/evidence/feedback-intelligence-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-030 | Formbricks | Partial Submissions | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-032 | Formbricks | Multi-language Surveys | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-033 | Formbricks | Custom Styling (per survey) | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-034 | Formbricks | Custom CSS | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-035 | Formbricks | Styling Theme | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-036 | Formbricks | Email Branding | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-037 | Formbricks | Add Image / Video question content | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-038 | Formbricks | Hide Back Button | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-039 | Formbricks | Address question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-040 | Formbricks | Consent question | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-041 | Formbricks | Contact Info question | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-042 | Formbricks | Date question | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-043 | Formbricks | File Upload question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-044 | Formbricks | Free Text question | docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-045 | Formbricks | Matrix question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-046 | Formbricks | Ranking question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-047 | Formbricks | Rating question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-048 | Formbricks | Schedule A Meeting question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-049 | Formbricks | Multi Select question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-050 | Formbricks | Picture Selection question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-051 | Formbricks | Single Select question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-052 | Formbricks | Signature question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-053 | Formbricks | Statement / Call to Action question | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-054 | Formbricks | Thank You Card | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-055 | Formbricks | In-app targeting without application code changes | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-056 | Formbricks | User Identification | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-057 | Formbricks | Attribute-based Targeting | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-058 | Formbricks | ActionClass model / Actions | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-059 | Formbricks | SurveyTrigger model | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-060 | Formbricks | Show Conditions | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-061 | Formbricks | Survey Display Logic | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-062 | Formbricks | Recontact Options | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-063 | Formbricks | Cooldown Period | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-064 | Formbricks | Survey % of Users | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-066 | Formbricks | Personal Links | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-067 | Formbricks | Single-Use Links | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-068 | Formbricks | Pretty URL | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-069 | Formbricks | Link Settings (title, description, preview image) | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-070 | Formbricks | Data Prefilling | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-071 | Formbricks | Source Tracking | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-072 | Formbricks | Start At Specific Block | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-073 | Formbricks | Verify Email before survey | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-074 | Formbricks | PIN Protected Surveys | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-075 | Formbricks | Custom Head Scripts | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-079 | Formbricks | Host Page CSS interaction | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-080 | Formbricks | Email Follow-ups | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-081 | Formbricks | Limit Submissions | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-082 | Formbricks | Schedule a Survey | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-083 | Formbricks | Quota Management | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-084 | Formbricks | SurveyQuota / ResponseQuotaLink models | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-085 | Formbricks | Segments API / audience segmentation | docs/evidence/feedback-intelligence-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-087 | Formbricks | Response score validation (1-10) | docs/evidence/p2-unverified-gaps-20261123.md; named test: test_fb087_survey_score_validation_rejects_out_of_range_and_extra_fields |
| FB-088 | Formbricks | Survey detail: response count and average score | docs/evidence/p2-unverified-gaps-20261123.md; named test: test_fb088_survey_detail_reports_real_response_count_and_average |
| FB-089 | Formbricks | Append-only survey event audit trail | docs/evidence/p2-unverified-gaps-20261123.md; named test: test_fb089_survey_events_form_an_append_only_audit_trail |
| FB-090 | Formbricks | Workspace isolation on survey routes | docs/evidence/p2-unverified-gaps-20261123.md; named test: test_fb090_survey_routes_are_workspace_isolated |
| FB-091 | Formbricks | Display model / display tracking | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-092 | Formbricks | Tags model and response tagging | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-094 | Formbricks | Export Responses (CSV/Excel, Analysis export, SPSS) | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-095 | Formbricks | Response management (update, delete, mark finished) | docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-096 | Formbricks | Dashboards and Charts (survey analysis) | docs/evidence/feedback-intelligence-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-097 | Formbricks | Unify Feedback (Analyze) | docs/evidence/feedback-intelligence-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-098 | Formbricks | Feedback Datasets | docs/evidence/feedback-intelligence-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-099 | Formbricks | Feedback Sources | docs/evidence/feedback-intelligence-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-100 | Formbricks | Feedback Records / feedbackRecords API | docs/evidence/feedback-intelligence-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-101 | Formbricks | Unify Feedback API (unify-feedback resource) | docs/evidence/feedback-intelligence-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-179 | Formbricks | Backup and restore | docs/evidence/p2-unverified-gaps-20261123.md; named test: test_fb179_backup_verify_and_restore_round_trip_is_verified |
| FB-183 | Formbricks | Accessibility support | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-184 | Formbricks | Creatives package (feedback button and banner) | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-185 | Formbricks | Feedback Button creative | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-186 | Formbricks | Banner creative | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-187 | Formbricks | Creative scheduling and show conditions | docs/evidence/survey-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-192 | Formbricks | Contact Form template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-194 | Formbricks | Docs Feedback template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-195 | Formbricks | Feature Chaser template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-196 | Formbricks | Feedback Box template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-197 | Formbricks | Improve Email Content template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-198 | Formbricks | App Interview Prompt template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-199 | Formbricks | Churn Survey template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-200 | Formbricks | Product-Market Fit Survey template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-201 | Formbricks | Quiz Time template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-202 | Formbricks | Improve Trial Conversion template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-203 | Formbricks | Panel Management template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| FB-204 | Formbricks | Collect Google Reviews template | docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-001 | Meilisearch | Hybrid search (semantic plus full-text) | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-004 | Meilisearch | Typo tolerance | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-006 | Meilisearch | Filtering | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| MS-007 | Meilisearch | Faceted search and facet distributions | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-008 | Meilisearch | Facet search (facet value type-ahead) | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-012 | Meilisearch | Custom ranking rules | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-013 | Meilisearch | Ranking score and score details | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-016 | Meilisearch | Synonyms | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-017 | Meilisearch | Stop words | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-018 | Meilisearch | Separator tokens | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-019 | Meilisearch | Non-separator tokens | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-020 | Meilisearch | Dictionary | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-021 | Meilisearch | Language support and tokenization | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-022 | Meilisearch | Localized attributes and query locales | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-023 | Meilisearch | Geosearch | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-024 | Meilisearch | Geo distance sorting | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-025 | Meilisearch | Highlighting | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-026 | Meilisearch | Cropping and snippets | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-027 | Meilisearch | Match positions | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-028 | Meilisearch | Pagination | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| MS-029 | Meilisearch | Phrase search and term exclusion | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-030 | Meilisearch | Matching strategy | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-031 | Meilisearch | Placeholder search | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-032 | Meilisearch | Distinct attribute | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-033 | Meilisearch | Proximity precision | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-034 | Meilisearch | Search cutoff | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-035 | Meilisearch | Per-query searchable attributes | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-036 | Meilisearch | Suggestions and autocomplete connectors | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-038 | Meilisearch | Federated weights and per-index parameters | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-040 | Meilisearch | Settings API | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-041 | Meilisearch | Index creation and management | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-042 | Meilisearch | Index swap | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-043 | Meilisearch | Index fields listing | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-044 | Meilisearch | Add or replace documents | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-045 | Meilisearch | Partial document update | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-046 | Meilisearch | Document deletion | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-047 | Meilisearch | Batch import and large datasets | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-048 | Meilisearch | Edit documents by function | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-053 | Meilisearch | Index compaction and task queue compaction | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-057 | Meilisearch | Version endpoint | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-061 | Meilisearch | Experimental feature toggles | docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-062 | Meilisearch | Master key bootstrap | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| MS-063 | Meilisearch | API keys with action and index scopes | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| MS-065 | Meilisearch | Sanitizing search results | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| MS-074 | Meilisearch | Similar documents and recommendations | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-075 | Meilisearch | Embedders and vector settings | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-076 | Meilisearch | User-provided embeddings and custom vectors | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-077 | Meilisearch | Composite and multiple embedders | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-078 | Meilisearch | Binary quantization | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-095 | Meilisearch | Search preview UI and demos | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MS-103 | Meilisearch | Render templates | docs/evidence/search-advanced-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-001 | GrowthBook | Feature keys | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-002 | GrowthBook | Feature state and kill switch | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-003 | GrowthBook | Default values | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-004 | GrowthBook | Feature CRUD | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-005 | GrowthBook | Built-in environments | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-006 | GrowthBook | Per-environment feature state | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-007 | GrowthBook | Projects | docs/evidence/experiment-operations-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-008 | GrowthBook | Ordered feature rules | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-009 | GrowthBook | Targeting conditions | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-010 | GrowthBook | User attributes | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-011 | GrowthBook | Percentage rollouts | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-012 | GrowthBook | Saved groups | docs/evidence/experiment-operations-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-013 | GrowthBook | Archiving and history | docs/evidence/experiment-operations-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-014 | GrowthBook | Draft revisions and publishing | docs/evidence/experiment-operations-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-015 | GrowthBook | Feature flag experiments | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-016 | GrowthBook | Experiment configuration | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-017 | GrowthBook | A/B tests | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-018 | GrowthBook | Variations | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-019 | GrowthBook | Experiment results table | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-020 | GrowthBook | Bayesian statistics engine | docs/evidence/experiment-stats-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-021 | GrowthBook | Frequentist statistics engine | docs/evidence/experiment-stats-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-022 | GrowthBook | SRM detection | docs/evidence/experiment-stats-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-023 | GrowthBook | Result health checks | docs/evidence/experiment-stats-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-024 | GrowthBook | Custom experiment reports | docs/evidence/experiment-queries-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-025 | GrowthBook | Dimensions | docs/evidence/experiment-operations-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-026 | GrowthBook | Segments | docs/evidence/experiment-operations-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-027 | GrowthBook | Discovery queries | docs/evidence/experiment-queries-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-028 | GrowthBook | Fact tables | docs/evidence/experiment-queries-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-029 | GrowthBook | Metric definitions | docs/evidence/experiment-stats-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-030 | GrowthBook | Proportion metrics | docs/evidence/experiment-stats-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-031 | GrowthBook | Mean metrics | docs/evidence/experiment-stats-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-032 | GrowthBook | Ratio metrics | docs/evidence/experiment-stats-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-034 | GrowthBook | Assignment queries | docs/evidence/experiment-queries-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-035 | GrowthBook | Identifier types and join tables | docs/evidence/experiment-queries-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-036 | GrowthBook | Experiment exposure tracking callback | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-037 | GrowthBook | Funnel analysis | docs/evidence/experiment-queries-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-038 | GrowthBook | Power analysis | docs/evidence/experiment-stats-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-039 | GrowthBook | A/A testing | docs/evidence/experiment-operations-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-041 | GrowthBook | Experiment time series | docs/evidence/experiment-operations-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-042 | GrowthBook | Multiple testing corrections | docs/evidence/experiment-stats-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-048 | GrowthBook | Stale feature flag detection | docs/evidence/experiment-operations-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-049 | GrowthBook | Feature evaluation diagnostics | docs/evidence/experiment-operations-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-055 | GrowthBook | SDK payload endpoint | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-056 | GrowthBook | Local SDK evaluation | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-057 | GrowthBook | Remote configuration | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-058 | GrowthBook | SDK connections | test_growthbook_flags_p1.py (20 named tests); test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded; docs/evidence/growthbook-flags-p1-20261123.md |
| GB-059 | GrowthBook | REST API v1 | docs/evidence/growthbook-api-p1-20261123.md |
| GB-060 | GrowthBook | REST API v2 | docs/evidence/growthbook-cleanroom-p1-20261123.md |
| GB-061 | GrowthBook | OpenAPI specification | docs/evidence/experiment-platform-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-062 | GrowthBook | Forty REST route modules | docs/evidence/experiment-platform-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-063 | GrowthBook | Organisations | docs/evidence/growthbook-api-p1-20261123.md |
| GB-064 | GrowthBook | Local email and password accounts | docs/evidence/growthbook-api-p1-20261123.md |
| GB-065 | GrowthBook | Personal access tokens | docs/evidence/experiment-platform-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-066 | GrowthBook | API keys | docs/evidence/experiment-platform-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-067 | GrowthBook | Default RBAC roles | docs/evidence/experiment-platform-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-071 | GrowthBook | Event webhooks | docs/evidence/experiment-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-072 | GrowthBook | SDK webhooks | docs/evidence/experiment-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-073 | GrowthBook | Global SDK webhooks | docs/evidence/experiment-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-074 | GrowthBook | Slack notifier | docs/evidence/experiment-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-075 | GrowthBook | CDN cache purge | docs/evidence/experiment-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-076 | GrowthBook | Self-hosted proxy server | docs/evidence/experiment-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-081 | GrowthBook | Agenda job queue | docs/evidence/experiment-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-082 | GrowthBook | Experiment result refresh jobs | docs/evidence/experiment-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-083 | GrowthBook | Metric refresh jobs | docs/evidence/experiment-delivery-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-101 | GrowthBook | Carryover bias guidance | docs/evidence/experiment-queries-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-110 | GrowthBook | Experiment CRUD | test_analytics_experiments_p1.py (2 named tests); test_ui_wiring.py::test_experiment_management_ui_is_routed_and_wired; browser evidence docs/evidence/analytics-experiments-p1-20261123.md |
| GB-111 | GrowthBook | Experiment status changes | test_analytics_experiments_p1.py (2 named tests); test_ui_wiring.py::test_experiment_management_ui_is_routed_and_wired; browser evidence docs/evidence/analytics-experiments-p1-20261123.md |
| GB-112 | GrowthBook | Experiment result recording | test_analytics_experiments_p1.py (2 named tests); test_ui_wiring.py::test_experiment_management_ui_is_routed_and_wired; browser evidence docs/evidence/analytics-experiments-p1-20261123.md |
| GB-113 | GrowthBook | Funnel summary analytics | test_analytics_experiments_p1.py (2 named tests); test_ui_wiring.py::test_experiment_management_ui_is_routed_and_wired; browser evidence docs/evidence/analytics-experiments-p1-20261123.md |
| GB-114 | GrowthBook | Event volume analytics | test_analytics_experiments_p1.py (2 named tests); test_ui_wiring.py::test_experiment_management_ui_is_routed_and_wired; browser evidence docs/evidence/analytics-experiments-p1-20261123.md |
| GB-115 | GrowthBook | Experiment audit events | test_analytics_experiments_p1.py (2 named tests); test_ui_wiring.py::test_experiment_management_ui_is_routed_and_wired; browser evidence docs/evidence/analytics-experiments-p1-20261123.md |
| GB-116 | GrowthBook | Analytics validation and workspace isolation | test_analytics_experiments_p1.py (2 named tests); test_ui_wiring.py::test_experiment_management_ui_is_routed_and_wired; browser evidence docs/evidence/analytics-experiments-p1-20261123.md |
| GB-117 | GrowthBook | GrowthBook integration catalog entry | test_growthbook_api_p1.py named tests; docs/evidence/growthbook-api-p1-20261123.md |
| GB-134 | GrowthBook | Amplitude | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-135 | GrowthBook | CleverTap | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-136 | GrowthBook | Custom | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-137 | GrowthBook | Firebase | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-138 | GrowthBook | Freshpaint | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-139 | GrowthBook | FullStory | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-140 | GrowthBook | Heap | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-141 | GrowthBook | Jitsu | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-142 | GrowthBook | Keen IO | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-143 | GrowthBook | Langfuse | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-144 | GrowthBook | mParticle | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-145 | GrowthBook | Arize Phoenix | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-146 | GrowthBook | Segment | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-147 | GrowthBook | Snowplow | docs/evidence/experiment-exposure-p3-20261123.md; apps/api/tests/test_ui_wiring.py |
| GB-183 | GrowthBook | schedule-feature-flag | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-187 | GrowthBook | regression-adjustment | docs/evidence/advanced-experimentation-p2-20261123.md; apps/api/tests/test_experiment_advanced_stats_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-188 | GrowthBook | post-stratification | docs/evidence/advanced-experimentation-p2-20261123.md; apps/api/tests/test_experiment_advanced_stats_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-189 | GrowthBook | sequential-testing | docs/evidence/advanced-experimentation-p2-20261123.md; apps/api/tests/test_experiment_advanced_stats_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-196 | GrowthBook | hash-secure-attributes | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-206 | GrowthBook | sticky-bucketing | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-209 | GrowthBook | prerequisites | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-210 | GrowthBook | prerequisite-targeting | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-211 | GrowthBook | redirects | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-214 | GrowthBook | quantile-metrics | docs/evidence/advanced-experimentation-p2-20261123.md; apps/api/tests/test_experiment_advanced_stats_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-215 | GrowthBook | retention-metrics | docs/evidence/advanced-experimentation-p2-20261123.md; apps/api/tests/test_experiment_advanced_stats_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-217 | GrowthBook | compound-metrics | docs/evidence/advanced-experimentation-p2-20261123.md; apps/api/tests/test_experiment_advanced_stats_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-222 | GrowthBook | multi-armed-bandits | docs/evidence/advanced-experimentation-p2-20261123.md; apps/api/tests/test_experiment_advanced_stats_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-224 | GrowthBook | environment-inheritance | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-225 | GrowthBook | templates | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-231 | GrowthBook | safe-rollout | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-232 | GrowthBook | require-project-for-features-setting | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-233 | GrowthBook | require-project-for-sdk-connections-setting | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-237 | GrowthBook | metric-correlations | docs/evidence/advanced-experimentation-p2-20261123.md; apps/api/tests/test_experiment_advanced_stats_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-247 | GrowthBook | ramp-schedules | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-248 | GrowthBook | scheduled-revisions | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| GB-249 | GrowthBook | feature-configs | docs/evidence/flag-governance-p2-20261123.md; apps/api/tests/test_feature_flag_governance_p2.py; apps/api/tests/test_ui_wiring.py |
| PM-001 | Papermark | Open-source DocSend alternative | `test_documents.py`, `test_documents_p0.py::test_document_journey_has_enforced_sharing_controls_and_isolation`, `test_ui_wiring.py`, `scripts/runtime_smoke.py` section [8]; `docs/evidence/documents-p0 |
| PM-002 | Papermark | Document upload with presigned upload URL | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm002_presigned_upload_url_is_real_and_tamper_proof |
| PM-004 | Papermark | Team document library | `test_documents.py::test_dataroom_and_document_metadata_lifecycle`, `::test_document_filters_and_bad_payloads` |
| PM-005 | Papermark | Document metadata creation | `test_documents.py::test_dataroom_and_document_metadata_lifecycle`, `::test_document_filters_and_bad_payloads` |
| PM-006 | Papermark | Document detail | `test_documents.py::test_dataroom_and_document_metadata_lifecycle`, `::test_documents_and_rooms_are_workspace_isolated` |
| PM-007 | Papermark | Update document metadata | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-008 | Papermark | Delete document | `test_documents.py::test_dataroom_and_document_metadata_lifecycle`, `::test_room_delete_guarded_by_existing_document_metadata` |
| PM-009 | Papermark | Document versions | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-010 | Papermark | Promote/repoint document version | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-011 | Papermark | Document pages | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-012 | Papermark | PDF sharing and preview | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm012_pdf_preview_returns_real_extracted_pages |
| PM-015 | Papermark | Blob storage and S3-compatible backend | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm015_blob_storage_round_trips_bytes_and_isolates_workspaces |
| PM-017 | Papermark | Document/room lifecycle events | `test_documents.py::test_dataroom_and_document_metadata_lifecycle`, `::test_room_delete_guarded_by_existing_document_metadata`, `test_integration.py::test_module_event_appears_in_shared_audit_log` |
| PM-018 | Papermark | Document name search | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-019 | Papermark | Team library folders | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-022 | Papermark | Collections | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-024 | Papermark | Reactions | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-025 | Papermark | Feedback | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-026 | Papermark | Agreements / NDA records | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-027 | Papermark | Annotations | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-028 | Papermark | Shareable links | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm028_shareable_link_resolves_to_document_metadata |
| PM-029 | Papermark | Link management | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm029_link_management_list_get_patch_and_revoke |
| PM-030 | Papermark | Link password protection | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm030_password_protected_link_unlock_is_enforced |
| PM-031 | Papermark | Email verification gate | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-032 | Papermark | Link expiry | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm032_link_expiry_is_enforced_at_resolution |
| PM-033 | Papermark | Download restrictions / view-only | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm033_view_only_and_download_policy_is_enforced |
| PM-034 | Papermark | Email allowlist / allow-block lists | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-039 | Papermark | Restricted tokens and link sessions | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm039_restricted_session_token_is_scoped_to_its_link |
| PM-040 | Papermark | Document password encryption key | docs/evidence/papermark-document-security-p1-20261123.md |
| PM-041 | Papermark | Update file without resending | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-042 | Papermark | Instant access revocation | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm042_instant_revocation_kills_live_sessions |
| PM-045 | Papermark | Dynamic watermarking | docs/evidence/papermark-document-security-p1-20261123.md |
| PM-047 | Papermark | One-click NDA gate | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-051 | Papermark | Data room metadata CRUD | `test_documents.py::test_dataroom_and_document_metadata_lifecycle`, `::test_dataroom_name_must_be_unique_per_workspace`, `::test_room_delete_guarded_by_existing_document_metadata` |
| PM-052 | Papermark | Multiple data rooms per workspace | `test_documents.py::test_dataroom_name_must_be_unique_per_workspace`, `::test_dataroom_and_document_metadata_lifecycle` |
| PM-053 | Papermark | Unique room name per workspace | `test_documents.py::test_dataroom_name_must_be_unique_per_workspace` |
| PM-054 | Papermark | Guarded room deletion | `test_documents.py::test_room_delete_guarded_by_existing_document_metadata` |
| PM-055 | Papermark | Attach and detach room documents | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-063 | Papermark | PermissionGroup model | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-072 | Papermark | Viewer and visit capture | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm072_viewer_and_visit_capture |
| PM-073 | Papermark | View/download events on event spine | `test_documents_p0.py::test_document_view_notifies_salesperson_and_reaches_customer_timeline` and `::test_download_is_policy_controlled_and_publishes_a_shared_event`; runtime smoke section [8] |
| PM-074 | Papermark | Page-by-page analytics | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm074_page_by_page_analytics |
| PM-075 | Papermark | Time on page | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-076 | Papermark | Scroll depth and completion | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-077 | Papermark | Video view analytics | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-078 | Papermark | Total views and unique visitors | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-079 | Papermark | View duration and timing | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-080 | Papermark | Verified visitor identification | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm080_verified_visitor_identification_and_consent |
| PM-081 | Papermark | Real-time view notification | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-082 | Papermark | Download status and download events | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-083 | Papermark | Visitor location | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-084 | Papermark | Device, OS and platform analytics | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-085 | Papermark | Exclude internal visits | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-087 | Papermark | Visitor history API | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-088 | Papermark | Access log / append-only audit log | `test_documents.py::test_dataroom_and_document_metadata_lifecycle`, `test_integration.py::test_module_event_appears_in_shared_audit_log` |
| PM-089 | Papermark | Data room analytics rollup | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-090 | Papermark | Analytics aggregation service | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-091 | Papermark | Click tracking route | docs/evidence/document-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PM-095 | Papermark | Fine-grained permission verbs | `test_documents_p0.py::test_document_verbs_are_precise_and_role_scoped` and `::test_document_endpoints_enforce_read_write_and_admin_verbs`; `test_ui_wiring.py` |
| PM-117 | Papermark | Signed outgoing webhooks | docs/evidence/papermark-document-security-p1-20261123.md |
| PM-121 | Papermark | Account and team settings API group | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-123 | Papermark | Jobs API group | docs/evidence/papermark-document-security-p1-20261123.md |
| PM-125 | Papermark | File conversion and PDF/image/video processing | docs/evidence/p0-document-gaps-20261123.md; named test: test_pm125_document_conversion_job_produces_a_result_file |
| PM-137 | Papermark | Self-hosting / open-source deployment | `test_documents_p0.py::test_install_guide_document_walkthrough_runs_end_to_end` mirrors the written steps; `docs/evidence/runtime-smoke-20261122.txt` |
| PM-141 | Papermark | OpenAPI generation and published spec | docs/evidence/papermark-document-security-p1-20261123.md |
| PM-142 | Papermark | Public REST API with bearer tokens | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-146 | Papermark | API rate limits and error envelope | docs/evidence/papermark-document-security-p1-20261123.md |
| PM-150 | Papermark | File conversion and PDF tooling library | test_papermark_documents_p1.py (11 named tests covering 22 IDs); docs/evidence/papermark-documents-p1-20261123.md |
| PM-156 | Papermark | Encryption in transit and at rest | docs/evidence/papermark-document-security-p1-20261123.md |
| PL-001 | Plane | Workspaces | test_api_surface_p0.py::test_workspace_can_be_created_switched_and_administered; test_ui_wiring.py::test_workspace_admin_surface_is_routed_and_wired; runtime smoke [14]; docs/evidence/api-surface-p0-2 |
| PL-002 | Plane | Projects | test_projects.py::test_project_crud_items_completion_and_events; test_projects.py::test_project_bad_payloads_and_missing_rows |
| PL-003 | Plane | Project members | `test_project_membership_p0.py::test_project_membership_registry_and_roles`, `::test_member_management_requires_project_admin_and_valid_identity`, runtime smoke section [12], `docs/evidence/project-me |
| PL-004 | Plane | Work Items / Issues | apps/api/tests/test_work_items.py::test_work_item_lifecycle_is_user_facing_and_workspace_isolated, ::test_assignee_set_changed_and_invalid_values_rejected, ::test_configurable_states_are_validated_gro |
| PL-005 | Plane | Work item descriptions | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-006 | Plane | Assignment / assignees | apps/api/tests/test_work_items.py::test_work_item_lifecycle_is_user_facing_and_workspace_isolated, ::test_assignee_set_changed_and_invalid_values_rejected, ::test_configurable_states_are_validated_gro |
| PL-007 | Plane | Priorities | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-008 | Plane | States | apps/api/tests/test_work_items.py::test_work_item_lifecycle_is_user_facing_and_workspace_isolated, ::test_assignee_set_changed_and_invalid_values_rejected, ::test_configurable_states_are_validated_gro |
| PL-009 | Plane | Labels | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-010 | Plane | Cycles | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-011 | Plane | Modules | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-012 | Plane | Sub-work items | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-013 | Plane | Relations | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-014 | Plane | Dependencies | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-015 | Plane | Parent-child links | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-016 | Plane | Estimates | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-017 | Plane | Due dates | apps/api/tests/test_work_items.py::test_work_item_lifecycle_is_user_facing_and_workspace_isolated, ::test_assignee_set_changed_and_invalid_values_rejected, ::test_configurable_states_are_validated_gro |
| PL-018 | Plane | Start dates | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-020 | Plane | Roadmaps | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-021 | Plane | List layout | docs/evidence/plane-support-ui-p1-20261123.md |
| PL-022 | Plane | Board layout / Kanban | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-023 | Plane | Calendar layout | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-024 | Plane | Timeline layout | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-025 | Plane | Table layout | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-026 | Plane | Filters | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-027 | Plane | Saved views | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-029 | Plane | Issue activity | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-030 | Plane | Comments | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-031 | Plane | Attachments / file assets | docs/evidence/work-collaboration-api-p2-20261123.md; apps/api/tests/test_plane_collaboration_api_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-032 | Plane | Mentions | docs/evidence/work-collaboration-api-p2-20261123.md; apps/api/tests/test_plane_collaboration_api_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-033 | Plane | Notifications | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| PL-035 | Plane | Work item updates | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-036 | Plane | Templates | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-037 | Plane | Recurring work items | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-038 | Plane | Search | apps/api/tests/test_work_items.py::test_work_item_lifecycle_is_user_facing_and_workspace_isolated, ::test_assignee_set_changed_and_invalid_values_rejected, ::test_configurable_states_are_validated_gro |
| PL-039 | Plane | Team collaboration | docs/evidence/work-collaboration-api-p2-20261123.md; apps/api/tests/test_plane_collaboration_api_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-040 | Plane | Permissions / RBAC | `test_project_membership_p0.py::test_project_roles_enforce_read_write_on_every_route`, `::test_public_projects_keep_workspace_role_fallback`, `tests/test_ui_wiring.py`, runtime smoke section [12], `do |
| PL-041 | Plane | Workspace admin | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| PL-042 | Plane | Project progress / delivery analytics | docs/evidence/plane-support-ui-p1-20261123.md |
| PL-043 | Plane | Public REST API | test_api_surface_p0.py::test_plane_adapter_records_crud_calls_only_when_configured; test_adapters.py capabilities; runtime smoke [14]; docs/evidence/api-surface-p0-20261123.md |
| PL-044 | Plane | API URL prefixes | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| PL-045 | Plane | API keys / personal access tokens | docs/evidence/plane-api-keys-p1-20261123.md |
| PL-048 | Plane | Cursor pagination | docs/evidence/work-collaboration-api-p2-20261123.md; apps/api/tests/test_plane_collaboration_api_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-049 | Plane | Rate limiting | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| PL-050 | Plane | fields and expand query parameters | docs/evidence/work-collaboration-api-p2-20261123.md; apps/api/tests/test_plane_collaboration_api_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-051 | Plane | OpenAPI schema, Swagger UI and ReDoc | docs/evidence/work-collaboration-api-p2-20261123.md; apps/api/tests/test_plane_collaboration_api_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-053 | Plane | Email/password authentication | test_workflow.py::unauthenticated_request_is_rejected; test_integration.py |
| PL-055 | Plane | Password reset, change and set | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| PL-056 | Plane | Email checks | docs/evidence/p2-unverified-gaps-20261123.md; named test: test_pl056_email_check_reports_availability_without_enumeration_abuse |
| PL-070 | Plane | API token permission scoping | docs/evidence/plane-api-keys-p1-20261123.md |
| PL-071 | Plane | Celery worker | docs/evidence/plane-worker-portability-p1-20261123.md |
| PL-077 | Plane | Notification task | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| PL-079 | Plane | Issue activities task | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-088 | Plane | Intake / intake issues | docs/evidence/plane-project-intake-p1-20261123.md |
| PL-094 | Plane | Pages | test_plane_projects_p1.py (15 named tests); test_ui_wiring.py::test_project_p1_work_management_controls_are_wired; docs/evidence/plane-projects-p1-20261123.md |
| PL-096 | Plane | Page version history | docs/evidence/wiki-pages-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PL-097 | Plane | Page analytics | docs/evidence/wiki-pages-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PL-098 | Plane | Page publish and export | docs/evidence/wiki-pages-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PL-099 | Plane | Page labels | docs/evidence/wiki-pages-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PL-100 | Plane | Nested pages | docs/evidence/wiki-pages-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PL-101 | Plane | Page collections | docs/evidence/wiki-pages-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PL-102 | Plane | Editor blocks | docs/evidence/wiki-pages-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PL-103 | Plane | Live co-editing and inline comments | docs/evidence/wiki-pages-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| PL-105 | Plane | Workspace invitations | test_plane_platform_p1.py and test_search_meilisearch_p1.py named tests; docs/evidence/plane-platform-p1-20261123.md; docs/evidence/meilisearch-search-p1-20261123.md |
| PL-130 | Plane | Work item security | docs/evidence/work-collaboration-api-p2-20261123.md; apps/api/tests/test_plane_collaboration_api_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-132 | Plane | Importers | docs/evidence/work-collaboration-api-p2-20261123.md; apps/api/tests/test_plane_collaboration_api_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-136 | Plane | Time tracking and worklogs | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-141 | Plane | Subscribers | docs/evidence/work-item-planning-p2-20261123.md; apps/api/tests/test_work_item_planning_p2.py; apps/api/tests/test_ui_wiring.py |
| PL-147 | Plane | Migration workflow | docs/evidence/plane-worker-portability-p1-20261123.md |
| PL-148 | Plane | PostgreSQL persistence | docs/evidence/plane-worker-portability-p1-20261123.md |
| MT-001 | Mautic | Open-source marketing automation platform | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-003 | Mautic | Extendable architecture and plugin system | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-007 | Mautic | LeadBundle - contacts | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-008 | Mautic | LeadBundle - segments | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_mt008_segments_are_static_or_dynamic_and_membership_is_real |
| MT-009 | Mautic | Contact types - visitors and known contacts | docs/evidence/marketing-content-p2-20261123.md; apps/api/tests/test_marketing_content_p2.py; apps/api/tests/test_ui_wiring.py |
| MT-011 | Mautic | Custom contact fields | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-012 | Mautic | EmailBundle - template emails | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_mt012_template_emails_are_stored_and_render_safely |
| MT-013 | Mautic | EmailBundle - segment broadcast emails | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_mt013_segment_broadcast_sends_once_per_consented_recipient |
| MT-014 | Mautic | Email HTML and text formats | docs/evidence/email-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MT-015 | Mautic | Email translations and A/B variants | docs/evidence/email-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MT-016 | Mautic | Email tokens and personalization | docs/evidence/mautic-marketing-p1-20261123.md |
| MT-017 | Mautic | Email open tracking pixel | docs/evidence/email-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MT-018 | Mautic | Email link and click tracking | docs/evidence/email-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MT-019 | Mautic | Email unsubscribe and preference centre tokens | `test_mautic_consent_identity_p0.py` four consent named tests, `test_ui_wiring.py`, runtime smoke section [11], `docs/evidence/mautic-consent-identity-p0-20261122.md` |
| MT-020 | Mautic | Email bounce management | docs/evidence/email-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MT-021 | Mautic | Email reply monitoring | docs/evidence/email-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MT-022 | Mautic | Mailer as owner and user signatures | docs/evidence/email-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MT-023 | Mautic | Base64 encoded images in emails | docs/evidence/email-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MT-024 | Mautic | Online version of email | docs/evidence/email-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MT-025 | Mautic | CampaignBundle - journeys and campaigns | test_marketing_journey_p0.py::test_campaign_can_be_authored_scheduled_and_activated_locally; ::test_journey_execution_records_local_events_and_respects_consent; test_marketing.py named tests; test_ui_ |
| MT-026 | Mautic | Campaign types and scheduling | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_mt026_campaign_types_and_scheduling_are_validated_and_due |
| MT-027 | Mautic | Campaign builder drag and drop | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_mt027_campaign_builder_canvas_wires_conditions_decisions_and_actions |
| MT-028 | Mautic | Campaign contact sources | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_mt028_campaign_contact_sources_enroll_once_from_segment_and_form |
| MT-029 | Mautic | PageBundle - landing pages | docs/evidence/marketing-content-p2-20261123.md; apps/api/tests/test_marketing_content_p2.py; apps/api/tests/test_ui_wiring.py |
| MT-030 | Mautic | FormBundle - campaign and standalone forms | docs/evidence/mautic-marketing-p1-20261123.md |
| MT-031 | Mautic | Progressive profiling via forms | docs/evidence/marketing-content-p2-20261123.md; apps/api/tests/test_marketing_content_p2.py; apps/api/tests/test_ui_wiring.py |
| MT-032 | Mautic | Form submit actions | docs/evidence/marketing-content-p2-20261123.md; apps/api/tests/test_marketing_content_p2.py; apps/api/tests/test_ui_wiring.py |
| MT-033 | Mautic | PointBundle - lead scoring | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-035 | Mautic | StageBundle - lifecycle stages | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-036 | Mautic | DynamicContentBundle | docs/evidence/marketing-content-p2-20261123.md; apps/api/tests/test_marketing_content_p2.py; apps/api/tests/test_ui_wiring.py |
| MT-037 | Mautic | AssetBundle | docs/evidence/marketing-content-p2-20261123.md; apps/api/tests/test_marketing_content_p2.py; apps/api/tests/test_ui_wiring.py |
| MT-042 | Mautic | SMS unsubscribes and DNC | docs/evidence/mautic-marketing-p1-20261123.md |
| MT-045 | Mautic | Marketing Messages multi-channel delivery | docs/evidence/mautic-marketing-p1-20261123.md |
| MT-046 | Mautic | Channel frequency rules and pause | docs/evidence/mautic-marketing-p1-20261123.md |
| MT-047 | Mautic | ReportBundle | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-048 | Mautic | DashboardBundle | docs/evidence/marketing-content-p2-20261123.md; apps/api/tests/test_marketing_content_p2.py; apps/api/tests/test_ui_wiring.py |
| MT-050 | Mautic | WebhookBundle | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-069 | Mautic | Cron console commands | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-070 | Mautic | Event-driven extension classes | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-072 | Mautic | REST API contexts and CRUD | test_api_surface_p0.py::test_api_contexts_expose_full_crud_with_validation_and_permissions; runtime smoke [14]; docs/evidence/api-surface-p0-20261123.md |
| MT-107 | Mautic | Legal review before derivative distribution | docs/evidence/mautic-marketing-p1-20261123.md |
| MT-112 | Mautic | Clean-room NOVARA marketing module recommendation | test_marketing_journey_p0.py::test_marketing_module_is_clean_room_and_satisfies_m1_to_m3; test_marketing.py named tests; FEATURE_MATRIX.md M1 to M3; docs/evidence/marketing-journey-p0-20261122.md |
| MT-113 | Mautic | Contact identity with external IDs | `test_mautic_consent_identity_p0.py::test_external_id_is_preserved_without_replacing_novara_identity`, `::test_external_identity_validation_and_workspace_scoping`; runtime smoke section [11]; `docs/ev |
| MT-114 | Mautic | Role scope translation to NOVARA RBAC | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-115 | Mautic | NOVARA-native lifecycle events | test_marketing_journey_p0.py::test_all_listed_lifecycle_events_are_registered_emitted_and_queryable; runtime smoke [13]; docs/evidence/marketing-journey-p0-20261122.md |
| MT-117 | Mautic | Funnel, engagement and attribution analytics | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| MT-122 | Mautic | Contact anonymization command | test_mautic_marketing_p1.py named tests; docs/evidence/mautic-marketing-p1-20261123.md |
| CW-001 | Chatwoot | Shared Inbox | apps/api/tests/test_support_inbox.py::test_shared_inbox_is_workspace_scoped_audited_and_local_only, ::test_conversation_persists_origin_type_and_four_named_events, ::test_public_reply_has_direction_ch |
| CW-002 | Chatwoot | Conversations | apps/api/tests/test_support_inbox.py::test_shared_inbox_is_workspace_scoped_audited_and_local_only, ::test_conversation_persists_origin_type_and_four_named_events, ::test_public_reply_has_direction_ch |
| CW-003 | Chatwoot | Messages / public replies | apps/api/tests/test_support_inbox.py::test_shared_inbox_is_workspace_scoped_audited_and_local_only, ::test_conversation_persists_origin_type_and_four_named_events, ::test_public_reply_has_direction_ch |
| CW-004 | Chatwoot | Conversation assignment | apps/api/tests/test_support_inbox.py::test_shared_inbox_is_workspace_scoped_audited_and_local_only, ::test_conversation_persists_origin_type_and_four_named_events, ::test_public_reply_has_direction_ch |
| CW-005 | Chatwoot | Teams | docs/evidence/chatwoot-support-p1-20261123.md; docs/evidence/support-p1-ui-20261123.md |
| CW-006 | Chatwoot | Agent availability / presence | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-008 | Chatwoot | Auto-assignment / round-robin | docs/evidence/chatwoot-support-p1-20261123.md; docs/evidence/support-p1-ui-20261123.md |
| CW-009 | Chatwoot | Conversation statuses | apps/api/tests/test_support_inbox.py::test_shared_inbox_is_workspace_scoped_audited_and_local_only, ::test_conversation_persists_origin_type_and_four_named_events, ::test_public_reply_has_direction_ch |
| CW-010 | Chatwoot | Snoozed conversations | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-011 | Chatwoot | Conversation priority | apps/api/tests/test_support_inbox.py::test_shared_inbox_is_workspace_scoped_audited_and_local_only, ::test_conversation_persists_origin_type_and_four_named_events, ::test_public_reply_has_direction_ch |
| CW-012 | Chatwoot | Labels | docs/evidence/chatwoot-support-p1-20261123.md; docs/evidence/support-p1-ui-20261123.md |
| CW-013 | Chatwoot | Custom attributes | docs/evidence/chatwoot-support-p1-20261123.md |
| CW-014 | Chatwoot | Contact profiles | `test_customer_profile_p0.py::test_ticket_belongs_to_exactly_one_existing_workspace_contact` and `::test_contact_profile_surfaces_only_its_linked_conversations`; `test_ui_wiring.py`; `docs/evidence/cu |
| CW-016 | Chatwoot | Contact notes | test_chatwoot_support_p1.py named tests; docs/evidence/chatwoot-support-p1-20261123.md |
| CW-017 | Chatwoot | Conversation history / customer timeline | test_chatwoot_support_p1.py named tests; docs/evidence/chatwoot-support-p1-20261123.md |
| CW-018 | Chatwoot | Customer identification / pre-chat identity | apps/api/tests/test_support_inbox.py::test_shared_inbox_is_workspace_scoped_audited_and_local_only, ::test_conversation_persists_origin_type_and_four_named_events, ::test_public_reply_has_direction_ch |
| CW-019 | Chatwoot | Private notes | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_cw019_private_notes_are_internal_only |
| CW-020 | Chatwoot | @Mentions in internal discussions | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-021 | Chatwoot | Collision detection | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-022 | Chatwoot | Read receipts | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-023 | Chatwoot | Canned responses / saved replies | docs/evidence/plane-support-ui-p1-20261123.md |
| CW-024 | Chatwoot | Macros | docs/evidence/chatwoot-support-p1-20261123.md; docs/evidence/support-p1-ui-20261123.md |
| CW-025 | Chatwoot | Bulk actions | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-028 | Chatwoot | Conversation filters | test_chatwoot_support_p1.py named tests; docs/evidence/chatwoot-support-p1-20261123.md |
| CW-029 | Chatwoot | Saved filter folders | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-030 | Chatwoot | Conversation search | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_cw030_conversation_search_matches_subject_body_and_messages |
| CW-032 | Chatwoot | Mute conversation | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-035 | Chatwoot | Website live chat widget | docs/evidence/chatwoot-visitor-conversation-p1-20261123.md |
| CW-048 | Chatwoot | Multi-inbox routing | docs/evidence/chatwoot-multi-inbox-p1-20261123.md |
| CW-051 | Chatwoot | Automation rules | test_chatwoot_support_p1.py named tests; docs/evidence/chatwoot-support-p1-20261123.md |
| CW-052 | Chatwoot | Business hours | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-053 | Chatwoot | Business hours date overrides | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-054 | Chatwoot | Business hours holidays | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-055 | Chatwoot | Business hours multiple slots | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-056 | Chatwoot | Away messages | docs/evidence/conversation-ops-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| CW-075 | Chatwoot | Contact segments / customer segmentation | docs/evidence/plane-support-ui-p1-20261123.md |
| CW-086 | Chatwoot | Help centre / portals | docs/evidence/chatwoot-support-p1-20261123.md; docs/evidence/support-p1-ui-20261123.md |
| CW-093 | Chatwoot | Dashboards / analytics overview | docs/evidence/chatwoot-support-p1-20261123.md; docs/evidence/support-p1-ui-20261123.md |
| CW-095 | Chatwoot | Conversation reports | docs/evidence/chatwoot-support-p1-20261123.md; docs/evidence/support-p1-ui-20261123.md |
| CW-096 | Chatwoot | Agent reports | docs/evidence/support-reporting-p2-20261123.md; apps/api/tests/test_support_reporting_p2.py; apps/api/tests/test_ui_wiring.py |
| CW-097 | Chatwoot | Team reports | docs/evidence/support-reporting-p2-20261123.md; apps/api/tests/test_support_reporting_p2.py; apps/api/tests/test_ui_wiring.py |
| CW-098 | Chatwoot | Inbox reports | docs/evidence/support-reporting-p2-20261123.md; apps/api/tests/test_support_reporting_p2.py; apps/api/tests/test_ui_wiring.py |
| CW-099 | Chatwoot | Label reports | docs/evidence/support-reporting-p2-20261123.md; apps/api/tests/test_support_reporting_p2.py; apps/api/tests/test_ui_wiring.py |
| CW-100 | Chatwoot | CSAT reports | docs/evidence/chatwoot-support-p1-20261123.md; docs/evidence/support-p1-ui-20261123.md |
| CW-101 | Chatwoot | Export reports | docs/evidence/support-reporting-p2-20261123.md; apps/api/tests/test_support_reporting_p2.py; apps/api/tests/test_ui_wiring.py |
| CW-102 | Chatwoot | CSAT surveys | docs/evidence/chatwoot-support-p1-20261123.md |
| CW-104 | Chatwoot | CSAT survey rules | docs/evidence/support-reporting-p2-20261123.md; apps/api/tests/test_support_reporting_p2.py; apps/api/tests/test_ui_wiring.py |
| CW-108 | Chatwoot | Webhooks | docs/evidence/chatwoot-webhook-p1-20261123.md |
| CW-114 | Chatwoot | Survey responses API | docs/evidence/support-reporting-p2-20261123.md; apps/api/tests/test_support_reporting_p2.py; apps/api/tests/test_ui_wiring.py |
| CW-117 | Chatwoot | OpenAPI 3.1 specification | docs/evidence/support-reporting-p2-20261123.md; apps/api/tests/test_support_reporting_p2.py; apps/api/tests/test_ui_wiring.py |
| CW-118 | Chatwoot | Scoped bearer tokens | test_chatwoot_support_p1.py named tests; docs/evidence/chatwoot-support-p1-20261123.md |
| CW-129 | Chatwoot | Accounts and account memberships | `test_customer_profile_p0.py` four membership named tests; runtime smoke section [9]; `docs/evidence/customer-profile-p0-20261122.md` |
| CW-158 | Chatwoot | Schema load and Rails migrations | test_chatwoot_support_p1.py named tests; docs/evidence/chatwoot-support-p1-20261123.md |
| CW-166 | Chatwoot | Authenticated and rate-limited inbound webhooks | test_chatwoot_support_p1.py named tests; docs/evidence/chatwoot-support-p1-20261123.md |
| NV-001 | Novu | Unified notification infrastructure (`one API` for Inbox, Email, SMS,  | `test_jobs.py::test_local_handler_creates_real_notification`, `test_workflow.py::test_intake_creates_one_identity_and_linked_records`; only local in-app slice |
| NV-002 | Novu | Event trigger API (`apps/api/src/app/events/trigger-event`) | `test_workflow.py::test_intake_creates_one_identity_and_linked_records`, `test_automation.py::test_dry_run_walks_records_and_records_runs`; neither is a generic Novu trigger |
| NV-003 | Novu | Bulk trigger API | docs/evidence/novu-notifications-p1-20261123.md |
| NV-004 | Novu | Topic trigger and fan-out | docs/evidence/novu-notifications-p1-20261123.md |
| NV-005 | Novu | Workflow builder / workflow management | `test_automation.py::test_automation_crud_status_and_events`, `::test_dry_run_walks_records_and_records_runs`; definition JSON is persisted and walked, but never delivers |
| NV-006 | Novu | Workflows v1 and v2 API controllers | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-007 | Novu | Notification channel steps (email, SMS, push, in-app, chat) | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_nv007_workflow_channel_steps_persist_results_without_delivery |
| NV-008 | Novu | Step conditions / conditional execution | docs/evidence/novu-notifications-p1-20261123.md |
| NV-009 | Novu | Code steps | docs/evidence/notification-automation-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-010 | Novu | Delay step (fixed, scheduled, dynamic) | docs/evidence/novu-notifications-p1-20261123.md |
| NV-011 | Novu | Scheduled delay / scheduled notification | docs/evidence/novu-notifications-p1-20261123.md |
| NV-012 | Novu | Digest step / event batching | docs/evidence/novu-notifications-p1-20261123.md |
| NV-013 | Novu | Scheduled digest | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-014 | Novu | Throttle step | docs/evidence/novu-notifications-p1-20261123.md |
| NV-015 | Novu | HTTP request step | docs/evidence/notification-automation-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-017 | Novu | Workflow templates / template catalogue | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-018 | Novu | Payload schema and validation | docs/evidence/novu-notifications-p1-20261123.md |
| NV-019 | Novu | Severity and critical workflows | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-023 | Novu | In-app notifications | tests/test_notifications_advanced.py::test_notification_persists_rich_content_per_workspace_and_user, ::test_feed_filters_and_pagination, ::test_bulk_seen_all_and_counts_by_category; docs/evidence/not |
| NV-025 | Novu | Provider integration catalog (`packages/providers/src/lib`) | docs/evidence/novu-notifications-p1-20261123.md |
| NV-026 | Novu | Integration conditions / provider routing | docs/evidence/notification-automation-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-027 | Novu | Demo integrations and sending limits | docs/evidence/notification-automation-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-028 | Novu | Trigger overrides | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-030 | Novu | Subscriber management (`subscribers-v1/v2`) | tests/test_notifications_advanced.py::test_one_identity_is_one_recipient_with_no_second_login, ::test_single_mark_read_is_user_and_workspace_scoped; docs/architecture/NOTIFICATION_RECIPIENT_MAPPING.md |
| NV-031 | Novu | Subscriber credentials / channel endpoints | docs/evidence/notification-automation-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-032 | Novu | Subscriber preferences (workflow, channel and global levels) | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_nv032_layered_preferences_resolve_global_workflow_and_channel |
| NV-033 | Novu | `<Inbox />` composable notification component | docs/evidence/novu-notifications-p1-20261123.md |
| NV-034 | Novu | Bell icon and real-time unread counts | docs/evidence/novu-notifications-p1-20261123.md |
| NV-035 | Novu | Notification feed, seen and read state | tests/test_notifications_advanced.py::test_seen_and_read_are_independent_states, ::test_single_mark_read_is_user_and_workspace_scoped, ::test_bulk_read_all_only_touches_callers_rows, ::test_bulk_seen_ |
| NV-036 | Novu | Inbox tabs and filters | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-038 | Novu | Subscriber delivery schedule / quiet hours | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-039 | Novu | Inbox preferences view | docs/evidence/p0-marketing-support-notify-gaps-20261123.md; named test: test_nv039_inbox_preferences_view_is_routed_and_wired |
| NV-040 | Novu | Inbox data object, conditional display and rich HTML | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-044 | Novu | Notification click behaviour and actions | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-045 | Novu | Topics | docs/evidence/novu-notifications-p1-20261123.md |
| NV-046 | Novu | Topic subscriptions with JSON Logic and context scope | docs/evidence/novu-notifications-p1-20261123.md |
| NV-048 | Novu | Activity Feed / workflow run debug timeline | docs/evidence/novu-notifications-p1-20261123.md |
| NV-051 | Novu | Delivery retry policy (provider, bridge, webhook layers) | docs/evidence/novu-notifications-p1-20261123.md |
| NV-052 | Novu | Failed message handling and `messages.failed` events | docs/evidence/novu-notifications-p1-20261123.md |
| NV-054 | Novu | Outbound webhooks | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-056 | Novu | Webhook signature verification, retries and replay | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-057 | Novu | REST API and generated OpenAPI document | test_api_surface_p0.py::test_notification_and_workflow_routes_are_documented_and_workspace_scoped; runtime smoke [14]; docs/evidence/api-surface-p0-20261123.md |
| NV-068 | Novu | Organizations and workspace configuration | tests/test_notifications_advanced.py::test_notification_settings_persist_and_deny_cross_workspace_access, ::test_notification_settings_reject_invalid_windows; migration b4d8c2f1a730; docs/evidence/not |
| NV-071 | Novu | API keys (`ApiKeyStrategy`, rotation) | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-073 | Novu | Contexts and multi-tenant notification scoping | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-081 | Novu | BullMQ queues, workers and health indicators | docs/evidence/novu-notifications-p1-20261123.md |
| NV-085 | Novu | Message records API (`messages`) | docs/evidence/novu-notifications-p1-20261123.md |
| NV-086 | Novu | Notification feeds API (`feeds`) | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-087 | Novu | Layouts / layout management (`layouts`) | docs/evidence/novu-workflows-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-099 | Novu | Personalize content (`{{variables}}` and LiquidJS filters) | docs/evidence/novu-notifications-p1-20261123.md |
| NV-103 | Novu | Platform limits and quotas | docs/evidence/notification-automation-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-104 | Novu | Broadcast event API | docs/evidence/notification-automation-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-106 | Novu | Notification event list and retrieve API | docs/evidence/novu-notifications-p1-20261123.md |
| NV-107 | Novu | Subscriber search and bulk create | docs/evidence/notification-automation-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| NV-118 | Novu | Community feature flags | docs/evidence/notification-automation-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| MK-001 | Marketing Skills | ab-testing | docs/evidence/marketing-skills-vendoring-p1-20261123.md |
| MK-005 | Marketing Skills | analytics | docs/evidence/marketing-skills-vendoring-p1-20261123.md |
| MK-015 | Marketing Skills | conversion-tracking | docs/evidence/marketing-skills-vendoring-p1-20261123.md |
| MK-017 | Marketing Skills | copywriting | docs/evidence/marketing-skills-vendoring-p1-20261123.md |
| MK-018 | Marketing Skills | cro | docs/evidence/marketing-skills-vendoring-p1-20261123.md |
| MK-039 | Marketing Skills | product-marketing | docs/evidence/marketing-skills-vendoring-p1-20261123.md |
| MK-048 | Marketing Skills | seo-audit | docs/evidence/marketing-skills-vendoring-p1-20261123.md |
| SB-008 | Sellbird | 29-signal catalog | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-009 | Sellbird | 26 free signals | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-010 | Sellbird | Paid signals require explicit confirmation | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-012 | Sellbird | Governed signal vocabulary and `signal_codes` | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-013 | Sellbird | Company records / `companies_list` | docs/evidence/p2-unverified-gaps-20261123.md; named test: test_sb013_company_records_create_list_update_archive_and_isolation |
| SB-014 | Sellbird | Prospect records / `prospects_list` | `test_listing.py::test_leads_support_search_filter_sort_and_pagination`, `test_workflow.py::test_lead_qualification_conversion_and_tasks` |
| SB-015 | Sellbird | Cohort builder | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-017 | Sellbird | Campaign and sequence drafting | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-018 | Sellbird | Personalised cold email writing | docs/evidence/sellbird-outreach-safety-p1-20261123.md |
| SB-019 | Sellbird | Offer suggestion | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-021 | Sellbird | Outbox review and `outbox_list` | docs/evidence/sellbird-outreach-safety-p1-20261123.md |
| SB-022 | Sellbird | Durable Outbox send queue and status ladder | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-023 | Sellbird | Autopilot opt-in | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-024 | Sellbird | Deterministic pre-send gate | docs/evidence/sellbird-outreach-safety-p1-20261123.md |
| SB-026 | Sellbird | Sending status and pause | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-028 | Sellbird | Send rules and header extension points | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-030 | Sellbird | Opt-out handling | docs/evidence/sellbird-outreach-safety-p1-20261123.md |
| SB-031 | Sellbird | Suppression / do-not-contact | docs/evidence/sellbird-outreach-safety-p1-20261123.md |
| SB-035 | Sellbird | Action logging / activity feed | `test_workflow.py::test_api_end_to_end`, `test_adversarial.py::test_events_are_append_only_idempotent_and_correlated` |
| SB-038 | Sellbird | Multi-agent pipeline | docs/evidence/sellbird-outreach-safety-p1-20261123.md |
| SB-042 | Sellbird | Sender agent role | docs/evidence/sellbird-outreach-safety-p1-20261123.md |
| SB-055 | Sellbird | Sending mode configuration | docs/evidence/sales-engagement-p2-20261123.md; apps/api/tests/test_ui_wiring.py |
| SB-061 | Sellbird | Loopback bind, Host and origin checks, security headers | `test_security.py` (4 tests), `test_adversarial.py::test_security_fix_regressions` |
| SB-079 | Sellbird | Compliance footer on outbound email | docs/evidence/sellbird-outreach-safety-p1-20261123.md |

## IMPLEMENTED_UNVERIFIED rows (0)

Code and tests exist locally; browser/E2E evidence was not captured for these rows. They are not counted as complete until verified.

| ID | Source | Feature | Evidence (from inventory) |
| --- | --- | --- | --- |

## Testing standard

1. Developer tests: named pytest cases with persistence, permission and validation assertions.
2. Independent QA: a separate reviewer re-runs the suite and checks the browser evidence files.
3. Adversarial/recovery: literal wildcards, workspace isolation, duplicate names, bad payloads, stale job recovery and guarded deletion are asserted in the named tests.
4. Honest boundaries: Docker, live PostgreSQL, outbound providers, non-Chromium browsers, physical devices and AI models are not verified and are not claimed.
5. Local only: all verification records live in the local SQLite workspace; no external message, commit, push, tag, release or deployment.
