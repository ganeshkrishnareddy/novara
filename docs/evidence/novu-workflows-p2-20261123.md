# Evidence — Novu-compatible notification workflow P2 cluster (T-086)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Twenty-four named tests were added or extended for this cluster: 16 acceptance
tests in `apps/api/tests/test_notification_workflows_p2.py` and one static UI
wiring guard added to the existing 21-guard `apps/api/tests/test_ui_wiring.py`
module (38 targeted tests pass together). No app code is mocked and no external
provider, SDK or network destination is contacted.

The implementation is a clean-room module,
`apps/api/novara_core/modules/notification_workflows.py`, registered in
`modules/__init__.py`. It owns seven additive workspace-scoped tables created by
Alembic revision `c4d5e6f7a8b1` (down revision `b3c4d5e6f7a9`). NV-071 is
verified against the pre-existing hashed/rotating `api_keys` module rather than
a duplicate implementation.

## Delivery boundary (important)

NOVARA does not perform real email, push, SMS, webhook or external HTTP
delivery in this cluster. "Trigger", "digest" and "webhook dispatch" persist
workspace-scoped records and audit events. The signed webhook delivery is a
one-time secret returned with the record; only its SHA-256 hash is stored. The
local `/webhooks/verify` route proves raw-body HMAC verification, tamper
rejection and nonce replay rejection. No claim of a real external send is made.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| NV-006 | `test_nv006_one_stable_workflow_api` | One documented stable API (`/api-contract`, version 1, empty legacy list), real workflow CRUD, 409 on duplicate key, 422 on invalid channel. |
| NV-013 | `test_nv013_digest_fires_once_per_window_even_with_many_or_zero_events` | Three triggers in one window fold into exactly one digest with `event_count == 3`; re-evaluating the same window returns the same id; an empty window still creates one digest. |
| NV-017 | `test_nv017_templates_instantiate_real_workflows` | Four provenance-bearing clean-room templates; instantiating creates real workflow rows with severity/critical/digest fields; audit event carries `channel_delivery_claimed: false`. |
| NV-019 | `test_nv019_critical_flows_cannot_be_muted_by_preference` | Critical workflow stays enabled with `source=critical-policy` when subscriber disabled; `subscriber_preference` disable returns 409; admin policy reason succeeds; non-critical flows respect the preference. |
| NV-028 | `test_nv028_trigger_overrides_are_scoped_and_cannot_inject_secrets` | Per-run provider/header/payload overrides are recorded on the message only; workflow unchanged; credential-like header and unknown provider return 422. |
| NV-036 | `test_nv036_inbox_tabs_and_filters_use_stored_fields` | Tag, category and unread filters return only matching persisted messages; mark-read changes the unread count. |
| NV-038 | `test_nv038_quiet_hours_hold_or_skip` | Stored weekly window with `hold`/`skip` policy; outside window produces `held` or `skipped`, inside window produces `delivered`. |
| NV-040 | `test_nv040_rich_content_is_sanitised_and_custom_fields_render` | `<script>`, `onclick` and `<iframe>` are removed while allow-listed `<b>` survives; custom `data` fields are stored. |
| NV-044 | `test_nv044_notification_actions_only_open_authorised_local_routes` | An approved `#/contacts/123` action returns an authorised route and audit event; external, `javascript:`, traversal and protocol-relative routes are rejected at creation. |
| NV-054 | `test_nv054_webhook_endpoints_registry_and_ssrf_controls` | Local-only endpoint registry (relative `/api/` path or loopback host), duplicate rejection, 422 for external/hostile URLs, HMAC-signed delivery record with one-time secret returned once and never stored. |
| NV-056 | `test_nv056_signature_tamper_replay_and_failed_recovery` | Valid signature verifies; tampered raw body fails; repeated nonce rejected as replay; failed delivery replayed once with an audit record and a second replay returns 409. |
| NV-071 | `test_nv071_api_keys_are_hashed_rotated_and_revoked` | Only SHA-256 hash stored; X-API-Key authenticates; rotation immediately invalidates the old secret; revocation invalidates the new one. |
| NV-073 | `test_nv073_contexts_isolate_inbox_and_preference_state` | Two context keys isolate messages and summary counts for the same user. |
| NV-086 | `test_nv086_feeds_isolate_stored_messages` | Two feeds assigned to two workflows; feed-filtered message queries return only that feed; duplicate feed key returns 409. |
| NV-087 | `test_nv087_layouts_render_without_script_injection` | Layout stored with sanitised markup; selected on a workflow; preview substitutes `{{content}}` and removes script/onerror attributes. |
| Cross-workspace | `test_notification_workflows_workspace_isolation` | A second workspace sees no workflows, messages or feeds and cannot trigger the first workspace's workflow. |
| UI | `test_notification_workflow_route_controls_are_rendered_and_dispatched` | The `notification-workflows` Operations route renders real API data and every rendered control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_notification_workflows_p2.py` → **16 passed**.
- `pytest apps/api/tests/test_notification_workflows_p2.py apps/api/tests/test_ui_wiring.py` → **38 passed, 1 warning**.
- `pytest apps/api/tests -q --disable-warnings` → **545 passed, 2 warnings in 292.19s** (baseline 528; +16 acceptance +1 UI guard).
- `node --check apps/web/app.js` → exit 0.
- `alembic heads` → single head `c4d5e6f7a8b1`.

## Not claimed

No real provider delivery, push token, external webhook host, third-party SDK,
MCP server, code-first bridge, agent tooling, AI adapters, multi-region
infrastructure or Novu-hosted feature is claimed. Rows outside this cluster
remain in their existing matrix states.
