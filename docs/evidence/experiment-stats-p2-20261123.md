# Evidence — GrowthBook experimentation statistics P2 cluster (T-088)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Twelve named acceptance tests were added in
`apps/api/tests/test_experiment_stats_p2.py` and one static UI wiring guard in
`apps/api/tests/test_ui_wiring.py`. Every test drives the real FastAPI app
against real persisted, workspace-scoped rows. No app code is mocked, no
GrowthBook source is copied and no external statistics service or hosted
experiment platform is contacted.

The implementation is a clean-room module,
`apps/api/novara_core/modules/experiment_stats.py`, registered in
`modules/__init__.py`. It owns three additive workspace-scoped tables created
by Alembic revision `e6f7a8b1c2d3` (down revision `d5e6f7a8b1c2`). All
mathematics is implemented locally with the Python standard library
(normal CDF/PPF via Abramowitz-Stegun and bisection, chi-square survival via
the regularised incomplete gamma function); SciPy is not used.

## Delivery boundary (important)

NOVARA does not contact GrowthBook, an external statistics service or any
hosted experiment platform. Experiment definitions, metric definitions and
observations are stored locally. Analysis results are computed on demand from
persisted observations. No claim of GrowthBook-hosted compatibility, external
data-source connectivity, live experiment assignment or third-party SDK
integration is made.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| GB-020 | `test_gb020_bayesian_engine_returns_probability_and_expected_loss` | Bayesian engine returns posterior probability that the variant beats control, expected loss and a credible interval; a 10% -> 30% conversion lift yields P(B>A) > 0.99 and near-zero loss. |
| GB-021 | `test_gb021_frequentist_engine_returns_p_value_and_confidence_interval` | Frequentist engine returns z-statistic, two-sided p-value and a 95% confidence interval; a strong lift gives p < 0.01 with a strictly positive interval; invalid engine names are rejected. |
| GB-022 | `test_gb022_srm_detects_skewed_traffic_and_accepts_balanced` | Chi-square sample-ratio-mismatch check passes a balanced 100/100 split and flags a skewed 100/160 split (p < 0.001, chi-square > 13); expected traffic totals equal observed totals. |
| GB-023 | `test_gb023_health_reports_low_sample_missing_variant_and_healthy` | Health check reports `healthy` for well-exposed variants and raises `low_sample` plus `no_exposure` diagnostics for an under-exposed experiment. |
| GB-029 | `test_gb029_030_031_032_metric_definitions_are_typed_and_validated` | Typed metric definitions (proportion/mean/ratio) persist and list per workspace; duplicate keys return 409 and unknown types 422. |
| GB-030 | `test_gb029_030_031_032_metric_definitions_are_typed_and_validated` plus both engine tests | Binary conversion metrics are defined as `proportion` and analysed in both engine tests using stored `sessions`/`conversions`; the frequentist result uses a pooled standard error and the Bayesian result uses Beta posteriors. |
| GB-031 | `test_gb031_mean_metric_analysis_uses_stored_variance` | Mean metric analysis derives mean 5.0 vs 5.3 from `value_sum/sessions` with variance from `value_sq_sum`, producing a ~0.3 difference and p < 0.05. |
| GB-032 | `test_gb032_ratio_metric_analysis_uses_delta_method` | Ratio metric analysis computes numerator/denominator ratio with delta-method variance from stored second moments; difference ~0.3 and a valid p-value. |
| GB-038 | `test_gb038_power_analysis_computes_sample_size_and_mde` | Normal-approximation power analysis returns required sample per variant for a given MDE and the detectable MDE for a given sample size; invalid baseline rates are rejected. |
| GB-042 | `test_gb042_multiple_testing_corrections` | Bonferroni and Benjamini-Hochberg adjusted p-values and significance flags are computed correctly over four p-values; out-of-range p-values are rejected. |
| Validation | `test_experiment_variants_and_observations_are_validated` | Traffic shares must sum to 1, 2-10 unique variants, unknown variants rejected, conversions cannot exceed sessions, and repeated observations upsert rather than duplicate. |
| Cross-workspace | `test_experiment_stats_workspace_isolation` | A second workspace sees no metrics/experiments and cannot analyse or post observations against the first workspace's experiment. |
| UI | `test_experiment_stats_route_controls_are_rendered_and_dispatched` | The `experiment-stats` Operations route renders live metric/experiment data and every rendered control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_experiment_stats_p2.py` -> **12 passed**.
- `pytest apps/api/tests/test_experiment_stats_p2.py apps/api/tests/test_ui_wiring.py`
  -> **36 passed, 1 warning**.
- `pytest apps/api/tests -q --disable-warnings` -> full-suite result recorded in
  `docs/TEST_RESULTS.md`.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `e6f7a8b1c2d3`.
- `scripts/migration_roundtrip_check.py d5e6f7a8b1c2` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Fresh-DB `alembic upgrade head` then `alembic check` -> **No new upgrade
  operations detected**.

## Not claimed

No GrowthBook-hosted feature, external data source, live experiment assignment,
third-party SDK, MCP server, agent tooling or AI adapter is claimed. Rows
outside this cluster remain in their existing matrix states.
