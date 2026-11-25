# T-056 evidence — P0 Feedback Studio (FB-001) (2026-11-22)

## Scope and finding

The matrix listed FB-001 as partially implemented with no frontend, but
inspection found a working Feedback Studio list/detail UI already present in
`apps/web/app.js`. The real gap was the survey lifecycle: surveys could be
created with a `draft` status but no route could publish, close or reopen them,
and responses had no closed-state or identity validation. The matrix was
corrected only after those criteria passed.

| ID | Source feature | Acceptance evidence |
| --- | --- | --- |
| FB-001 | Free and open source surveying platform (clean-room boundary) | `test_feedback_lifecycle_p0.py::test_survey_lifecycle_controls_responses_and_is_audited`, `::test_survey_updates_validate_metadata_and_identities` |

## What was built

- `modules/feedback.py`: `PATCH /surveys/{id}` with validated draft/active/closed
  transitions, name uniqueness and description edits; `survey.updated` and
  `survey.status_changed` audit events; closed surveys reject new responses
  with 409; response contact ids must exist in the same workspace.
- `apps/web/app.js`: survey detail now offers Publish, Close and Reopen
  according to status and hides the response form when closed.
- `scripts/runtime_smoke.py`: section [10] verifies the lifecycle over HTTP.

No database migration was needed: `Survey.status` already exists.

## Commands and results

From `D:\NOVARA\apps\api` (Python at `D:\NOVARA\.venv\Scripts\python.exe`):

```
python -m pytest tests/test_feedback_lifecycle_p0.py tests/test_phase4_ui_contract.py -q -rs
  7 passed, 1 warning in 2.29s

python -m pytest tests/test_ui_wiring.py tests/test_feedback_lifecycle_p0.py -q -rs
  11 passed, 1 warning in 0.87s

python -m pytest -q -rs
  222 passed, 1 warning in 73.52s
```

From `D:\NOVARA`:

```
node --check apps\web\app.js -> no syntax errors
python scripts\runtime_smoke.py -> RUNTIME SMOKE: PASS (sections 1-10)
```

The only warning is the known Starlette/httpx TestClient deprecation notice.
No response bodies, tokens or credentials were printed.

## Matrix accounting

Only FB-001 was changed; all seven FEATURE_PARITY deliverables regenerated:

- 1,488 permanent IDs, zero omissions
- VERIFIED_COMPLETE 66 (was 65)
- complete-like 151 / 1,488 = 10.15% (was 150 / 10.08%)
- PARTIALLY_IMPLEMENTED 146 (was 147)
- P0: 111 rows — 59 verified, 11 partial, 32 replacement, 9 restricted

## Not claimed

- No survey distribution, email invitations or external hosting: responses are
  local records only.
- No Formbricks code, instance or second login.
- No commit, push, tag, deployment or public publishing. Git HEAD remains
  `73e9f76`.

## Next

T-057: select the next group from the 11 remaining P0 partial rows (Plane 4,
Mautic 6, Novu 1).
