# Evidence — final P0 marketing/support/notification gaps (2026-11-23)

## Scope

The last eleven locally actionable P0 rows were promoted to VERIFIED_COMPLETE
by `apps/api/tests/test_p0_marketing_support_notify_gaps.py` (11 named tests,
all passing). All backend tests drive the real FastAPI app through the shared
`client` fixture; the two UI rows assert the actual SPA source.

Two genuine defects were found and fixed while writing these tests:

1. `@router.get("/{campaign_id}")` was declared before the literal collection
   routes, so `/campaigns/segments` and `/campaigns/email-templates` were
   captured as a campaign id. `marketing.py` now sorts its routes so literal
   paths win, regardless of declaration order.
2. Layered notification preferences were stored but had no resolver. A real
   `POST /notification-preferences/resolve` endpoint now computes the effective
   state (channel > workflow > global > default) and returns every candidate
   layer so the decision is inspectable.

## Row-to-test mapping

| Row | Named test | What is proven |
| --- | --- | --- |
| MT-008 | `test_mt008_segments_are_static_or_dynamic_and_membership_is_real` | explicit static membership and criteria-driven dynamic refresh both produce real member rows |
| MT-012 | `test_mt012_template_emails_are_stored_and_render_safely` | template stored/listed; token rendering substitutes values and HTML-escapes hostile input |
| MT-013 | `test_mt013_segment_broadcast_sends_once_per_consented_recipient` | broadcast bound to a segment, one recipient queued and dispatched once, status recorded as sent |
| MT-026 | `test_mt026_campaign_types_and_scheduling_are_validated_and_due` | time/event campaign validation, schedule persistence and real `due` activation |
| MT-027 | `test_mt027_campaign_builder_canvas_wires_conditions_decisions_and_actions` | SPA exposes action/condition/decision steps, local event actions, rule config and a wired add handler |
| MT-028 | `test_mt028_campaign_contact_sources_enroll_once_from_segment_and_form` | a combined campaign enrolls the right contact from segment/form sources and does not duplicate on re-run |
| CW-019 | `test_cw019_private_notes_are_internal_only` | internal note is readable by agents and absent from the public message stream |
| CW-030 | `test_cw030_conversation_search_matches_subject_body_and_messages` | search matches ticket subject, body and message content and excludes absent terms |
| NV-007 | `test_nv007_workflow_channel_steps_persist_results_without_delivery` | five channel steps (email/SMS/push/in-app/chat) persist a `queued` result; no delivery is claimed |
| NV-032 | `test_nv032_layered_preferences_resolve_global_workflow_and_channel` | global/workflow/channel rows resolve with correct precedence and a default fallback |
| NV-039 | `test_nv039_inbox_preferences_view_is_routed_and_wired` | notification inbox exposes a preferences dialog driven by the real preference API with a wired save form |

## Verification

- Targeted: 11 passed.
- `node --check apps/web/app.js`: exit 0.
- Full API suite after integration: 448 passed, 2 warnings (upstream
  Starlette/httpx deprecation only).

## Honest limits

Channel steps record local *intents* (`queued`) through registered local
adapters; they are not provider deliveries. The campaign builder is a local
step list with conditions/decisions/actions, not a third-party drag-and-drop
SaaS canvas. Notification preferences are applied by the local resolver; no
external notification provider reads them.
