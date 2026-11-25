# Phase 4 browser verification — 2026-11-22

Local server: `uvicorn novara_core.main:app` on `127.0.0.1:8000`, started from `D:\NOVARA` with the project virtualenv. Signed-in browser session reused from the earlier Phase 3 E2E run; no new credentials or external services were used.

## Universal Search

1. Global search box filled with `E2E`. Dropdown rendered four typed results from the real `/api/v1/workspaces/{id}/search?q=E2E` API: Contact `E2E Acceptance`, Lead `E2E Acceptance`, Task `Qualify lead: E2E Acceptance`, Outreach draft `Following up, E2E Acceptance`. Previously this dropdown only queried contacts plus in-session caches.
2. "Open universal search" navigated to `#/search`. Page showed `4 matches for "E2E"` in a typed table (Record / Type / Detail).
3. Result-type filter changed to `Leads`; the table reduced to the single Lead row. Filter is client-side over the API response; no extra request was made.

## Customer Inbox

1. Navigation to `#/inbox` rendered an empty-state screen with "0 active of 0 tickets." and a governance note: "Tickets and replies stay in this workspace. No email or message is sent by this build."
2. "New ticket" opened a dialog with Subject, Details, Linked contact and Priority. Created `Browser verification ticket` linked to `E2E Acceptance`, priority `High`.
3. The app navigated to the ticket detail, showing the linked contact and a conversation area.
4. Added reply `Internal note: verified in browser. No external message sent.` — it appeared in the conversation thread.
5. Changed status to `Pending`; the action buttons switched to `Open / Resolved / Closed`.
6. Returned to the inbox: `1 active of 1 tickets.` with a row showing the subject, linked contact, `High` priority and `Pending` status.

## Scope note

All records were created in the local SQLite workspace only. No email, SMS, chat message or public post was created. Browser evidence is local and does not imply Docker, PostgreSQL or production verification.
