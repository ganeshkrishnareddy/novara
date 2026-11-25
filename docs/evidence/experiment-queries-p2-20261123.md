# Evidence — local experiment data exploration P2 cluster (T-090)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Eight named acceptance tests were added in
`apps/api/tests/test_experiment_queries_p2.py` and one static UI wiring guard in
`apps/api/tests/test_ui_wiring.py`. Every acceptance test drives the real
FastAPI app against real persisted, workspace-scoped experiment, flag,
assignment, exposure and time-series rows. No app code is mocked.

The implementation is a clean-room module,
`apps/api/novara_core/modules/experiment_queries.py`, registered in
`modules/__init__.py`. It owns eight additive workspace-scoped tables created by
Alembic revision `a8b1c2d3e4f5` (down revision `f7a8b1c2d3e4`). It reuses the
workspace identity, permission and event contracts already used by NOVARA's
experiment-statistics and experimentation-operations modules.

## Delivery boundary (important)

NOVARA does not contact GrowthBook, a warehouse, an external data source or any
hosted analytics platform. Fact tables and queries are local logical views over
this workspace's own rows. No warehouse SQL is assembled or executed against a
remote system, no GrowthBook source is copied, and no external SDK, MCP server
or AI adapter is claimed.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| GB-028 | `test_gb028_fact_tables_describe_shared_local_row_sets` | Fact tables declare a supported local source and explicit fields; unsupported sources, unknown fields and duplicate keys return 422/422/409; the listing and a real 20-row preview are workspace-scoped. |
| GB-027 | `test_gb027_discovery_queries_filter_and_project_local_facts` | A saved query filters and projects real observation rows, returning only the matching control row; unknown fields, invalid filters and duplicate keys are rejected with 422/422/409. |
| GB-034 | `test_gb034_assignment_queries_identify_exposed_units` | Assignment queries identify two real exposed units from flag exposures; source and reference validation, duplicate keys, filters and run results are verified. |
| GB-035 | `test_gb035_identifier_types_and_joins_resolve_local_ids` | Identifier types normalise and validate values with regex; two different types are joined with persisted mappings and resolve in both directions; invalid regex, duplicate types, same-type joins and bad directions are rejected. |
| GB-037 | `test_gb037_funnel_analysis_measures_ordered_steps` | An ordered assigned → exposed → converted funnel computes real counts [2, 2, 26], per-step rates and 13.0% overall conversion; reversed steps return 422. |
| GB-024 | `test_gb024_custom_reports_summarize_local_experiment_data` | Experiment-summary and funnel-summary reports persist locally and run over real rows; total sessions/conversions and both variants are verified; missing config and duplicate keys are rejected. |
| GB-101 | `test_gb101_carryover_guidance_warns_and_requires_ack` | A restart before the washout produces warning guidance and requires an acknowledgement before it clears; a compliant gap produces low-risk guidance; invalid dates and duplicate keys are rejected. |
| Cross-workspace | `test_experiment_queries_workspace_isolation` | A second workspace sees none of the first workspace's fact tables, queries, identifiers, joins, funnels, reports or carryover assessments and cannot fetch or resolve them by id. |
| UI | `test_experiment_queries_route_controls_are_rendered_and_dispatched` | The new `experiment-queries` Operations route renders live local data and every rendered control has exactly one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_experiment_queries_p2.py` -> **8 passed, 1 warning**.
- `pytest apps/api/tests/test_experiment_queries_p2.py apps/api/tests/test_ui_wiring.py`
  -> **34 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `a8b1c2d3e4f5`.
- `scripts/migration_roundtrip_check.py f7a8b1c2d3e4` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md`. The T-089 rerun that
  preceded this cluster was **581 passed, 2 warnings** with the eight failures
  confined to this cluster, which was collected before it was registered.

## Not claimed

No GrowthBook-hosted feature, external warehouse or data source, live
experiment assignment, third-party SDK, MCP server, agent tooling or AI adapter
is claimed. Rows outside this cluster remain in their existing matrix states.
