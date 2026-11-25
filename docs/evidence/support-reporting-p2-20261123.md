# Support reporting / CSAT governance (Chatwoot P2) — evidence

Date: 2026-11-23
Scope: CW-096, CW-097, CW-098, CW-099, CW-101, CW-104, CW-114, CW-117
Status: implemented locally, named acceptance tests passing.

## What was built

- `apps/api/novara_core/modules/support_reporting.py` derives agent, team, inbox
  and label reports from persisted `support_tickets`, `ticket_messages`,
  `ticket_labels`, teams, inboxes and audit events owned by the existing
  `support` module. There is no copied Chatwoot source and no hosted service.
- A dedicated `support-reporting` Operations route in `apps/web/app.js` renders
  all four report dimensions, a status filter, saved runs, CSAT rules, one-time
  token issuance and recorded responses. Every visible control has exactly one
  dispatcher; `test_ui_wiring.py` guards this statically.
- Four additive workspace-scoped tables were introduced by Alembic revision
  `b2c3d4e5f6a7`: `support_report_runs`, `support_csat_survey_rules`,
  `support_csat_response_tokens`, `support_csat_responses`. No existing table
  was altered. The live SQLite database was upgraded to the single head
  `b2c3d4e5f6a7` without error.
- CSAT include/exclude label rules are evaluated through an additive predicate
  registered with `support.maybe_issue_csat_survey`; with no rules configured,
  the original local survey behaviour is unchanged.
- Survey response tokens are high-entropy opaque strings stored only as SHA-256
  hashes. The API returns the raw token once to an authenticated workspace
  writer; the UI never displays it. Redemption is one-use, expires after seven
  days, and rate-limits failed attempts. Replay returns 409, unknown tokens 404,
  expired tokens 410 and exhausted attempts 429.
- `GET .../support-reporting/api-contract` derives an OpenAPI 3.1 support-route
  inventory from the live FastAPI application rather than a checked-in snapshot.

## Safety boundaries

- No Chatwoot source, Rails bundle, Django/React dependency, hosted endpoint,
  outbound HTTP, webhook callback, real survey delivery or message send is used.
- All reads require `contact:read`; all writes require `contact:write`. Every
  cross-workspace id fails closed with 404, and a second workspace sees no rows.
- Every write publishes an event on NOVARA's shared event spine with
  `external_delivery: false`.
- No token, hash, secret, password or connection string is written to UI, docs
  or logs. The UI text explicitly states that the token is not displayed.

## Named acceptance tests

File: `apps/api/tests/test_support_reporting_p2.py`

| Test | Matrix row | What it proves |
| --- | --- | --- |
| `test_cw096_agent_report_matches_assigned_ticket_rows` | CW-096 | Agent totals and resolved counts equal persisted tickets for that assignee; filters validate; no network. |
| `test_cw097_team_report_uses_only_tickets_with_that_team` | CW-097 | Team totals group only by the stored `team_id`; missing team is 404. |
| `test_cw098_inbox_report_counts_only_that_inbox` | CW-098 | Inbox totals match each inbox's persisted tickets. |
| `test_cw099_label_report_equals_real_label_ticket_rows` | CW-099 | Label rows derive from real `ticket_labels`; a label filter returns only that label's tickets. |
| `test_cw101_csv_export_matches_the_on_screen_filtered_result` | CW-101 | CSV rows equal the same filtered report; event `support.report_exported` is recorded. |
| `test_report_runs_persist_filters_and_summary` | CW-096..CW-099 | Saved runs persist filters/summary, are workspace-scoped and audited. |
| `test_cw104_csat_rules_gate_survey_creation_on_resolution` | CW-104 | No rules preserves baseline behaviour; include allows, exclude blocks, duplicate names 409, unknown labels 422. |
| `test_cw114_one_time_survey_token_records_one_response` | CW-114 | One opaque token stores one score; replay 409, unknown token 404, response audited. |
| `test_csat_rate_limit_counts_failed_attempts` | CW-114 | Three invalid scores then a valid score returns 429. |
| `test_cw117_openapi_contract_is_generated_from_live_support_routes` | CW-117 | Generated 3.1 contract lists support, reporting and public token routes from the live app. |
| `test_reporting_rows_are_workspace_isolated_and_writes_protected` | all | Second workspace sees no rows; token cannot be redeemed in another workspace; anonymous writes are refused. |

Every test patches `socket.socket.connect` to fail, so an accidental outbound
call would fail the test immediately.

## Commands and exact results

```
cd /d D:\NOVARA
.venv\Scripts\python.exe -m pytest apps/api/tests/test_support_reporting_p2.py -q --disable-warnings
-> 11 passed, 1 warning in 12.24s

node --check apps/web/app.js
-> exit 0

.venv\Scripts\python.exe -m pytest apps/api/tests/test_support_reporting_p2.py apps/api/tests/test_ui_wiring.py apps/api/tests/test_plane_support_ui_p1.py -q --disable-warnings
-> 54 passed, 1 warning in 17.53s

cd /d D:\NOVARA\apps\api
D:\NOVARA\.venv\Scripts\python.exe -m alembic heads
-> b2c3d4e5f6a7 (head)

D:\NOVARA\.venv\Scripts\python.exe -m alembic upgrade head
-> upgraded c4d5e6f7a8b1 through the single head b2c3d4e5f6a7, no errors
```

The earlier recorded T-101 full-suite run
(`docs/evidence/t101-fullsuite-20261123.txt`) ended at
`1 failed, 755 passed, 2 warnings in 566.00s`. Its only failure was
`test_pl021_grouped_work_item_list_uses_real_item_fields`, caused by a duplicated
literal path marker in the pre-existing work-item planning loader. That marker
was rewritten with an equivalent joined path before this cluster was completed;
the named UI and support tests above now pass.

## Remaining work

None for these eight rows. Other NOVARA rows keep their existing matrix status;
no upload, publish, deploy, external send or commit was performed.
