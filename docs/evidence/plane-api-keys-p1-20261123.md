# Plane API keys and token scoping — P1 evidence (2026-11-23)

Clean-room NOVARA implementation. No secret, token hash or credential is printed
in this document or in test output. No external service is contacted.

## Rows and named tests

| Master ID | Feature | Named acceptance test |
|---|---|---|
| PL-045 | API keys / personal access tokens | `test_api_keys_p1.py::test_pl045_api_key_authenticates_and_secret_is_not_stored`, `::test_pl045_expired_and_revoked_keys_fail_closed`, `::test_pl045_rotation_invalidates_old_secret`, `::test_pl045_key_cannot_escalate_or_cross_workspace` |
| PL-070 | API token permission scoping | `test_api_keys_p1.py::test_pl070_read_scoped_key_is_denied_write_and_allows_read` |

## Commands and results (backend)

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_api_keys_p1.py apps/api/tests/test_security.py apps/api/tests/test_document_security_p1.py -q --disable-warnings
# 15 passed, 1 warning in 6.40s

.venv\Scripts\python.exe scripts/migration_roundtrip_check.py c9f7e1b3a5d2
# ROUND TRIP PASS: upgrade -> downgrade -> upgrade, existing data preserved
```

Full-suite and UI results are recorded in `docs/NOVARA_AUTONOMOUS_EXECUTION.md`
after the current P1 cycle merges.

## What the tests prove

- A real `X-API-Key` header authenticates through the shared FastAPI
  dependency. The row stores only `SHA-256(secret)` plus a short prefix; the
  plaintext is never stored, listed, returned by the detail route, or printed.
  `last_used_at` is updated on real use.
- Scopes are explicit permission strings. A `contact:read` key can read contacts
  but a write returns `403 permission required: contact:write`; a `contact:write`
  key can create but cannot read. Wildcard `*`, duplicate scopes, unknown scopes
  and scopes not held by the caller are rejected.
- Key management (create/list/rotate/revoke) is bearer-only. A key holding
  `workspace:manage` still cannot mint, rotate or revoke another key.
- Expired, revoked and unknown keys all fail closed with `401 invalid or expired
  API key`. Rotation replaces the hash, immediately invalidates the old secret,
  accepts the new one and records `api_key.created` / `api_key.rotated` audit
  events.
- A key is bound to its workspace: using it on another workspace's routes
  returns `403 cross-workspace access is denied`.

## Migration

`apps/api/migrations/versions/d4e6f8a0b2c1_api_keys_p1.py` adds the `api_keys`
table idempotently on top of `c9f7e1b3a5d2`, with a unique `(workspace_id,
prefix)` constraint and indexes for workspace lookup.

## Honest limitations

- Secret hashing is SHA-256 over the high-entropy generated token; it is not a
  slow password KDF. That is appropriate here because the secret is random and
  never user-chosen.
- Expiry is checked on every request against UTC-normalised timestamps to
  survive SQLite's naive DATETIME round trip.
## Settings UI

`apps/web/app.js` now lists workspace API keys (name, prefix, scopes, expiry,
revocation), gates the panel on `workspace:manage`, and binds issue, rotate and
revoke to the real endpoints. Creation and rotation reveal the secret exactly
once in a read-only dialog; listing never returns it. `test_api_keys_ui_p1.py`
proves the real issue → rotate → revoke lifecycle with old/new secret checks and
asserts each UI marker is bound exactly once.

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_api_keys_ui_p1.py apps/api/tests/test_api_keys_p1.py apps/api/tests/test_ui_wiring.py apps/api/tests/test_plane_support_ui_p1.py -q --disable-warnings
# 27 passed, 1 warning in 5.98s

node --check apps/web/app.js
# exit 0
```
