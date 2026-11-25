# Plane/Support UI wiring — named evidence (2026-11-23)

Every API assertion drives the real FastAPI app. Every UI assertion reads the
actual `apps/web/app.js` source, so a control without a live handler cannot pass.
No external call, mock delivery or provider credential is involved.

| Master ID | Named test | Proved locally |
|---|---|---|
| PL-021 | `test_plane_support_ui_p1.py::test_pl021_grouped_work_item_list_uses_real_item_fields` | A work item with state, priority, assignee and start/due dates created through the API appears in the grouped list source; the legacy task table is retained; markers assert one renderer using real `ItemOut` fields. |
| PL-042 | `test_plane_support_ui_p1.py::test_pl042_progress_cards_match_sql_counts` | Three real items (1 todo, 2 done) produce `/progress` counts `3/1/0/2` and `66.67%`; the SPA renders those exact buckets and computed percentage — no invented velocity data. |
| CW-023 | `test_plane_support_ui_p1.py::test_cw023_saved_reply_ui_insert_expands_without_sending` | A saved reply expands with real contact/ticket data, reports an unresolved variable, leaves the ticket message list empty, and the SPA has exactly one insert handler, one expand handler and a notice element. |
| CW-075 | `test_plane_support_ui_p1.py::test_cw075_segment_ui_reuse_filters_inbox` | A stored segment returns exactly the matching contact and count `1`; the inbox toolbar exposes the segment select, loads its contacts and displays the selected segment info. |

## Commands and results

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_plane_support_ui_p1.py apps/api/tests/test_ui_wiring.py apps/api/tests/test_api_keys_p1.py apps/api/tests/test_project_intake_p1.py -q --disable-warnings
# 28 passed, 1 warning in 6.79s

node --check apps/web/app.js
# exit 0
```

## Honest limitations

- These are source-level UI wiring guards plus real API assertions; they prove
  handlers and renderers exist and are bound to real fields. They are not a
  full browser interaction/E2E run against a live server.
- Saved-reply insertion fills the local composer only; sending remains a
  separate explicit action and is not exercised here.
- Segment filtering is local set filtering over the segment contact API result;
  no external audience provider is contacted.
