# Support operations UI — evidence (2026-11-23)

## Scope
Customer inbox (`#/inbox`) now exposes real, workspace-scoped support
configuration that is already served by the local API. No outbound message is
sent; no adapter or external mailbox is contacted.

## Controls
- Inbox and label filters (`ticket-inbox`, `ticket-label`) narrow the loaded
  ticket list; they are backed by `/tickets/inboxes` and `/tickets/labels`.
- Support operations panel: Teams, Inboxes, Labels, Routing rules, Segments,
  Replies & macros, Help centre and Reports. Each opens a modal populated by
  the corresponding real endpoint: `/tickets/teams`, `/tickets/inboxes`,
  `/tickets/labels`, `/tickets/routing-rules`, `/tickets/segments`,
  `/tickets/saved-replies`, `/tickets/macros`, `/tickets/help-portals` and
  `/tickets/reports/overview|conversations|csat`.

## Evidence
- `node --check apps/web/app.js` → exit 0.
- `apps/api/tests/test_ui_wiring.py::test_support_p1_operations_ui_is_routed_and_wired`
  asserts one dispatcher per action, the exact `data-action` markup, the two
  new filters and every API path used by the modals.
- Full UI wiring file: 17 passed, 1 deprecation warning.

## Honest limits
This closes UI routing only. The named backend acceptance tests for the
individual CW rows are a separate batch and are not claimed here.
