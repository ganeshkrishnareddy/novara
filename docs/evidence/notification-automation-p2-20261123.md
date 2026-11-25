# Evidence — clean-room notification automation P2 cluster (T-096)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Ten named acceptance tests were added in
`apps/api/tests/test_notification_automation_p2.py` (nine feature rows plus one
workspace-isolation test) and one static UI wiring guard in
`apps/api/tests/test_ui_wiring.py`. Every test drives the real FastAPI app
against real persisted, workspace-scoped rows. No app code is mocked.

The clean-room module `apps/api/novara_core/modules/notification_automation.py`
owns ten additive workspace-scoped tables created by Alembic revision
`a6b8c9d0e1f2` (down revision `f5a7b8c9d0e1`). It extends NOVARA's existing
notification-workflows engine with a local subscriber registry, sandboxed code
steps, local-stub HTTP steps, provider routing, demo providers with quotas,
hashed channel endpoints, documented platform limits, authorised broadcast and
workspace feature flags.

## Delivery boundary (important)

These Novu rows are MIT-core patterns and were implemented clean-room: no Novu
source was copied. There is no outbound HTTP, no real email/SMS/push delivery
and no hosted provider. HTTP steps resolve only against registered `/local/`
stub records (`external_calls: false`); demo sends persist `simulated` local
rows; broadcasts create `delivered_local` in-app records only
(`external_delivery: false`). Channel secrets are stored as SHA-256 hashes and
never returned; endpoint values are masked in every response. Code steps run
in a whitelisted-AST expression sandbox (no `exec`/`eval`, no imports, no
dunder access, fixed function set), never arbitrary native code.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| NV-009 | `test_nv009_code_steps_are_sandboxed_versioned_and_published` | Code steps compile in a restricted sandbox, version on update, gate evaluation on publish, and reject imports, file access and dunder traversal. |
| NV-015 | `test_nv015_http_steps_resolve_only_registered_local_stubs` | HTTP steps require explicit authorisation (403 otherwise), reject outbound URLs (422), fail without a registered stub (422) and return the local stub response with `external_calls: false`. |
| NV-026 | `test_nv026_routing_selects_primary_and_fallback_chain` | Routing selects a provider by subscriber/context/data conditions with priority ordering, returns the fallback chain and defaults to `in_app`; unknown providers are rejected. |
| NV-027 | `test_nv027_demo_providers_enforce_their_daily_quotas` | Demo SMS sends are simulated locally, stop at the documented daily quota (429) and report usage/remaining with `real_delivery: false`. |
| NV-031 | `test_nv031_channel_endpoints_store_hashed_secrets_only` | Push/SMS/chat/email endpoints persist per subscriber; secrets are hashed, raw values never appear in responses, duplicates and invalid channels are rejected, removal works. |
| NV-103 | `test_nv103_platform_quotas_are_documented_and_enforced` | Documented caps are workspace-scoped and overridable (workspace-manage only); bulk-create and payload-size caps are enforced; unknown caps are rejected. |
| NV-104 | `test_nv104_broadcast_requires_flag_and_explicit_authorisation` | Broadcast is feature-flag gated (409), requires explicit authorisation (403), rejects empty audiences (422) and delivers local records to every subscriber. |
| NV-107 | `test_nv107_subscriber_search_and_bulk_create` | Subscribers are searchable across key/email/name; bulk create accepts up to 500, rejects duplicates in-request (422) and existing keys (409), and enforces the 501 limit. |
| NV-118 | `test_nv118_feature_flags_gate_experimental_features` | Flags expose env-style defaults, toggle per workspace, gate experimental routes (409 when disabled) and reject unknown flags (404). |
| Isolation | `test_notification_automation_workspace_isolation` | A second workspace cannot list or address this workspace's subscribers, endpoints, code steps, routing rules or deliveries; cross-workspace flag writes fail closed with 403. |
| UI | `test_notification_automation_route_controls_are_rendered_and_dispatched` | The `notification-automation` Operations route renders quotas, flags, subscribers, code steps, HTTP stubs, routing, demo providers and broadcast; every control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_notification_automation_p2.py` -> **10 passed, 1 warning**.
- `pytest apps/api/tests/test_notification_automation_p2.py apps/api/tests/test_ui_wiring.py`
  -> **42 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `a6b8c9d0e1f2`.
- `scripts/migration_roundtrip_check.py f5a7b8c9d0e1` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md`.

## Not claimed

No Novu-hosted feature, server SDK, client SDK, CLI, MCP server, agent
toolkit, web chat channel, S3 storage, inbound email parse, real push/SMS/email
delivery or outbound HTTP is claimed. Rows outside this cluster remain in
their existing matrix states.