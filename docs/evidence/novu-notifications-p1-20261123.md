# Novu P1 evidence — 2026-11-23

## Scope and method

- Acceptance suite: `apps/api/tests/test_novu_notifications_p1.py` — **22 named tests, 22 passed** (`python -m pytest apps/api/tests/test_novu_notifications_p1.py -q --disable-warnings`).
- Every test drives the real FastAPI app with bootstrap/auth fixtures, asserts over persisted workspace rows or real HTTP responses, and uses an isolated test workspace. A second workspace is used for isolation checks.
- The suite is local-only: adapters record `local_mock` calls with `delivered: false`, jobs execute registered local handlers, and no test claims a provider delivery. Time-dependent workflow state is advanced by updating stored `fire_at`/`locked_at` rows, not by faking a clock in the app.
- Source behaviour was accounted for from the existing NOVARA feature catalogue and the Novu feature names; no Novu server source was copied. Where the source mechanism is unavailable locally (subscriber HMAC sessions, `apps/ws` WebSockets), the acceptance criterion is met through a different mechanism and the row is recorded as a compatible replacement, not as source-equivalent.

## Implementation touched

- `apps/api/novara_core/modules/automation.py`: persisted `AutomationPayloadSchema`, `Topic`, `TopicSubscription`, `DigestBucket`, `ThrottleCounter`, `ScheduledRun`, `WorkflowDelayState`, `WorkflowRunStep`, `WorkflowMessageLink`; bulk/topic triggers, digest/throttle endpoints, payload-schema validation, condition reasons, dynamic/scheduled delays, run-timeline correlation.
- `apps/api/novara_core/modules/notification_preferences.py`: per-workspace preferences and a template preview route that applies filters **before** HTML escaping and rejects script/secret variables.
- `apps/api/novara_core/modules/adapters.py`, `modules/jobs.py`, `modules/operations.py`: truthful capability catalog, message records, failed-message ledger, retry policy and queue health.
- `apps/web/app.js`, `apps/web/styles.css`: native light-theme notification panel, bell/unread badge and SSE stream subscription.

## Test-to-feature evidence

| Feature | Named test | Verified behaviour |
| --- | --- | --- |
| NV-003 | `test_nv003_bulk_trigger_creates_one_audited_run_per_recipient_and_is_idempotent` | One audited run and correlated event per recipient, replay-safe idempotency, 50-recipient cap, foreign users rejected. |
| NV-004 | `test_nv004_topic_trigger_fans_out_only_to_matching_subscriptions_with_actor_exclusion` | Only matching subscriptions receive runs; excluded actors and foreign-workspace subscribers do not. |
| NV-008 | `test_nv008_nested_conditions_include_exclude_real_steps_with_skip_reasons` | Nested conditions include/skip real steps and the stored trace records why. |
| NV-010 | `test_nv010_delayed_run_stays_observable_and_resumes_the_same_run` | Deferred run remains queryable and resumes the same stored run after `fire_at` elapses. |
| NV-011 | `test_nv011_scheduled_notification_resolves_recipient_timezone_and_fires` | Wall-clock slot is resolved in the recipient time zone and fires once. |
| NV-048 | `test_nv048_run_timeline_records_real_step_outcomes_and_linked_messages` | Step-by-step stored outcomes and linked local messages, not inferred status. |
| NV-106 | `test_nv106_event_retrieve_exposes_real_steps_and_generated_messages` | Event retrieve by id returns real steps and generated local messages. |
| NV-012 | `test_nv012_digest_window_batches_events_into_one_downstream_execution` | Three events in one window form one bucket, one flush, one downstream run with the grouped count; double flush conflicts. |
| NV-014 | `test_nv014_throttle_skips_extra_triggers_without_creating_a_message` | Extra trigger is `skipped`, produces no run or message, and emits `throttle.skipped`. |
| NV-018 | `test_nv018_payload_schema_rejects_invalid_triggers_before_any_run` | Missing/wrong-type/unknown fields return 422 and create no run; valid payload runs. |
| NV-025 | `test_nv025_provider_catalog_reports_four_truthful_capability_states` | `configured`, `disabled`, `not_configured`, `blocked` states with consistent counts; mock invoke reports `delivered: false`; blocked provider stays blocked. |
| NV-051 | `test_nv051_retry_policy_is_documented_per_layer_and_mocks_are_not_deliveries` | Retry policy states local jobs implemented, provider/webhook layers not implemented; failed job dead-letters and retried job requeues with backoff; no Notification row is created. |
| NV-052 | `test_nv052_failed_messages_are_queryable_and_emit_audit_events` | Failed messages are queryable by transaction/channel, workspace-scoped, and emit `message.failed` audit events without a delivered claim. |
| NV-081 | `test_nv081_queue_health_reports_local_state_and_recovery_is_workspace_scoped` | Health reports local state and stale running jobs; recovery requeues only the owning workspace's stale job. |
| NV-085 | `test_nv085_message_records_are_queryable_by_channel_subscriber_and_transaction` | Message records filter by channel/subscriber/transaction, are `delivered: false`, deduplicate and support delete. |
| NV-033 | `test_nv033_native_light_theme_notification_panel_uses_only_the_local_api` | Source contract: native panel and actions call only the local API, no foreign Inbox dependency, light-only stylesheet. This is a source-contract test, not a browser E2E run. |
| NV-034 | `test_nv034_bell_unread_counts_match_the_database_after_create_and_read` | Unread/unseen counts come from persisted rows and change after read/read-all actions; the UI badge hook exists. |
| NV-042 | `test_nv042_notification_api_cannot_be_read_by_guessing_a_subscriber_id` | Guessed subscriber ids without a session return 401; with a session they cannot reveal another user's notifications or mark them read. Equivalent outcome via NOVARA bearer sessions, **not** Novu HMAC subscriber sessions. |
| NV-089 | `test_nv089_notification_stream_updates_without_a_manual_reload_and_is_workspace_scoped` | Server-sent event stream pushes real count snapshots, denies a foreign workspace and reflects a new notification without reload. Equivalent outcome via local SSE, **not** `apps/ws` WebSockets. |
| NV-099 | `test_nv099_templates_resolve_allowed_variables_and_reject_scripts_or_credentials` | Allowed variables and `lower`/`upper` filters resolve with HTML escaping; scripts, iframes, secret variables and expressions are rejected with 422 and never echoed. |
| NV-045 | `test_nv045_topics_are_workspace_unique_with_full_lifecycle` | Topics are unique per workspace with create/list/update/delete and cross-workspace isolation. |
| NV-046 | `test_nv046_only_subscriptions_matching_payload_conditions_and_context_fan_out` | Only subscriptions matching payload conditions and context scope enter the fan-out. |

## Decision record

- NV-042 and NV-089 are recorded as `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION`: the acceptance criteria are met and tested, but the source transport/mechanism is not reproduced.
- No provider delivery, push delivery or WebSocket service is claimed. Counts, catalogues and message records describe local state truthfully.
