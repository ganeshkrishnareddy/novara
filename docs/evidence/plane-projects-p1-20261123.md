# Plane projects — P1 evidence (2026-11-23)

## Status
15 named acceptance tests pass. Clean-room implementation; no Plane source was
used and no external service was contacted.

## Command
```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_plane_projects_p1.py -q
```
Result: **15 passed** (Starlette/httpx deprecation warning only).

## IDs closed
PL-005, PL-007, PL-009, PL-010, PL-011, PL-012, PL-015, PL-018, PL-022,
PL-026, PL-027, PL-029, PL-030, PL-079, PL-094.

## What is proven
- Project states, assignees, membership and workspace isolation.
- Work-item CRUD, descriptions with immutable versions, priorities, labels,
  dependencies, milestones, pages, comments, cycles and assignment windows.
- Board grouping by real workflow states; saved views restore filters, layout,
  sort and sharing; modules carry leads, dates, members and progress.
- Item activity is an immutable field-change history on the shared event spine.
- Cross-workspace access is denied (403) and missing resources return 404.

## UI evidence
`apps/web/app.js` project detail now loads board, views, labels and modules
from the real API and exposes: priority filter, saved-view selector, Board /
Labels / Modules / Activity buttons, label-create form, and the matching
modals/dispatchers. Guard:
`test_ui_wiring.py::test_project_p1_work_management_controls_are_wired`.
`node --check apps/web/app.js` OK.

## Scope notes
Rows whose acceptance criteria explicitly require a browser screenshot remain
honestly scoped to backend + wired UI with a static wiring guard; no fake live
data or placeholder success messages were introduced.
