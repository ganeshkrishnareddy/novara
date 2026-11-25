# T-062 evidence — P1 analytics experiments and UI (GB-110–GB-116)

## Scope

All seven P1 rows were `BACKEND_ONLY`: the analytics module already had real
CRUD, status, results, funnel and event-volume endpoints with named backend
tests, but no user-facing experiment experience. This cycle added that UI and
proved every criterion with named tests and a real browser walkthrough.

| ID | Criterion | Evidence |
| --- | --- | --- |
| GB-110 | UI list/create/edit/delete use the real API | browser steps 3, 4, 7, 8; `test_experiment_crud_status_and_audit_are_ui_reachable` |
| GB-111 | Status changes with workspace isolation | browser step 5; `test_experiment_crud_status_and_audit_are_ui_reachable` |
| GB-112 | Valid results stored, invalid rejected | browser step 6; `test_experiment_results_and_aggregates_use_real_local_rows` |
| GB-113 | Funnel counts from real rows, one workspace | `test_experiment_results_and_aggregates_use_real_local_rows` |
| GB-114 | Event volume date-filtered and workspace-isolated | same named test |
| GB-115 | Experiment audit events: type, workspace, append-only | `test_experiment_crud_status_and_audit_are_ui_reachable` |
| GB-116 | Validation, isolation, no partial writes | both named tests |

## What was built

- `apps/web/app.js` `loadInsights()` now loads `GET /analytics` alongside the
  funnel and event-volume feeds and renders an Experiments table with live
  status, metric and target columns.
- Five wired controls with exactly one dispatcher each: New experiment,
  Results, Change status, Edit experiment, Delete experiment. Four matching
  forms use `POST`, `PATCH`, `POST /status` and `POST /results` on the real API.
- A result modal shows recorded variant rows with a derived conversion rate and
  rejects `conversions > impressions` at the API boundary.
- Fixed a genuine bug found by the browser walkthrough: HTML number inputs
  default to `step=1`, so decimal baselines/targets failed native validation
  before reaching the API. `field()` now supports `step`, and the experiment
  fields use `step="any"`; result counters use `min="0"`.

## Browser walkthrough (built-in Browser surface)

Run against a real uvicorn server on `127.0.0.1:8765` with a disposable SQLite
database. All actions were performed in the NOVARA SPA, not by calling the API
directly.

1. First-run setup completed through the UI; owner session established.
2. Navigated to **Insights**; the Experiments card rendered with an empty state.
3. **New experiment** → filled name `Browser onboarding test`, metric
   `activation_rate`, baseline `0.28`, target `0.35` and a hypothesis →
   submitted. The row appeared in the table as **Draft** with target `0.35`.
4. Decimal validation was initially observed failing on the two number inputs;
   the field helper was corrected and the flow re-run successfully.
5. **Change status** → selected `Running` → the row updated to **Running**.
6. **Results** → recorded `control`, 200 impressions, 24 conversions. Reopening
   the modal showed `control | 200 | 24 | 12.0%`.
7. **Edit experiment** → target changed to `0.5` → the table showed `0.5`.
8. **Delete experiment** → confirmation → the table returned to the empty state.

Screenshot of the populated state:
`docs/evidence/analytics-experiments-p1-20261123.png`.
No external analytics provider was contacted; all figures came from local rows.

## Commands

```
node --check apps\web\app.js                                  -> no syntax errors
python -m pytest tests/test_analytics_experiments_p1.py -q    -> 2 passed
python -m pytest tests/test_ui_wiring.py -q                   -> new guard passed
```

Named guard: `test_ui_wiring.py::test_experiment_management_ui_is_routed_and_wired`
asserts one dispatcher per action/form and no duplicate handlers.
