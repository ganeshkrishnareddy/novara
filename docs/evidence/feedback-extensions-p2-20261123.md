# Evidence — Formbricks P2 survey extensions (2026-11-23)

## Scope

Closed 26 Formbricks P2 rows with a new clean-room module
`apps/api/novara_core/modules/feedback_extensions.py`, layered on the existing
Feedback Studio without modifying its green lifecycle tests. The module owns
its tables (`survey_configs`, `survey_questions`, `survey_answers`,
`survey_embedded_data`) and one APIRouter registered through
`modules/__init__.py`. No Formbricks source was copied and no external service
is contacted: every result is local persistence plus an audited event.

## Rows closed and their named test

| ID | Capability | Test (`apps/api/tests/test_feedback_extensions_p2.py`) |
| --- | --- | --- |
| FB-008 | displayOptions enum (4 values, validated) | `test_fb008_display_options_validated` |
| FB-009 | Survey visibility modes + allowed roles | `test_fb009_visibility_modes` |
| FB-011 | Best-practice preset template | `test_fb011_012_013_templates_and_presets` |
| FB-012 | NPS preset | `test_fb011_012_013_templates_and_presets` |
| FB-013 | CSAT preset | `test_fb011_012_013_templates_and_presets` |
| FB-014 | CES question type | `test_fb014_ces_and_question_types` |
| FB-016 | Logic jumps | `test_fb016_017_018_logic_and_branching` |
| FB-017 | Show If condition | `test_fb016_017_018_logic_and_branching` |
| FB-018 | Branching and endings (`jump_to: __end__`) | `test_fb016_017_018_logic_and_branching` |
| FB-019 | Set Value / expressions | `test_fb019_set_value_and_fb028_variables` |
| FB-021 | Question codes, unique per survey | `test_fb021_question_codes_unique` |
| FB-022 | Hidden fields | `test_fb022_023_hidden_fields_and_embedded_data` |
| FB-023 | Embedded data on answers | `test_fb022_023_hidden_fields_and_embedded_data` |
| FB-026 | set/clear embedded data + recall | `test_fb026_027_028_recall_and_variables` |
| FB-027 | Recall data | `test_fb026_027_028_recall_and_variables` |
| FB-028 | Variables | `test_fb026_027_028_recall_and_variables` |
| FB-030 | Partial submissions | `test_fb030_partial_submissions` |
| FB-032 | Multi-language survey labels | `test_fb032_033_034_035_language_and_styling` |
| FB-033 | Custom styling | `test_fb032_033_034_035_language_and_styling` |
| FB-034 | Custom CSS | `test_fb032_033_034_035_language_and_styling` |
| FB-035 | Styling theme | `test_fb032_033_034_035_language_and_styling` |
| FB-037 | Image / video question content types | `test_fb014_ces_and_question_types` |
| FB-040 | Consent question | `test_fb040_041_042_044_contact_and_closure` |
| FB-041 | Contact Info question | `test_fb040_041_042_044_contact_and_closure` |
| FB-042 | Date question | `test_fb040_041_042_044_contact_and_closure` |
| FB-044 | Free Text question | `test_fb014_ces_and_question_types`, `test_fb040_041_042_044_contact_and_closure` |

## Security and isolation

`test_feedback_extensions_workspace_isolation` proves a survey in workspace A is
not readable through workspace B's config path and a question cannot be patched
across workspaces. Every mutation is gated by `verify_workspace` and a
`require(CONTACT_READ)` / `require(NOTE_WRITE)` dependency, and every mutation
publishes an event carrying the acting principal. Invalid enums, duplicate
codes and unsupported logic fields are rejected before any row is written; a
closed survey rejects new answers.

## Verification actually run (from `D:\NOVARA`)

- Targeted suite: `python -m pytest apps/api/tests/test_feedback_extensions_p2.py -q` → **13 passed**.
- Full regression: `python -m pytest apps/api/tests -q --disable-warnings` → **472 passed, 2 warnings in 237.24s** (upstream Starlette/httpx + Alembic config deprecations only). Baseline before this cluster was 459.
- No frontend change in this cluster; the last `node --check apps/web/app.js` (exit 0) and runtime smoke (sections [1]-[15], 432 paths) remain current.

## Honest limits

These are clean-room NOVARA implementations of the recorded acceptance criteria,
not copies of Formbricks. Presentation/webhook delivery, real respondent
recruitment and any Formbricks-hosted service remain out of scope. Frontend
controls for the new configuration fields are not added in this cluster; the
rows are claimed on real backend behaviour, persistence, permissions and tests,
with the frontend status recorded honestly in the matrix.
