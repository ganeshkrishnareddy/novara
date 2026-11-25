# Customer Inbox P0 — implementation evidence (2026-11-22)

Feature IDs: **CW-001, CW-002, CW-003, CW-004, CW-009, CW-011, CW-018** (all P0,
Chatwoot source family). Status: **VERIFIED_COMPLETE against each row's recorded
acceptance criteria.** All work is local and uncommitted; no external message was
sent.

## What changed

| Area | File | Change |
| --- | --- | --- |
| Data | `apps/api/novara_core/modules/support.py` | `support_tickets` gains `origin_channel` and `conversation_type`; `ticket_messages` gains `direction` and `channel`. |
| Events | same file | Added `ticket.assigned` and `ticket.contact_identified` to the event registry. Status-change events now carry an optional validated reason. |
| API | same file | `GET /tickets/counts`, `GET /tickets/stream` (local SSE feed), `POST /tickets/identify`, `GET /tickets/assignees`, `?mine` / `?unassigned` / `?assignee_id` queue filters. Assignment and status changes are audited. |
| Migration | `apps/api/migrations/versions/d5e9b3c2f841_conversation_metadata.py` | Idempotent add of the four new columns; validated upgrade/downgrade/upgrade. |
| UI | `apps/web/app.js` | Live queue counts via streaming fetch, owner filters, assignee selector, origin/type context, message direction/channel badges, pre-chat identity capture, origin/type/direction controls in forms. |
| Contract test | `apps/api/tests/test_phase4_ui_contract.py` | Exact response-shape assertions updated for the four new fields. |

## Named tests

`apps/api/tests/test_support_inbox.py` — 8 named tests, all passing:

1. `test_shared_inbox_is_workspace_scoped_audited_and_local_only` — CW-001:
   contact:read scope, subject/contact/priority/status context, audit events and
   zero campaign/broadcast rows after a reply.
2. `test_conversation_persists_origin_type_and_four_named_events` — CW-002:
   origin and conversation type round trip, four named lifecycle events,
   cross-workspace ID returns 404.
3. `test_public_reply_has_direction_channel_order_and_verified_actor` — CW-003:
   inbound/outbound direction, channel, thread order, verified actor id and
   timestamp; invalid direction/channel rejected.
4. `test_assignment_requires_active_member_and_audits_reassignment` — CW-004:
   active same-workspace member only, 422 for missing/inactive/foreign user,
   assignee list, reassignment and clearing audited.
5. `test_status_transitions_and_reasons_are_validated_and_audited` — CW-009:
   exactly four statuses, invalid values 422, every transition publishes
   `ticket.status_changed` with its reason.
6. `test_priority_persists_filters_and_rejects_unknown_values` — CW-011:
   four priorities persist, filter correctly, unknown value 422, queue counts.
7. `test_pre_chat_identity_reuses_single_crm_contact` — CW-018:
   email upsert reuses one CRM contact, unknown contact ID 422, existing
   conversation count reflects the linked ticket.
8. `test_queue_counts_and_realtime_stream_route_are_registered` — CW-001:
   live aggregates and a real first SSE frame, route present in OpenAPI.

Commands and results:

```
cd D:\NOVARA\apps\api
& ..\..\.venv\Scripts\python.exe -m pytest tests/test_support_inbox.py -q
8 passed, 1 warning in 3.88s

& ..\..\.venv\Scripts\python.exe -m pytest -q -rs
193 passed, 1 warning in 67.10s
```

The warning is Starlette's `httpx` TestClient deprecation notice, not a product failure.
Baseline before this cycle was 184 passed; the eight new named tests and one route-order
regression test are additive and no assertion was weakened.

### Route-order defect found and fixed

A live route probe showed that `GET /tickets/saved-replies`, `/macros`,
`/sla-policies`, `/business-hours`, `/escalation-rules` and `/csat` all returned
404: the dynamic `GET /tickets/{ticket_id}` was registered first and captured
those static names as ticket IDs. The dynamic handler is now registered last, and
`tests/test_support.py::test_static_support_routes_are_not_shadowed_by_ticket_id`
asserts every static route resolves to its own handler with HTTP 200.

## Migration safety

Applied to the development database, which moved from `b4d8c2f1a730` to
`d5e9b3c2f841` with data preserved. On a disposable database the full path was
exercised: upgrade to head, downgrade one revision, upgrade to head again. Final
schema contains `origin_channel`, `conversation_type`, `direction` and `channel`.
Each column is added only when missing, so a local `init_db()` startup cannot make
the revision fail.

## Real server

`docs/evidence/runtime-smoke-20261122.txt` gained a Customer inbox section and was
re-run against a real uvicorn process on a throwaway database:

```
[6] Customer inbox (P0)
  PASS pre-chat identity reuses CRM contact (HTTP 201)
  PASS conversation created with origin metadata (HTTP 201)
  PASS reply stored with direction and channel (HTTP 201)
  PASS queue counts reflect the ticket (HTTP 200)
  PASS assignee list available to agents (HTTP 200)
  PASS inbox stream route registered
```

OpenAPI path count rose from 166 to 170. Response bodies containing tokens are
never logged.

## Design notes

- `GET /tickets/assignees` is scoped to `contact:read` rather than the existing
  `GET /workspaces/{id}/members` endpoint, which requires `member:manage`.
  Agents can therefore assign conversations without gaining member-management
  rights. A second workspace owned by the same person is **not** treated as a
  foreign user: the shared identity model deliberately allows one person to be a
  member of several workspaces.
- `snoozed` is intentionally not implemented. CW-009's recorded criterion
  requires exactly the four values open/pending/resolved/closed; adding a fifth
  would violate it. Reopening is represented by a validated status reason.
- Real-time updates use a streaming `fetch` because the bearer token travels in
  the header; native `EventSource` cannot set headers. The feed polls local
  aggregates and performs no external I/O.
- External channel adapters, real email/WhatsApp delivery, round-robin workload
  rules and priority-based routing are **not** claimed by these rows. They remain
  separately accounted for in the matrix.
