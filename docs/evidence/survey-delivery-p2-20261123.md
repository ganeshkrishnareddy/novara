# Evidence — clean-room survey delivery P2 cluster (T-093)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Nineteen named acceptance tests were added in
`apps/api/tests/test_survey_delivery_p2.py` and one static UI wiring guard in
`apps/api/tests/test_ui_wiring.py`. Every test drives the real FastAPI app
against real persisted, workspace-scoped rows. No app code is mocked.

The clean-room module `apps/api/novara_core/modules/survey_delivery.py` owns
seven additive workspace-scoped tables created by Alembic revision
`d3e4f5a7b8c9` (down revision `c2d3e4f5a7b8`). It extends NOVARA's existing
survey records with delivery configuration, a no-code multi-page flow, email
branding/follow-ups, PIN and head-script controls, accessibility settings and
local creatives with show conditions.

## Delivery boundary (important)

All Formbricks rows here are AGPL-3.0 community-core features and were
implemented clean-room: no Formbricks server source was copied. No hosted
widget, survey email, tracking pixel, CDN, external SDK or form provider is
contacted. PINs are stored only as SHA-256 hashes; creatives are evaluated
locally with an explicit `local_evaluation: true` result. This verifies
NOVARA's own local adapter, not source-equivalence with Formbricks.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| FB-002 | `test_fb002_in_app_survey_delivery_is_a_persisted_channel` | In-app is a validated, persisted delivery channel. |
| FB-003 | `test_fb003_website_survey_targets_are_recorded` | Website delivery is recorded for anonymous visitors. |
| FB-004 | `test_fb004_link_survey_is_shareable_by_survey_identifier` | Link surveys expose a local share URL rooted at the survey ID. |
| FB-005 | `test_fb005_email_survey_channel_is_recorded` | Email is an explicit channel; unknown channels are rejected with 422. |
| FB-006 | `test_fb006_embedded_surveys_generate_local_iframe_and_email_snippets` | Embed mode generates local iframe and email snippets; unsupported modes are rejected. |
| FB-010 | `test_fb010_no_code_survey_editor_creates_question_pages` | Editable question pages persist with duplicate-key protection. |
| FB-015 | `test_fb015_multi_page_flow_has_rules_fallbacks_and_endings` | Flow outline exposes ordered pages, post-block rules, fallbacks and endings; invalid rule kinds are rejected. |
| FB-036 | `test_fb036_email_branding_is_workspace_scoped` | Respondent email branding is stored per config; no send is performed. |
| FB-038 | `test_fb038_hide_back_button_is_a_configurable_flag` | The back-button flag is persisted and togglable. |
| FB-074 | `test_fb074_pin_protected_surveys_verify_without_exposing_the_pin` | Four-digit PINs are hashed at rest, validated, verified without disclosure and removable; a bad PIN is rejected. |
| FB-075 | `test_fb075_custom_head_scripts_are_scoped_to_one_config` | Head scripts are stored, toggleable, deduplicated and included in the local embed head. |
| FB-079 | `test_fb079_host_page_css_interaction_is_isolated_by_style_scope` | Host CSS mode is validated and the style scope appears in generated markup. |
| FB-080 | `test_fb080_email_followups_are_triggered_by_answers_or_endings` | Follow-ups are local records keyed to answer or ending triggers; invalid triggers are rejected. |
| FB-183 | `test_fb183_accessibility_settings_are_persisted_and_validated` | Structured accessibility settings persist on the config. |
| FB-184 | `test_fb184_creatives_package_registers_local_creatives` | The creatives package registers workspace-scoped creatives with duplicate/type validation. |
| FB-185 | `test_fb185_feedback_button_creative_has_label_icon_colour_and_position` | The edge feedback button stores label/icon/colours/size/position and evaluates locally. |
| FB-186 | `test_fb186_banner_creative_stores_message_button_and_schedule` | The banner stores message/button/position and a minute schedule, and evaluates inside it. |
| FB-187 | `test_fb187_creative_show_conditions_gate_page_device_views_and_share` | Show conditions gate page, device, views, share and schedule with explicit reason codes. |
| Isolation | `test_survey_delivery_workspace_isolation` | A second workspace cannot read another workspace's configs/creatives or address their config, script or creative IDs. |
| UI | `test_survey_delivery_route_controls_are_rendered_and_dispatched` | The `survey-delivery` Operations route renders configs and creatives; every control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_survey_delivery_p2.py` -> **19 passed, 1 warning**.
- `pytest apps/api/tests/test_survey_delivery_p2.py apps/api/tests/test_ui_wiring.py`
  -> **48 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `d3e4f5a7b8c9`.
- `scripts/migration_roundtrip_check.py c2d3e4f5a7b8` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md`.

## Not claimed

No Formbricks-hosted feature, survey email delivery, tracking pixel, hosted
widget, external SDK, MCP server, agent tooling or AI adapter is claimed. Rows
outside this cluster remain in their existing matrix states.
