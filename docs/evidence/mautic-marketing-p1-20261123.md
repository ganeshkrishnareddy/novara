# Mautic-compatible marketing P1 — named acceptance evidence (2026-11-23)

All tests run against clean-room NOVARA code. Contacts, events and local
delivery records are real rows; the only socket is the webhook test's own
loopback HTTP server. Command:

```
D:\NOVARA\.venv\Scripts\python.exe -m pytest apps/api/tests/test_mautic_marketing_p1.py -q --disable-warnings
# 19 passed, 1 warning in 9.21s
```

| Master ID | Named test | Proved locally |
|---|---|---|
| MT-001 | `test_mt001_native_marketing_module_is_real_and_workspace_scoped` | A real native campaign/segment/journey/enrollment/run lifecycle persists, validates, enforces workspace isolation and emits real events; no Mautic source or HTTP client is imported. |
| MT-003 | `test_mt003_extension_contract_is_documented_and_enforced` | Documented extension contract with register/dispatch/unregister and isolated context copies. |
| MT-007 | `test_mt007_contact_profile_search_and_update_are_auditable` | Profile patch, query/tag/custom-field search and audited events; JSON filtering now uses portable SQLAlchemy 2 extraction on SQLite and `->>` on PostgreSQL. |
| MT-011 | `test_mt011_custom_fields_validate_filter_and_public_update` | Field definitions, required/select/number validation, filtering, signed public updates and audited definition/value changes. |
| MT-016 | `test_mt016_token_rendering_escapes_defaults_urls_and_dates` | Token substitution escapes values, applies defaults and formats dates without injection. |
| MT-030 | `test_mt030_forms_create_or_update_contacts_and_trigger_actions` | Header token validation (missing/invalid 401, bad answers 422), contact create/update, tag/lifecycle/enroll actions and submission history. The token is now a real request header, not an ignored query parameter. |
| MT-033 | `test_mt033_scoring_rules_apply_with_history` | Rules applied in definition order update `Lead.score`; cumulative history is `[10, 25, 30]`; rule changes audited. |
| MT-035 | `test_mt035_stage_definitions_guard_transitions_and_record_history` | Stage definitions guard transitions and record history. |
| MT-042 | `test_mt042_sms_stop_reply_blocks_local_sms_delivery` | Opt-out stops local SMS and is audited. |
| MT-045 | `test_mt045_marketing_messages_resolve_preferred_channel_and_send_once` | Channel preference resolves and produces one local delivery attempt. |
| MT-046 | `test_mt046_channel_frequency_caps_and_pause_are_enforced` | Frequency caps and pauses are enforced. |
| MT-047 | `test_mt047_configurable_marketing_reports_run_from_local_data` | Configurable reports run from local rows. |
| MT-050 | `test_mt050_webhooks_are_signed_retried_and_logged` | Signed payloads are delivered to a loopback receiver, non-2xx replies are logged with their real HTTP status and retried; no secret is exposed in logs. |
| MT-069 | `test_mt069_scheduled_jobs_run_and_leave_observable_runs` | Scheduled jobs run and leave observable real runs. |
| MT-070 | `test_mt070_marketing_event_catalogue_registers_extension_events` | Marketing lifecycle events are registered on the shared event spine. |
| MT-107 | `test_mt107_derivative_distribution_is_explicitly_out_of_scope` | Distribution of derivative material is explicitly out of scope; no review is claimed. |
| MT-114 | `test_mt114_legacy_scope_translation_maps_to_existing_rbac` | Legacy scopes map deterministically to NOVARA permissions. |
| MT-117 | `test_mt117_funnel_engagement_and_attribution_use_local_events` | Funnel, engagement and attribution are computed from real local events, including pre-entry form submissions linked through enrollment rows. |
| MT-122 | `test_mt122_contact_anonymization_preserves_audit_trail` | Contact anonymisation preserves the audit trail. |

PostgreSQL JSON behaviour is verified by SQL compilation only (the test
environment is SQLite); no PostgreSQL server is available here.
