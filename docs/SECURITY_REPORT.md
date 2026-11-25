# Security report

Checkpoint: 2026-11-22. This describes verified design and known gaps, not a
finished audit.

## Verified controls

- **Identity is server-side.** `get_principal()` resolves the user from a
  hashed, server-stored access token and an active workspace membership.
  Client-supplied `user_id` values are never accepted as proof of identity.
- **Workspace isolation.** Every authenticated endpoint calls
  `verify_workspace()` and filters rows by `workspace_id`. Session tokens carry
  exactly one active workspace; switching workspaces requires a fresh login or
  accepting an invitation.
- **Passwords.** bcrypt with per-password salt and SHA-256 pre-hashing to avoid
  bcrypt's 72-byte truncation. Only the hash is stored.
- **Tokens.** Random 256-bit tokens stored only as SHA-256 hashes. Access tokens
  expire in 1 hour, refresh tokens in 14 days. Refresh rotation replaces both;
  logout and password change revoke sessions. Password-reset revokes all sessions.
- **RBAC.** Seven workspace-scoped roles: owner, admin, sales_manager,
  sales_rep, marketing, support, read_only. Permissions are checked in the
  dependency layer, not trusted from the UI.
- **External actions.** There is no send endpoint. Outreach approval only
  changes a local status and writes an audit event. No email, SMS or webhook is
  sent from the core service.
- **Audit.** The event log is append-only, workspace-scoped, carries actor id,
  correlation id and idempotency key. No update/delete route exists.
- **Input validation.** Pydantic models forbid extra fields; duplicates and
  invalid roles/emails are rejected with 409/422.

## Verified tests

`tests/test_workflow.py` covers unauthorized access, expired/revoked tokens,
refresh rotation, cross-workspace denial, read-only escalation attempts,
IDOR-style access, duplicate rejection and delete safeguards.
`tests/test_adversarial.py` adds adversarial cases; module and integration suites
cover every registered router. The final full suite returned
**99 passed, 1 upstream warning** (see `TEST_RESULTS.md`).

On 2026-11-22 the four earlier fixes were independently reverified with
regression tests: blank/whitespace workspace names, malformed/whitespace emails
with case normalisation, `owner_id` restricted to active same-workspace members,
and a single shared `verify_workspace()` helper used by all scoped routes.
Cross-workspace reads and writes are denied for every scoped resource, including
module routes. No new security defect was found in that checkpoint.

Defects found by the adversarial review and fixed:

- Blank workspace name accepted at first-run bootstrap — now rejected with 422.
- Email validator accepted internal whitespace — now rejected.
- `create_company`, `create_lead`, `create_task`, `update_lead` and `update_task`
  accepted a body-supplied `owner_id` from outside the workspace — now validated
  against active workspace membership.
- `main.py` kept a private duplicate of the workspace check; it now uses the
  single shared `verify_workspace()` dependency helper.

## Known gaps (do not treat as secure until closed)

- No rate limiting or lockout on login, registration or password reset.
- Email ownership is not verified at registration; the verification token
  flow exists but no delivery adapter is configured.
- Invitation tokens are returned to the inviter because no mail adapter exists;
  the invitee cannot receive them automatically yet.
- CSRF protection is not needed for pure Bearer-token APIs, but a future
  cookie-based frontend session would require it.
- Dependency vulnerability scanning and secret scanning have not been run.
- PostgreSQL RLS is not configured; isolation currently relies on ORM query
  filters. Every new query must keep the `workspace_id` predicate.
- `NOVARA_DEV_MODE` can expose one-time tokens in API responses. It must stay
  off outside local development.
- The original public commit `678a13f` contains machine-specific details in
  history. Rewriting history was not authorised and was not done.

## Required before any networked deployment

Close the gaps above, complete the adversarial suite, add rate limiting, run
dependency/secret scans, and verify backups and restore on PostgreSQL.
