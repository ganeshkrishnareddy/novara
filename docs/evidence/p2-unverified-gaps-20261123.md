# Evidence — P2 IMPLEMENTED_UNVERIFIED gaps (2026-11-23)

## Scope

Seven P2 rows were promoted to VERIFIED_COMPLETE by a single named acceptance
suite: `apps/api/tests/test_p2_unverified_gaps.py` (7 tests, all passing).
Backend tests drive the real FastAPI app; the Formbricks rows also assert the
real SPA source for the required UI route, and FB-179 runs the real local
backup/restore CLI against a throwaway SQLite file.

Two real gaps were closed while writing these tests:

1. **PL-056** had no email-check endpoint. `POST /api/v1/auth/email/check` now
   normalises and validates the address, reports availability without creating
   a user or session, and enforces a local 8-per-60-second per-client limit so
   the availability bit cannot be used as a bulk enumeration oracle. The sign-up
   form calls it before registering.
2. **SB-013** had create/list only. Company records now support partial update
   and reversible archive/restore, backed by an additive `archived` column
   (`b9d4f7a2c615`), three audit event types, and full workspace isolation.

A third, previously latent problem was found by the migration round-trip check:
the marketing model extensions (`segment_members`, five `campaigns` columns,
two `journey_steps` columns) existed only via runtime `create_all`, so a fresh
Alembic database diverged from `Base.metadata`. Additive revision
`d3f6b9c2e5a8` closes that gap. `alembic check` now reports **No new upgrade
operations detected** and the round-trip passes on a strict migration-only DB.

## Row-to-test mapping

| Row | Named test | What is proven |
| --- | --- | --- |
| FB-087 | `test_fb087_survey_score_validation_rejects_out_of_range_and_extra_fields` | scores outside 1–10 and extra fields return 422; boundary 10 is accepted; the response form is wired in the SPA |
| FB-088 | `test_fb088_survey_detail_reports_real_response_count_and_average` | empty detail has count 0/null average; three real responses yield count 3 and average 7.0; survey UI route is wired |
| FB-089 | `test_fb089_survey_events_form_an_append_only_audit_trail` | created/status-changed/response-created events are published, stable across reads, and no event mutation route exists in OpenAPI |
| FB-090 | `test_fb090_survey_routes_are_workspace_isolated` | cross-workspace list is empty and detail/response/patch return 403/404; a foreign session cannot use this workspace; survey detail route is wired |
| FB-179 | `test_fb179_backup_verify_and_restore_round_trip_is_verified` | real SQLite backup reports integrity ok, verify counts rows, restore rebuilds data and the alembic version after simulated loss; no PostgreSQL/Docker claim |
| PL-056 | `test_pl056_email_check_reports_availability_without_enumeration_abuse` | invalid format 422; registered address unavailable, fresh address available; check is read-only; ninth check returns 429; sign-up form uses the endpoint |
| SB-013 | `test_sb013_company_records_create_list_update_archive_and_isolation` | foreign owner rejected 422, duplicate 409, update/duplicate-name guard, archive/restore visibility, cross-workspace 404/403 |

## Verification

- Targeted: 7 passed.
- Full API suite after integration: 455 passed, 2 warnings (upstream
  Starlette/httpx deprecation only).
- Single Alembic head (`d3f6b9c2e5a8`); `alembic check` clean;
  `scripts/migration_roundtrip_check.py f5a7b9c1d2e4` passes with the
  pre-existing workspace row preserved.

## Honest limits

Backup/restore is verified for the local SQLite path only. The email check is a
local availability bit with a bounded per-client rate limit; it does not send
mail and is not a CAPTCHA. Company archive is reversible and never a hard delete.
No provider delivery, hosted database or browser E2E runner is claimed.
