# Evidence — Feedback Intelligence / Unify Feedback P2 cluster (T-087)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Eleven named tests were added for this cluster: ten acceptance tests in
`apps/api/tests/test_feedback_intelligence_p2.py` and one static UI wiring guard
in `apps/api/tests/test_ui_wiring.py` (33 targeted tests pass together with the
pre-existing guards). No app code is mocked and no external feedback service,
analytics backend or model is contacted.

The implementation is a clean-room module,
`apps/api/novara_core/modules/feedback_intelligence.py`, registered in
`modules/__init__.py`. It owns seven additive workspace-scoped tables created by
Alembic revision `d5e6f7a8b1c2` (down revision `c4d5e6f7a8b1`). No Formbricks
server source is copied.

## Delivery boundary (important)

NOVARA does not contact Formbricks, Cube.js, an external feedback provider or a
hosted analytics service. "Insights", "dashboards" and "unify" are computed from
persisted workspace-scoped records. Sentiment is a deterministic, local keyword
classifier — no external model is called. Audience segments evaluate real
workspace contact attributes. No claim of a real external delivery or hosted
feature is made.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| FB-024 | `test_fb024_field_library_reused_across_surveys_changes_in_one_place` | A library field created once is bound into two real surveys; editing its label updates both effective field lists (change in one place); duplicate keys return 409, unknown field types 422, double binding 409, unbinding removes only one survey's field. |
| FB-025 | `test_fb025_reserved_fields_captured_on_every_record_and_not_spoofable` | The five system fields (page, campaign, device, timing, request_context) are listed and all appear on every ingested record; a caller-supplied `timing` value is overwritten by the server; `captured_at` is server-set. |
| FB-029 | `test_fb029_respondent_metadata_captured_and_grouped_per_dataset` | Respondent id/locale/device are captured at ingestion; metadata is grouped by a workspace-scoped SHA-256 respondent hash with record counts; two datasets isolate the same respondent context. |
| FB-085 | `test_fb085_segments_filter_real_contact_attributes` | A rule over contact `custom_fields` (plan=pro, score>=7) matches exactly one of three real contacts; invalid operators return 422 and duplicate keys 409; evaluation publishes an audit event. |
| FB-096 | `test_fb096_dashboard_widgets_compute_live_from_stored_records` | Four widget types (sentiment, count_by_source, volume, field distribution) are computed from persisted records; a new record changes the computed result, proving live analytics rather than stored static values. |
| FB-097 | `test_fb097_unified_insights_aggregate_all_sources` | Unified insights aggregate records across two datasets/sources with sentiment/source-type/dataset breakdowns, reserved-field coverage and generation time; ingestion audit event carries `reserved_capture_claimed: false`. |
| FB-098 | `test_fb098_datasets_and_fb099_sources_are_workspace_scoped` | Datasets are created and listed with duplicate-key rejection. |
| FB-099 | `test_fb098_datasets_and_fb099_sources_are_workspace_scoped` | Sources are created under a dataset, listed, duplicate-key and invalid-type rejected; attaching a source from a different dataset to a record returns 422. |
| FB-100 | `test_fb100_records_ingest_filter_and_sentiment_override` | Records ingest with local sentiment classification, filter by sentiment/external id, are fetched individually, and accept an audited manual sentiment override; invalid sentiment returns 422. |
| FB-101 | `test_fb101_unify_feedback_api_group_is_documented` | One stable API group contract (version 1, empty legacy list, local-only delivery) documents all seven resources. |
| Cross-workspace | `test_feedback_intelligence_workspace_isolation` | A second workspace sees no datasets, fields, segments, dashboards or insights and cannot read/mutate the first workspace's records, fields, segments or dashboards. |
| UI | `test_feedback_intelligence_route_controls_are_rendered_and_dispatched` | The `feedback-intelligence` Operations route renders live API data and every rendered control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_feedback_intelligence_p2.py` → **10 passed**.
- `pytest apps/api/tests/test_feedback_intelligence_p2.py apps/api/tests/test_ui_wiring.py` → **33 passed, 1 warning**.
- `pytest apps/api/tests -q --disable-warnings` → **full-suite result recorded in `docs/TEST_RESULTS.md`**.
- `node --check apps/web/app.js` → exit 0.
- `alembic heads` → single head `d5e6f7a8b1c2`.
- `scripts/migration_roundtrip_check.py c4d5e6f7a8b1` → **ROUND TRIP PASS: upgrade -> downgrade -> upgrade, existing data preserved**.

## Not claimed

No Formbricks-hosted feature, Cube.js analytics service, external feedback
provider, third-party SDK, model-based sentiment service, MCP server or
multi-region infrastructure is claimed. Rows outside this cluster remain in
their existing matrix states.
