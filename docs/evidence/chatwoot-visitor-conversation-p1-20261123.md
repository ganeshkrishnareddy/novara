# CW-035 visitor conversation — named evidence (2026-11-23)

Clean-room NOVARA implementation. No hosted widget, external provider, network
call or fake channel indicator is involved.

| Master ID | Named test | Proved locally |
|---|---|---|
| CW-035 | `test_cw035_visitor_conversation_p1.py::test_cw035_visitor_conversation_appears_in_agent_inbox` | An admin issues a revocable site token bound to one real inbox; a visitor starts a conversation that becomes a genuine open ticket and inbound message in that agent queue; the server fixes the real `web_form` origin and rejects a visitor-supplied channel; follow-up messages append to the same thread; a different site token cannot reach it; revocation closes the entry point while preserving the conversation; all steps publish audited events. |

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_cw035_visitor_conversation_p1.py -q --disable-warnings
# 1 passed, 1 warning in 0.90s

.venv\Scripts\python.exe scripts/migration_roundtrip_check.py f5a7b9c1d2e4
# ROUND TRIP PASS: upgrade -> downgrade -> upgrade, existing data preserved
```

## Implementation surface

- `apps/api/novara_core/modules/visitor_conversations.py` — `VisitorSite` and
  `VisitorConversation` tables; admin site-token create/list/revoke under
  `/api/v1/workspaces/{workspace_id}/visitor-sites`; public start/reply under
  `/api/v1/public/visitor-conversations`.
- The public body schemas use `extra="forbid"`, so a visitor cannot submit an
  `origin_channel`. The server sets `web_form` on both the ticket and every
  message, and the SPA renders `ticket.origin_channel` from stored data.
- A conversation is explicitly bound to the issuing site, so another token —
  even one pointed at the same inbox — cannot append to it.
- Migration `f5a7b9c1d2e4` creates the two tables idempotently on top of the
  project-intake head.

## Honest limitations

- This is a local visitor entry point with a revocable token, not a hosted chat
  widget with browser session tracking, CAPTCHA or abuse protection. Deployments
  must add edge protection and rate limiting for a public internet surface.
- The visitor reuses the workspace contact identity by email; there is no
  anonymous cookie identity across devices.
- No agent reply is sent through an external channel; the agent responds through
  the ordinary local ticket message route.
