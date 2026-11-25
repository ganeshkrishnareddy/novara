# Evidence — clean-room work-item planning (T-102)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Fifteen named acceptance tests were added in
`apps/api/tests/test_work_item_planning_p2.py` (one per PL row plus a contract
guard, workspace isolation and write-permission checks) and one static UI
wiring guard in `apps/api/tests/test_ui_wiring.py`. Every test drives the real
FastAPI app with real persisted, workspace-scoped rows; no app code is mocked.

The clean-room module `apps/api/novara_core/modules/work_item_planning.py` owns
nine additive workspace-scoped tables created by Alembic revision `a1b2c3d4e5f6`
(down revision `f1a2b3c4d5e6`, merged into single head `f2b3c4d5e6f7`). They
extend NOVARA's existing `project_items`, `project_modules` and `project_pages`
tables by foreign key only. No existing table is altered.

## Delivery boundary (important)

This is a clean-room implementation written from each feature's documented
behaviour, not from Plane's Django, React or source tree. Notable honest limits:

- **Relations** create a symmetric row in the other work item; no upstream
  relation model or GraphQL layer is used.
- **Dependencies** are typed (`blocked_by`, `blocking`, `start_after`,
  `finish_before`) with local violation detection and timeline conflict
  markers; there is no external rules engine.
- **Estimates** persist schemes and values and aggregate by project/cycle;
  monthly recurrence uses a documented 30-day month, not a calendar library.
- **Roadmap, calendar, timeline and table** are derived views over persisted
  local rows with explicit, validated PATCH operations, not a spreadsheet or
  Gantt vendor component.
- **Recurrence** is materialised only by an explicit audited API/UI action.
  No background scheduler daemon, cron, queue or hosted service is claimed.
- **Subscribers** are the exact source for notification recipients; no email,
  push or webhook is sent and `external_delivery` is false.

The API contract reports `version: 1`, `legacy_versions: []`,
`external_calls: false`, `external_delivery: false`,
`scheduler: explicit local materialisation only` and `delivery: local-only`.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| PL-013 | `test_pl013_relations_create_inverse_and_appear_on_both_items` | Creating `implements` also creates `implemented_by` on the target; both items list the link; duplicates, self-links and unknown types fail. |
| PL-014 | `test_pl014_typed_dependencies_detect_violations` | Typed dependency persists, reports a violation while the prerequisite is open, clears when it is done; date-based kind and invalid inputs validated. |
| PL-016 | `test_pl016_estimates_persist_and_aggregate_by_project_and_cycle` | Points/category schemes persist; values and allowed categories validate; totals aggregate by project and by cycle. |
| PL-020 | `test_pl020_roadmap_groups_future_work_by_month_and_project` | Future due dates group by month and project without copying Plane source; unknown project fails closed. |
| PL-023 | `test_pl023_calendar_places_items_on_due_dates` | Items appear under their due date with a local item URL; date bounds filter correctly. |
| PL-024 | `test_pl024_timeline_persists_schedule_changes_and_marks_conflicts` | Timeline schedule PATCH persists to the work item, invalid ranges fail, and a `finish_before` violation renders as a conflict marker. |
| PL-025 | `test_pl025_table_cells_persist_with_validation` | Inline title/priority/status/date edits persist; invalid status, date, title length, unknown column and non-member assignee fail 422. |
| PL-035 | `test_pl035_updates_show_subitem_progress` | Short updates are separate records and report live sub-item done/total progress; empty body fails. |
| PL-036 | `test_pl036_templates_prefill_items_projects_and_pages` | Templates create prefilled items, projects and pages; duplicates conflict and missing project fails 422. |
| PL-037 | `test_pl037_recurrence_materializes_on_demand_emits_event` | A weekly rule creates the next item on the expected date, advances `next_at`, refuses early replay and publishes `planning.item_recurred`. |
| PL-136 | `test_pl136_worklogs_persist_and_sum_per_item` | Worklogs persist and sum to 135 minutes / 2.25 hours for one item; zero minutes fails. |
| PL-141 | `test_pl141_subscribers_drive_notification_recipients` | Subscriber set is the exact recipient source; duplicate/unknown/removed cases behave correctly; no external delivery. |
| Robustness | `test_planning_contract_declares_local_only_clean_room` | Contract advertises one API version, no legacy claims and explicit local-only recurrence. |
| Isolation | `test_planning_rows_are_workspace_isolated_and_write_protected` | A second workspace sees no planning rows and cannot read another workspace's item data; unauthenticated writes fail. |
| UI | `test_work_item_planning_route_controls_are_rendered_and_dispatched` | The `work-item-planning` Operations route renders all twelve feature panels; every control has a dispatcher and form handler. |

## Commands and results

- `pytest apps/api/tests/test_work_item_planning_p2.py` -> **14 passed, 1 warning**.
- `pytest apps/api/tests/test_work_item_planning_p2.py apps/api/tests/test_ui_wiring.py`
  -> **52 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `f2b3c4d5e6f7`.
- `scripts/migration_roundtrip_check.py f1a2b3c4d5e6` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md` when complete, never assumed.

## Not claimed

No Plane source, Django/React dependency, hosted endpoint, scheduler daemon,
websocket transport, outbound HTTP, PDF/Gantt renderer or real notification
delivery is claimed. Other Plane rows remain in their existing matrix states.
