# Evidence — clean-room experiment exposure trackers (T-099)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Nineteen named acceptance tests were added in
`apps/api/tests/test_experiment_exposure_p3.py` (one per GB row plus
idempotency/rejection, batch accounting, custom field mapping, configuration
validation and workspace isolation) and one static UI wiring guard in
`apps/api/tests/test_ui_wiring.py`. Every test drives the real FastAPI app with
real persisted, workspace-scoped rows. `socket.socket.connect` is patched to
raise during each provider test, so any attempted outbound traffic fails the
test. No app code is mocked.

The clean-room module `apps/api/novara_core/modules/experiment_exposure.py`
owns five additive workspace-scoped tables created by Alembic revision
`d9e1f2a3b4c5` (down revision `c8d0e1f2a3b4`): `exposure_trackers`,
`exposure_field_mappings`, `normalized_exposures`, `exposure_rejections` and
`exposure_batches`. It is entirely additive.

## Delivery boundary (important)

GrowthBook is MIT for its core; nothing was copied. For each provider the
module records only the documented *field vocabulary* (event field, accepted
exposure event names, subject/property/experiment/variation paths) and maps a
caller-supplied payload into one normalised local exposure row. There is no
vendor SDK, browser snippet, hosted endpoint, webhook receiver, outbound HTTP
or upstream source. The API contract reports `external_calls: false`,
`external_delivery: false`, `vendor_sdk_used: false` and
`generated_by: local-adapter`. Deduplication keys are derived deterministically
from the normalised subject/experiment/variation plus the payload, so retries
collapse without a stored coordination service. Invalid payloads are appended
to a local rejection log rather than silently dropped.

## Row-by-row evidence

Each row has its own named test, calling the shared offline helper with that
provider's key and independently recorded field expectations.

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| GB-134 | `test_gb134_amplitude_exposure_maps_to_local_event_spine` | `$exposure` / `event_properties` / `user_id` payload normalises locally and publishes `experiment.exposure_recorded`. |
| GB-135 | `test_gb135_clevertap_exposure_maps_to_local_event_spine` | `Experiment Viewed` / `properties` / `identity` payload normalises locally. |
| GB-136 | `test_gb136_custom_exposure_maps_to_local_event_spine` plus `test_custom_mapping_overrides_documented_field_paths` | Caller-written plain payload normalises; custom dotted-path mappings override subject/experiment/variation with validation. |
| GB-137 | `test_gb137_firebase_exposure_maps_to_local_event_spine` | `event` / `params` / `app_instance_id` payload normalises locally. |
| GB-138 | `test_gb138_freshpaint_exposure_maps_to_local_event_spine` | `event` / `properties` / `anonymous_id` payload normalises locally. |
| GB-139 | `test_gb139_fullstory_exposure_maps_to_local_event_spine` | `event` / `properties` / `user_id` payload normalises locally. |
| GB-140 | `test_gb140_heap_exposure_maps_to_local_event_spine` | `event` / `properties` / `identity` payload normalises locally. |
| GB-141 | `test_gb141_jitsu_exposure_maps_to_local_event_spine` | `event` / `props` / `user_id` payload normalises locally. |
| GB-142 | `test_gb142_keenio_exposure_maps_to_local_event_spine` | Nested `event_name` / `keen.properties` / `keen.id` payload normalises locally. |
| GB-143 | `test_gb143_langfuse_exposure_maps_to_local_event_spine` | `name` / `metadata` / `user_id` payload normalises locally. |
| GB-144 | `test_gb144_mparticle_exposure_maps_to_local_event_spine` | `event` / `attributes` / `user_id` payload normalises locally. |
| GB-145 | `test_gb145_arizephoenix_exposure_maps_to_local_event_spine` | `event` / `attributes` / `session_id` payload normalises locally. |
| GB-146 | `test_gb146_segment_exposure_maps_to_local_event_spine` | `Experiment Viewed` / `properties` / `userId` payload normalises locally. |
| GB-147 | `test_gb147_snowplow_exposure_maps_to_local_event_spine` | `event` / `properties` / `domain_userid` payload normalises locally. |
| Robustness | `test_exposure_retries_are_idempotent_and_invalid_payloads_are_rejected` | Replays return `duplicate` without a second row; non-exposure payloads are rejected with 422 and a logged reason. |
| Robustness | `test_exposure_batch_counts_accepted_duplicate_and_rejected` | A four-item batch yields 2 accepted / 1 duplicate / 1 rejected with a durable summary batch row. |
| Robustness | `test_tracker_configuration_is_validated_and_can_be_disabled` | Unknown providers fail 422, duplicates 409, disabled trackers reject ingestion, and unknown ids fail 404. |
| Isolation | `test_exposure_adapters_are_workspace_isolated` | A second workspace sees no trackers/exposures/rejections/stats and cannot ingest through or mutate another workspace's tracker. |
| UI | `test_exposure_route_controls_are_rendered_and_dispatched` | The `experiment-exposure` Operations route renders all 14 provider paths, tracker config, mappings, ingestion, batches and rejections; every control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_experiment_exposure_p3.py` -> **19 passed, 1 warning**.
- `pytest apps/api/tests/test_experiment_exposure_p3.py apps/api/tests/test_ui_wiring.py`
  -> **54 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `d9e1f2a3b4c5`.
- `scripts/migration_roundtrip_check.py c8d0e1f2a3b4` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md`.

## Not claimed

No GrowthBook source, vendor SDK, browser snippet, hosted API, webhook
receiver, outbound HTTP, real analytics destination or exposure delivery is
claimed. Other GrowthBook rows remain in their existing matrix states.
