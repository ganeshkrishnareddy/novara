# Advanced experimentation statistics — clean-room evidence (P2, 2026-11-23)

## Scope

This cluster closes eight GrowthBook commercial-tier rows by implementing each
capability from the **documented public method**, not from upstream source:

| Row | Capability | Local implementation |
|-----|-----------|----------------------|
| GB-187 | regression-adjustment | CUPED: `theta = Cov(pre, post) / Var(pre)`, adjusted effect and variance-reduction ratio |
| GB-188 | post-stratification | size-weighted mean of per-stratum control/treatment effects |
| GB-189 | sequential testing | mSPRT always-valid boundary plus O'Brien-Fleming alpha spending |
| GB-214 | quantile metrics | interpolated quantile with deterministic seeded bootstrap percentile interval |
| GB-215 | retention metrics | day-N retention curve from cohort counts with validation |
| GB-217 | compound metrics | weighted component composition with a single score |
| GB-222 | multi-armed bandits | Thompson sampling (Marsaglia-Tsang gamma / beta sampling) and UCB, with Bayesian reward updates |
| GB-237 | metric correlations | Pearson product-moment correlation with `r²` |

## What is real

- **Backend module** `apps/api/novara_core/modules/experiment_advanced_stats.py`
  owns all eight algorithms and the `/advanced-experiments` API group.
- **Persistence** is three additive workspace-scoped tables created by Alembic
  revision `e5f6a7b8c9d0`: `adv_analyses`, `adv_bandit_arms`, `adv_holdouts`.
  No existing table is altered.
- **Permissions**: `verify_workspace` plus `require(CONTACT_READ)` for reads and
  `require(NOTE_WRITE)` for writes. Cross-workspace analysis ids return 404 and
  cross-workspace bandit state is empty. All mutations publish events on the
  shared NOVARA event spine.
- **UI**: a dedicated `advanced-experiments` Operations route renders the local
  contract, saved analyses, bandit state, recommendation/reward controls and
  holdout assignment. Static wiring guards live in `test_ui_wiring.py`.
- **No external access**: `socket.socket.connect` is patched to raise in every
  acceptance test. No GrowthBook source, stats package, hosted platform,
  warehouse, SDK or external statistics service is contacted. No licensed
  enterprise code, entitlement or default paid dependency is used.

## Verification

Named acceptance tests in `apps/api/tests/test_experiment_advanced_stats_p2.py`:

1. `test_gb187_cuped_variance_reduction` — positive theta, adjusted variance below
   raw variance, persisted/retrievable analysis, cross-workspace 404, 422 on
   mismatched series.
2. `test_gb188_post_stratification_weighted_effect` — two strata, 12 units,
   weighted effect between 3 and 6, 422 on incomplete strata.
3. `test_gb189_sequential_testing_boundaries` — early OBF boundary larger than
   final, early stop false, final and mSPRT stop true, 422 on zero information.
4. `test_gb214_quantile_metric_bootstrap` — p50 of 1..100 equals 50.5, interval
   contains the point estimate and is deterministic for a fixed seed.
5. `test_gb215_retention_metrics_curve` — day-ordered curve, day-0 = 1.0,
   day-30 = 0.25, 422 when retained exceeds cohort size.
6. `test_gb217_compound_metrics_weighted_score` — weighted score 12.5 from
   10×3 and 20×1, 422 on zero weight.
7. `test_gb222_bandit_recommend_and_reward` — arms persisted, Thompson and UCB
   recommendations valid and deterministic, reward updates alpha/beta/pulls,
   cross-workspace isolation, 404 on missing arm, holdout created and checked.
8. `test_gb237_metric_correlation` — r = 1.0 for a linear series, 422 on a
   constant series.

Targeted result:

```
$env:PYTHONPATH='apps/api'; .venv\Scripts\python.exe -m pytest apps/api/tests/test_experiment_advanced_stats_p2.py apps/web/tests/ui_v68_experiment_advanced_stats_contract.py -q --disable-warnings
9 passed, 1 warning in 7.94s
```

Combined clean full suite (T-105 + T-106, one run):

```
.venv\Scripts\python.exe -m pytest apps/api/tests -q --disable-warnings
797 passed, 2 warnings in 578.96s (0:09:38)
```
Evidence: `docs/evidence/t106-fullsuite-20261123.txt` (exit 0).

## Honest limits

These are local, deterministic algorithm implementations over workspace data.
They do not connect to a warehouse, event stream, SDK payload or call a hosted
GrowthBook instance. Statistical correctness is proven by the named tests above;
no claim is made about parity with a licensed enterprise build at production
scale. Rows that genuinely require provider credentials, hosted approval or
external delivery remain `EXTERNAL_DEPENDENCY_BLOCKED` and are untouched.
