# Evidence — local experimentation delivery P2 cluster (T-092)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Nine named acceptance tests were added in
`apps/api/tests/test_experiment_delivery_p2.py` and one static UI wiring guard
in `apps/api/tests/test_ui_wiring.py`. Every test drives the real FastAPI app
against real persisted, workspace-scoped rows. No app code is mocked.

The clean-room module `apps/api/novara_core/modules/experiment_delivery.py`
owns seven additive workspace-scoped tables created by Alembic revision
`c2d3e4f5a7b8` (down revision `b1c2d3e4f5a7`). It records webhooks, notifier
messages, local cache entries/purges, local proxy snapshots and local refresh
jobs, and recomputes refresh results from NOVARA's own experiment-statistics
and time-series tables.

## Delivery boundary (important)

No outbound webhook, Slack message, CDN API, external proxy fetch or external
scheduler is contacted. All "delivery" is a local, audited record with an
explicit `external_* = false` or `*_local` status returned to the caller.
No GrowthBook source is copied. Rows here verify NOVARA's own local adapter,
not source-equivalence with a hosted platform.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| GB-071 | `test_gb071_event_webhooks_record_local_deliveries` | Event webhooks subscribe to a type, reject duplicate keys/unknown scopes/unsubscribed events and record local deliveries with audit events. |
| GB-072 | `test_gb072_sdk_webhooks_record_payload_change` | SDK-scope webhooks record one local delivery for a payload change. |
| GB-073 | `test_gb073_global_sdk_webhooks_record_any_payload_change` | Global SDK webhooks record each payload change without an event filter. |
| GB-074 | `test_gb074_slack_compatible_notifier_records_without_sending` | Slack-style messages are local drafts/records; a URL field is rejected with 422 and recorded state explicitly reports no external delivery. |
| GB-075 | `test_gb075_cdn_cache_purge_records_local_invalidation` | Local cache entries are stored and versioned, then purged by prefix with a counted, audited local record; no CDN call is made. |
| GB-076 | `test_gb076_self_hosted_proxy_serves_local_and_stale_snapshots` | The proxy serves stored payloads and stale-if-error snapshots locally; a strict snapshot returns 503 on simulated upstream error, with no external fetch. |
| GB-081 | `test_gb081_agenda_style_local_refresh_queue` | Refresh jobs are durable, validated (duplicate key 409, unknown type 422) and workspace-scoped. |
| GB-082 | `test_gb082_experiment_result_refresh_uses_local_observations` | An experiment-result refresh recomputes definition/observation counts and variants from NOVARA's own statistics rows. |
| GB-083 | `test_gb083_metric_refresh_uses_local_time_series` | A metric refresh recomputes point counts, metric keys and session totals from stored local time-series rows. |
| Isolation | `test_experiment_delivery_workspace_isolation` | A second workspace cannot read another workspace's rows, cannot emit its webhooks or serve its proxy snapshots (404), and its purge cannot touch the first workspace's cache. |
| UI | `test_experiment_delivery_route_controls_are_rendered_and_dispatched` | The `experiment-delivery` Operations route renders the local contract, webhooks, notifier/cache/proxy/job counts; every control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_experiment_delivery_p2.py` -> **10 passed, 1 warning**.
- `pytest apps/api/tests/test_experiment_delivery_p2.py apps/api/tests/test_ui_wiring.py`
  -> **38 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `c2d3e4f5a7b8`.
- `scripts/migration_roundtrip_check.py b1c2d3e4f5a7` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md`.

## Not claimed

No GrowthBook-hosted feature, external webhook endpoint, Slack workspace, CDN,
external proxy, hosted scheduler, warehouse data source, third-party SDK, MCP
server, agent tooling or AI adapter is claimed. Rows outside this cluster remain
in their existing matrix states.
