# GrowthBook feature flags — P1 evidence (2026-11-23)

## Status
20 named acceptance tests pass. All work is local; no GrowthBook source was
used and no external service was contacted.

## Command
```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_growthbook_flags_p1.py -q
```
Result: **20 passed** (Starlette/httpx deprecation warning only).

## IDs closed
GB-001, GB-002, GB-003, GB-004, GB-005, GB-006, GB-008, GB-009, GB-010,
GB-011, GB-015, GB-016, GB-017, GB-018, GB-019, GB-036, GB-055, GB-056,
GB-057, GB-058.

## What is proven
- Feature keys: validation, immutability, workspace isolation, audit events.
- Kill switch, per-environment independent state, default values, ordered
  first-match-wins rules, targeting operators, deterministic percentage
  rollout, prerequisites, variant weights and experiment-reference rules.
- Local experiment result table computed from real local result rows.
- Exposure callbacks record the first assignment per user and are audited.
- SDK connections are revocable, environment-scoped and audited; the SDK
  payload endpoint rejects missing/wrong/cross-workspace keys (401/403).
- `evaluate_local()` matches server evaluation without an HTTP round trip;
  remote configuration reflects flag/environment/rule changes immediately.

## UI evidence
`apps/web/app.js` Workspaces → Feature flags now provides: environment
selector, default-value column, Rules and Exposure modals, SDK-key creation
with one-time secret display, SDK payload viewer, and a rule-create form.
Guard: `test_ui_wiring.py::test_feature_flag_p1_controls_are_wired_and_guarded`
(one dispatcher per control, no duplicates). `node --check apps/web/app.js` OK.

## Scope notes
No licence-restricted code was copied. All implementations are clean-room and
local-first. GB-110..GB-116 were closed separately in T-062.
