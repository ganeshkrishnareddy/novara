# T-059 evidence — P0 Mautic marketing journey and lifecycle (2026-11-22)

## Scope

| ID | Source feature | Acceptance evidence |
| --- | --- | --- |
| MT-025 | CampaignBundle — journeys and campaigns | `test_marketing_journey_p0.py::test_campaign_can_be_authored_scheduled_and_activated_locally`, `::test_journey_execution_records_local_events_and_respects_consent` |
| MT-112 | Clean-room NOVARA marketing module recommendation | `test_marketing_journey_p0.py::test_marketing_module_is_clean_room_and_satisfies_m1_to_m3`, plus the four named `test_marketing.py` M1–M3 tests |
| MT-115 | NOVARA-native lifecycle events | `test_marketing_journey_p0.py::test_all_listed_lifecycle_events_are_registered_emitted_and_queryable` |

Clean-room implementation. No Mautic instance, bundle, schema or proprietary code
was copied. No email, message, tracking pixel, landing page or webhook is
delivered: every step writes a local analytics record on the shared event spine.

## What was built

- `modules/marketing.py`: a scheduled campaign now has ordered local journey
  steps (`journey_steps`) and consent-gated contact progress
  (`campaign_enrollments`). `POST /schedule` sets a validated window,
  `POST /due` activates drafts whose window has opened, `POST /run` advances each
  active enrollment one step and records `email.sent` / `journey.step_completed`
  events with per-enrollment idempotency keys, and `POST /engagement` records
  locally observed opens and clicks. Suppressed or do-not-contact contacts are
  refused at enrollment; the `email.sent` step re-checks consent before
  recording.
- MT-115: all ten lifecycle kinds from `03-plane-mautic.md` section 2.15 —
  `contact.segmented`, `campaign.entered`, `campaign.exited`, `email.sent`,
  `email.opened`, `email.clicked`, `form.submitted`, `page.visited`,
  `webhook.received`, `journey.step_completed` — are registered through
  `register_event_types`, emitted by real actions and queryable via
  `GET /campaigns/analytics/lifecycle` (optionally filtered by `kind`).
- `apps/web/app.js`: the Campaign Studio detail now loads journey steps,
  enrollments, contacts and lifecycle events alongside metrics and offers working
  controls to add a step, save a schedule, run one step, enroll a contact, record
  engagement and exit a journey. Datetime-local values are converted to UTC
  before posting. The UI states explicitly that steps record local analytics
  only and that nothing shown represents a delivered message.
- Migration `e4b1c7a9d052` adds `journey_steps` and `campaign_enrollments`
  idempotently and reverses cleanly.

## Commands and results

From `D:\NOVARA\apps\api` (Python at `D:\NOVARA\.venv\Scripts\python.exe`):

```
python -m pytest tests/test_marketing_journey_p0.py -q -rs
  4 passed, 1 warning in 1.20s

python -m pytest tests/test_marketing_journey_p0.py tests/test_ui_wiring.py -q -rs
  16 passed, 1 warning in 1.25s

python -m pytest -q -rs
  239 passed, 1 warning in 80.10s
```

From `D:\NOVARA`:

```
node --check apps\web\app.js                    -> no syntax errors
python -m compileall -q apps\api\novara_core scripts\runtime_smoke.py -> no errors
python scripts\runtime_smoke.py                 -> RUNTIME SMOKE: PASS (sections 1-13)
python C:\...\novara_t059_migrate_check.py
  upgrade -> downgrade -> upgrade                -> ROUND TRIP PASS, campaign preserved
```

The only warning is the known Starlette/httpx TestClient deprecation notice.
No bearer tokens, response bodies or credentials were printed.

## Behavior proved

- A draft campaign is scheduled with a validated window (reversed dates are
  rejected), then `POST /due` activates only the due, still-open campaign and
  publishes a real status event.
- Journey steps are unique by position and limited to local recording actions;
  duplicate positions and delivery-style actions are rejected.
- Enrollment is unique per contact, refuses suppressed contacts, emits
  `campaign.entered` once (idempotency keyed), and a second `run` completes the
  journey and emits `campaign.exited`. A repeated run does not duplicate the
  `email.sent` event.
- Every listed lifecycle event is present in the registered event types and in
  the persisted events for the workspace; filtered analytics return exactly the
  requested kind and an unknown kind is a 422.
- Runtime smoke section [13] repeats schedule → activate → author step → enroll
  → run → engagement → three intake kinds → analytics query over real HTTP
  against a real uvicorn server.
- The module source contains no Mautic import, no HTTP/email/mail client and no
  external send call; the UI guard fails if a control is rendered without a
  dispatcher.

## Matrix accounting

Only MT-025, MT-112 and MT-115 were changed in `MASTER_FEATURE_MATRIX.csv`; all
seven FEATURE_PARITY deliverables were regenerated:

- 1,488 permanent IDs, zero omissions
- VERIFIED_COMPLETE 73 (was 70)
- complete-like 158 / 1,488 = 10.62% (was 155 / 10.42%)
- PARTIALLY_IMPLEMENTED 139 (was 142)
- P0: 111 rows — 66 verified, 4 partial, 32 replacement, 9 restricted

## Not claimed

- No real outbound email, SMS, ads, landing page, tracking pixel or webhook
  delivery; journey steps are local analytics only.
- No advanced segmentation builder, landing-page builder or external sync
  adapter; these remain explicit future work.
- No live Mautic instance, license or embedded Mautic source.
- No commit, push, tag, deployment or public publishing. Git HEAD remains
  `73e9f76`.

## Next

T-060: select from the 4 remaining P0 partial rows (PL-001, PL-043, MT-072,
NV-057).
