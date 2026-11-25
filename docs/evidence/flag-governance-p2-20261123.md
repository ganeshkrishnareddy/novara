# Advanced feature-flag governance — clean-room evidence (P2, 2026-11-23)

## Scope

This cluster closes fourteen GrowthBook commercial-tier rows by implementing
each capability from the **documented public method**, not from upstream source:

| Row | Capability | Local implementation |
|-----|-----------|----------------------|
| GB-183 | schedule-feature-flag | latest-started schedule resolves the effective flag state at a given time |
| GB-196 | hash-secure-attributes | salted SHA-256 of sensitive attribute values before matching |
| GB-206 | sticky-bucketing | deterministic SHA-256 bucket per user/flag, stored so it never flips on a rollout change |
| GB-209 | prerequisites | named flag must hold a required value before the dependent flag is on |
| GB-210 | prerequisite targeting | prerequisite may carry a saved all-clause targeting condition |
| GB-211 | redirect rule result | rule returns a local relative or http(s) target; no network fetch |
| GB-224 | environment inheritance | parent chain with child overrides applied last |
| GB-225 | reusable flag templates | saved definition instantiated into a named flag |
| GB-231 | safe rollout guardrails | guardrail delta decides rollback / hold / promote |
| GB-232 | require project for features | per-workspace setting, persisted |
| GB-233 | require project for SDK | per-workspace setting, persisted |
| GB-247 | ramp schedules | linear interpolation of traffic percentage over a time window |
| GB-248 | scheduled revisions | pending revision applied, then resolved by effective time |
| GB-249 | typed feature configurations | json/number/string/boolean config values, workspace-scoped |

## What is real

- **Backend module** `apps/api/novara_core/modules/feature_flag_governance.py`
  owns all fourteen capabilities and the `/flag-governance` API group.
- **Persistence** is twelve additive workspace-scoped tables created by Alembic
  revision `f6a7b8c9d0e1`. No existing table is altered.
- **Permissions**: `verify_workspace` plus `require(CONTACT_READ)` for reads and
  `require(NOTE_WRITE)` for writes. Cross-workspace identifiers return 404 or
  empty results. All mutations publish `flag.governance_changed` on NOVARA's
  shared event spine.
- **UI**: a dedicated `flag-governance` Operations route renders the local
  contract and every control. Static wiring guards live in `test_ui_wiring.py`.
- **No external access**: `socket.socket.connect` is patched to raise in every
  acceptance test. No GrowthBook source, SDK, hosted endpoint, licence server,
  warehouse or external service is contacted. No licensed enterprise code,
  entitlement or default paid dependency is used.

## Verification

Named acceptance tests in `apps/api/tests/test_feature_flag_governance_p2.py`:

1. `test_gb183_scheduled_flag_state` — latest started schedule wins, 422 on an
   invalid timestamp.
2. `test_gb196_hash_secure_attributes` — 64-character digest, no raw value,
   correct match and non-match.
3. `test_gb206_sticky_bucketing_stable` — variant unchanged across rollout
   percentages, 422 on out-of-range percent.
4. `test_gb209_prerequisites_value_check` — required value met/unmet reasons.
5. `test_gb210_prerequisite_targeting_conditions` — saved condition gates the
   prerequisite.
6. `test_gb211_redirect_rule_result` — local target returned, missing rule is
   null, unsafe scheme rejected.
7. `test_gb224_environment_inheritance` — parent chain plus child overrides.
8. `test_gb225_template_instantiation` — saved template instantiates a flag.
9. `test_gb231_safe_rollout_guardrail` — rollback, hold and promote decisions.
10. `test_gb232_gb233_workspace_settings` — both require-project settings
    persist and default to false.
11. `test_gb247_ramp_schedule` — 0/50/100 interpolation plus invalid window.
12. `test_gb248_scheduled_revisions` — unresolved before apply, resolved after.
13. `test_gb249_feature_configs_isolation` — typed config persists and is
    tenant-scoped, invalid type rejected.

Command (record exact result here after execution):

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_feature_flag_governance_p2.py apps/api/tests/test_ui_wiring.py -q --disable-warnings
```

## Honest limits

These are local, deterministic implementations over workspace data. They are
not a GrowthBook SDK, hosted platform, warehouse-connected system or licensed
enterprise feature. No external targeting service, licence check, redirect
fetch or paid dependency is used. No commit, push, deploy, publish or external
send was made.
