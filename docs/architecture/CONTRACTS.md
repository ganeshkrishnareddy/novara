# NOVARA shared contracts (implementation slice 0.1)

This document describes what is actually implemented in `apps/api/novara_core`,
not a future roadmap. It is the contract every later module must obey so NOVARA
stays one product rather than ten applications behind one navigation bar.

## The four shared primitives

| Primitive | Table / module | Rule |
|---|---|---|
| Workspace | `workspaces` | The tenant boundary. Every owned row carries `workspace_id`; queries filter on it. |
| Customer identity | `contacts` | Exactly one contact row per `(workspace_id, email)`. No module may create its own customer table. |
| Event spine | `events` via `events.publish_event()` | Append-only. All modules emit through this function; nothing updates or deletes an event. |
| Audit log | `GET /workspaces/{id}/events` | The same event table, exposed for review. Consequential actions are always events. |

## Event envelope (schema version 1)

Every event stores:

- `seq` — monotonic sequence, gives the log a stable order.
- `id` — UUID, the public identifier.
- `event_type` — one of the values in `novara_core.events.EVENT_TYPES`.
- `occurred_at` — UTC timestamp.
- `workspace_id` — tenant boundary.
- `entity_id` — the primary record the event is about.
- `correlation_id` — shared by every event in one workflow run. This is what makes a customer timeline show records from several modules.
- `schema_version` — currently 1.
- `idempotency_key` — unique per workspace; a repeat returns the original event instead of appending another.
- `payload` — module-specific JSON.

Event types implemented so far: `contact.identified`, `contact.updated`,
`task.created`, `notification.created`, `outreach.draft_created`,
`outreach.approved`.

## Implemented workflow: website form to connected records

`workflow.handle_website_form()` performs, in one transaction:

1. Validate and normalise the submission email.
2. Find or create the single `Contact` for that workspace and email. A repeated
   `submission_id` short-circuits the whole workflow (idempotency).
3. Create a follow-up `Task` linked to the contact.
4. Create an in-app `Notification` for a valid user of that workspace.
5. Create an `OutreachDraft` with status `draft`.
6. Emit four events with one shared `correlation_id`.

The customer timeline endpoint follows that correlation id, so it returns the
contact, task, notification and draft events together. This is the beginning of
the "one customer, one timeline" behaviour in the founder vision.

## Approval and external action boundary

- `approve_outreach_draft()` requires an existing `User` in the same workspace
  whose role is `admin` or `sales_manager`. Other roles get `PermissionError`.
- Approval writes `OUTREACH_APPROVED` to the audit log with the actor id and role.
- **No code in this service sends email, posts publicly, or performs a
  destructive action.** There is no send endpoint. `OutreachDraft.status` values
  are `draft` and `approved` only. A delivery adapter will need its own
  authorisation and audit event before it can be added.

## Storage

SQLite is the local-first development store. SQLAlchemy 2.x mapped classes are
the contract, so PostgreSQL can replace the engine without changing modules.
`set NOVARA_DB_PATH` to relocate the development database.

## Run and verify

From `apps/api`:

```
python -m pytest -q tests
python -m uvicorn novara_core.main:app --reload
```

Interactive API documentation is served at `/docs` by FastAPI.

## Deliberately not implemented yet

- Real authentication and session management. Role checks currently trust the
  stored user id supplied by the caller; this must be replaced with an
  authenticated actor before any networked deployment.
- PostgreSQL, migrations, backup/restore, multi-process event sequencing.
- The other nine capability areas. There are no other modules in this slice.
- Any desktop/mobile installer or cross-platform packaging.
- Any external integration, AI model call, or paid service.

These are stated as gaps, not hidden. No test or document claims they work.
