# Evidence — Formbricks P2 survey cluster B (2026-11-23)

## Scope

Closed 24 Formbricks P2 rows by extending the clean-room
`apps/api/novara_core/modules/feedback_extensions.py` module with extended
question types, shareable links, display tracking, response tagging and response
management. Four additive workspace-scoped tables were added: `survey_links`,
`survey_displays`, `survey_tags`, `survey_answer_tags`. All eight survey
extension tables are now in the Alembic chain via revision `f1a2b3c4d5e6`.
No Formbricks source was copied; no survey is distributed and no external
service is contacted.

## Rows closed and named test

All tests are in `apps/api/tests/test_feedback_extensions_p2b.py`.

| ID | Capability | Test |
| --- | --- | --- |
| FB-039 | Address question | `test_extended_question_types` |
| FB-043 | File Upload question | `test_extended_question_types` |
| FB-045 | Matrix question | `test_extended_question_types` |
| FB-046 | Ranking question | `test_extended_question_types` |
| FB-047 | Rating question | `test_extended_question_types` |
| FB-048 | Schedule A Meeting question | `test_extended_question_types` |
| FB-049 | Multi Select question | `test_extended_question_types` |
| FB-050 | Picture Selection question | `test_extended_question_types` |
| FB-051 | Single Select question | `test_extended_question_types` |
| FB-052 | Signature question | `test_extended_question_types` |
| FB-053 | Statement / CTA question | `test_extended_question_types` |
| FB-054 | Thank You Card question | `test_extended_question_types` |
| FB-066 | Personal links | `test_fb066_personal_link_bound_to_contact` |
| FB-067 | Single-use links consumed once | `test_fb067_single_use_link_consumed_once` |
| FB-068 | Pretty URL slug | `test_fb068_068b_069_pretty_url_and_link_settings` |
| FB-069 | Link settings (title, description, preview image) | `test_fb068_068b_069_pretty_url_and_link_settings` |
| FB-070 | Data prefilling | `test_fb070_071_prefill_and_source_tracking` |
| FB-071 | Source tracking | `test_fb070_071_prefill_and_source_tracking` |
| FB-072 | Start at a specific block | `test_fb072_start_at_specific_block` |
| FB-073 | Verify identity before survey | `test_fb073_require_identified_respondent` |
| FB-091 | Display model / display tracking | `test_fb091_display_tracking` |
| FB-092 | Tags model and response tagging | `test_fb092_tags_and_response_tagging` |
| FB-094 | Export responses as CSV | `test_fb094_export_responses_csv` |
| FB-095 | Response update, delete and mark finished | `test_fb095_response_update_delete_and_mark_finished` |

## UI

`apps/web/app.js` gained a share-link table and creation form, a tag list and
creation form, and a structured-answers table with finish/delete actions and a
CSV export viewer. `apps/api/tests/test_ui_wiring.py` statically guards each
control and its dispatcher so it cannot silently become a dead button.

## Security and isolation

`test_p2b_workspace_isolation` proves another workspace cannot resolve a link by
token, cannot record a display against it and cannot patch an answer belonging
to the first workspace. Single-use links return 409 on reuse; identity-gated
links reject anonymous submissions; duplicate slugs/tags/tag assignments are
rejected. Every mutation publishes an audited event with the acting principal.
No link performs an external send or hosts content.

## Verification actually run (from `D:\NOVARA`)

- Targeted acceptance suite: **12 passed**.
- UI wiring + both feedback clusters: **43 passed**.
- Full API suite after all changes: **486 passed, 2 warnings in 249.55s**
  (baseline before this cluster: 473).
- `node --check apps/web/app.js`: exit 0.
- Migration: single Alembic head `f1a2b3c4d5e6`; round trip from
  `e7d2c4b8a1f6` upgrade → downgrade → upgrade PASS with data preserved.

## Honest limits

These are clean-room NOVARA implementations of the recorded acceptance
criteria, not Formbricks code. "Verify email before survey" is implemented as a
required identified respondent (a contact in the workspace), not a
cryptographic email-ownership check with external delivery. CSV export returns
content through the local API rather than a browser file download. Display
tracking records impressions at the API layer, not through an injected client
script. Structured answers and the older score-based responses remain two
distinct local records; both are shown in the survey detail view. No real
survey distribution, invitation email or third-party analytics is claimed.
