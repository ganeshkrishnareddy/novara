# Evidence — Targeting, triggers, controls and templates (2026-11-23)

## Scope

Closed 26 Formbricks P2 rows with a new clean-room module
`apps/api/novara_core/modules/feedback_targeting.py` and twelve original
template presets added to `feedback_extensions.py`. Five additive
workspace-scoped tables were introduced (`survey_user_profiles`,
`survey_action_classes`, `survey_triggers`, `targeting_decisions`,
`survey_controls`) and registered in Alembic revision `a2b3c4d5e6f8`. All
decisions are computed from local state and audited. No survey is injected into
a host page, no email is sent and no external SDK or Formbricks service is
contacted. No Formbricks source was copied.

## Rows closed and named test

| ID | Capability | Test |
| --- | --- | --- |
| FB-055 | In-app targeting without host code changes | `test_fb055_inapp_targeting_without_code_changes` |
| FB-056 | User identification and attribute merge | `test_fb056_user_identification_and_attribute_merge` |
| FB-057 | Attribute-based targeting / show conditions | `test_fb057_fb060_attribute_based_show_conditions` |
| FB-058 | ActionClass model and actions | `test_fb058_action_class_creation_and_dedup` |
| FB-059 | SurveyTrigger model and lifecycle | `test_fb059_trigger_creation_and_lifecycle` |
| FB-060 | Show conditions (eq/neq/contains/gt/gte/lt/lte/in) | `test_fb057_fb060_attribute_based_show_conditions` |
| FB-061 | Display logic / required attributes | `test_fb061_display_logic_requires_attributes` |
| FB-062 | Recontact options (always/once/limited) | `test_fb062_recontact_options` |
| FB-063 | Cooldown period | `test_fb063_cooldown_period` |
| FB-064 | Deterministic percentage rollout | `test_fb064_percentage_rollout_is_stable` |
| FB-081 | Limit submissions | `test_fb081_limit_submissions` |
| FB-082 | Schedule a survey | `test_fb082_schedule_a_survey` |
| FB-083 | Segments / audience attributes | `test_fb083_segment_targeting` |
| FB-084 | Quota management | `test_fb084_quota_management` |
| FB-192 | Contact Form template | `test_all_documented_template_presets_create_real_surveys` |
| FB-194 | Docs Feedback template | same |
| FB-195 | Feature Chaser template | same |
| FB-196 | Feedback Box template | same |
| FB-197 | Improve Email Content template | same |
| FB-198 | App Interview Prompt template | same |
| FB-199 | Churn Survey template | same |
| FB-200 | Product-Market Fit Survey template | same |
| FB-201 | Quiz Time template | same |
| FB-202 | Improve Trial Conversion template | same |
| FB-203 | Panel Management template | same |
| FB-204 | Collect Google Reviews template | same |

Targeting tests are in `apps/api/tests/test_feedback_targeting_p2c.py`;
template tests in `apps/api/tests/test_feedback_templates_p2c.py`. Templates
are not claimed by name: each creates a real survey with persisted typed
questions, and `test_template_questions_are_answerable_and_isolated` submits a
real answer for every question of a template survey.

## Security and isolation

`test_p2c_workspace_isolation` proves another workspace cannot read a user
profile, cannot list action classes, cannot evaluate a trigger by id and cannot
evaluate a control for a survey it does not own. `test_p2c` template isolation
does the same for template-created questions. Every mutation requires
`verify_workspace` plus `require(CONTACT_READ)` / `require(NOTE_WRITE)` and
publishes an audited event with the acting principal; automated cooldown
decisions use the recorded `"system"` actor.

## UI

`apps/web/app.js` gained a Targeting and controls panel on the survey detail
view: action-class creation, trigger list and creation, a local trigger
evaluation modal, submission-control form, and a template dropdown containing
all twelve new presets. `apps/api/tests/test_ui_wiring.py` statically guards
each control and dispatcher.

## Verification actually run (from `D:\\NOVARA`)

- Targeted targeting + templates suites: **17 passed**.
- UI wiring + targeted: **36 passed** (20 UI guards after adding the new guard).
- Full API suite: **504 passed, 2 warnings in 254.63s** (baseline 486).
- `node --check apps/web/app.js`: exit 0.
- Migration: single Alembic head `a2b3c4d5e6f8`; round trip from
  `f1a2b3c4d5e6` upgrade → downgrade → upgrade PASS with existing data preserved.

## Honest limits

Percentage rollout uses a stable SHA-256 bucket of trigger id and user id, not a
live experimentation service. This is a local evaluation endpoint: there is no
injected client script, no host-page CSS interaction, no real-time event stream
from a browser SDK and no external delivery. Schedule evaluation compares the
current UTC time to stored ISO timestamps; no background scheduler is running.
Templates are original NOVARA question sets modelled on the documented
purpose of each source template, not copies of upstream template content.
