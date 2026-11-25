# Evidence — GrowthBook experimentation operations P2 cluster (T-089)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Eleven named acceptance tests were added in
`apps/api/tests/test_experiment_operations_p2.py` and one static UI wiring guard
in `apps/api/tests/test_ui_wiring.py`. Every test drives the real FastAPI app
against real persisted, workspace-scoped rows. No app code is mocked, no
GrowthBook source is copied and no hosted experiment platform, warehouse or
analytics service is contacted.

The implementation is a clean-room module,
`apps/api/novara_core/modules/experiment_operations.py`, registered in
`modules/__init__.py`. It owns nine additive workspace-scoped tables created by
Alembic revision `f7a8b1c2d3e4` (down revision `e6f7a8b1c2d3`). The module builds
on NOVARA's existing `feature_flags` tables (`FeatureFlag`, `FlagRule`,
`FlagEnvironmentState`, `FlagAssignment`, `FlagExposure`) and reuses the same
local evaluator so diagnostics cannot disagree with real flag evaluation.

## Delivery boundary (important)

NOVARA does not contact GrowthBook, a warehouse or any hosted experiment
platform. Projects, saved groups, revisions, archives, dimensions, segments,
A/A tests and time-series points are stored locally. Diagnostics explain the
result of NOVARA's own local flag evaluator. No claim of GrowthBook-hosted
compatibility, external data-source connectivity, live experiment assignment
or third-party SDK integration is made.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| GB-007 | `test_gb007_projects_namespace_flags_experiments_and_settings` | Projects are created, listed and archived per workspace; duplicate keys return 409 and malformed keys 422. |
| GB-012 | `test_gb012_saved_groups_evaluate_local_targeting_lists` | A saved group with two attribute conditions evaluates true for a matching user and false for a non-matching user; duplicate keys 409, invalid operators 422, groups scoped to their project. |
| GB-013 | `test_gb013_flag_archive_and_history_keeps_full_change_record` | Archive records a reason, disables the flag and appears with the ordered revision history; restore clears the archived state and records a timestamp; double restore 422. |
| GB-014 | `test_gb014_draft_revisions_do_not_affect_evaluation_until_published` | A draft revision leaves the live flag unchanged; duplicate drafts 409, rollout outside 0-100 returns 422; publishing applies enabled/rollout/description and cannot be repeated. |
| GB-025 | `test_gb025_dimensions_breakdown_validates_declared_values` | Dimensions persist with declared values; breakdown accepts a declared value with a real session count and rejects unknown values, duplicate keys and negative counts. |
| GB-026 | `test_gb026_segments_are_reusable_attribute_slices` | A reusable segment with equality and greater-than rules evaluates real attributes; duplicate keys 409 and unknown operators 422. |
| GB-039 | `test_gb039_aa_tests_validate_assignment_and_metric_plumbing` | A/A test records observations for two identical variants and passes when rates differ by < 1 percentage point; a 20-point imbalance fails; conversions > sessions 422. |
| GB-041 | `test_gb041_experiment_timeseries_gives_cumulative_impact_by_day` | Three days of points produce cumulative session/conversion series [100,300,600] and [10,40,100]; malformed days 422 and the same key upserts instead of duplicating. |
| GB-048 | `test_gb048_stale_flags_detection` | Flags are flagged for being disabled, fully rolled out, never delivered or archived; a real local evaluation removes the `never_exposed` reason by recording an assignment, and archiving adds the `archived` reason. |
| GB-049 | `test_gb049_diagnostics_explain_why_a_user_received_a_value` | Diagnostics call the same local evaluator as the live flag route, return the winning variant and reason (`rule_match`), and expose a five-step trail (flag state, environment, prerequisites, rules, saved groups) that changes for a non-matching user. |
| Cross-workspace | `test_experiment_ops_workspace_isolation` | A second workspace sees no projects/dimensions/segments/A-A tests/stale flags/time-series data and cannot read or mutate the first workspace's flag history, saved groups, segments or archive state. |
| UI | `test_experiment_ops_route_controls_are_rendered_and_dispatched` | The `experiment-ops` Operations route renders live project, flag, segment and A/A data and every rendered control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_experiment_operations_p2.py` -> **11 passed**.
- `pytest apps/api/tests/test_experiment_operations_p2.py apps/api/tests/test_ui_wiring.py`
  -> **36 passed, 1 warning**.
- `pytest apps/api/tests -q --disable-warnings` -> full-suite result recorded in
  `docs/TEST_RESULTS.md`.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `f7a8b1c2d3e4`.
- `scripts/migration_roundtrip_check.py e6f7a8b1c2d3` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Fresh-DB `alembic upgrade head` then `alembic check` -> **No new upgrade
  operations detected**.

## Not claimed

No GrowthBook-hosted feature, external warehouse, data source, live experiment
assignment, third-party SDK, MCP server, agent tooling or AI adapter is claimed.
Rows outside this cluster remain in their existing matrix states.
