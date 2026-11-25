# Papermark document security and hardening — P1 evidence (2026-11-23)

All work is clean-room NOVARA code. No Papermark source was copied, no external
service was contacted and no secrets were printed. The only socket opened by a
test is the loopback HTTP server used to prove webhook signature verification.

## Rows closed

| Master ID | Feature | Named acceptance test |
|---|---|---|
| PM-040 | Document password encryption key | `test_document_security_p1.py::test_pm040_secret_vault_hides_plaintext_and_rotates_named_key` |
| PM-045 | Dynamic watermarking | `test_document_security_p1.py::test_pm045_watermark_overlay_is_per_viewer_attributed_and_escaped` |
| PM-117 | Signed outgoing webhooks | `test_document_security_p1.py::test_pm117_document_shared_webhook_reaches_loopback_subscriber_and_verifies` |
| PM-123 | Jobs API group | `test_document_api_hardening_p1.py::test_pm123_document_job_enqueued_executed_and_audited` |
| PM-141 | OpenAPI generation and published spec | `test_document_api_hardening_p1.py::test_pm141_published_openapi_spec_matches_real_document_routes` |
| PM-146 | API rate limits and error envelope | `test_document_api_hardening_p1.py::test_pm146_document_rate_limit_returns_canonical_envelope` |
| PM-156 | Encryption in transit and at rest | `test_document_security_p1.py::test_pm156_encrypted_file_bytes_at_rest_and_transport_headers` |

Two additional named tests cover workspace isolation and input validation:
`test_document_security_rows_are_workspace_isolated` and
`test_document_security_validators_reject_extra_fields_and_wrong_events`.

## Commands and results

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_document_security_p1.py apps/api/tests/test_document_api_hardening_p1.py -q --disable-warnings
# 9 passed, 1 warning in 6.95s

.venv\Scripts\python.exe -m pytest apps/api/tests/test_ui_wiring.py apps/api/tests/test_document_security_p1.py apps/api/tests/test_document_api_hardening_p1.py -q --disable-warnings
# 26 passed, 1 warning in 6.11s

node --check apps/web/app.js
# exit 0

.venv\Scripts\python.exe -m py_compile apps/api/novara_core/modules/document_security.py apps/api/novara_core/modules/jobs.py apps/api/novara_core/modules/storage.py apps/api/novara_core/middleware.py apps/api/novara_core/modules/email_campaigns.py apps/api/tests/test_document_security_p1.py apps/api/tests/test_document_api_hardening_p1.py apps/api/migrations/versions/b8f4c2d6e0a3_document_security_p1.py
# exit 0
```

.venv\Scripts\python.exe -m pytest apps/api/tests -q --disable-warnings
# 392 passed, 1 warning in 192.59s

.venv\Scripts\python.exe scripts/migration_roundtrip_check.py b8f4c2d6e0a3
# ROUND TRIP PASS: upgrade -> downgrade -> upgrade, existing data preserved

## What the named tests prove

- **PM-040**: a known document password secret is stored only as a versioned
  authenticated-ciphertext token. The raw DB column and every API response omit
  the plaintext. Promoting a new active key and rotating re-encrypts the row;
  the original value decrypts under the new key, and substituting wrong key
  bytes with the same key id fails closed. Events record storage and rotation.
- **PM-156**: a real PDF byte payload is stored as ciphertext in
  `encrypted_document_blobs`; the plaintext and its identifying marker are
  absent from the stored token. Download restores exact bytes, verifies the
  SHA-256 checksum, sets `Content-Disposition`, and carries the standard
  security headers. A corrupted checksum is rejected.
- **PM-045**: two viewers receive distinct view ids, tokens and watermark
  strings. Each generated SVG overlay contains four tiled, XML-escaped text
  nodes carrying that viewer's identity, view id and UTC timestamp. The other
  viewer's attribution is absent, hostile markup is escaped, and the underlying
  document row is unchanged. The browser preview artifact
  `docs/evidence/watermark-preview-20261123.html` was generated from the real
  overlay endpoint and rendered in Chromium at
  `http://127.0.0.1:8765/watermark-preview-20261123.html`; the browser DOM
  showed the same view id and viewer email on all three page labels. Screenshot:
  `docs/evidence/watermark-preview-20261123.png`.
- **PM-117**: a genuine `document.shared` event reaches a loopback HTTP
  subscriber. `X-NOVARA-Signature` equals the HMAC computed from the signing
  secret, delivery id and raw body; a tampered signature and a wrong secret do
  not verify. A `WebhookDelivery` row records `delivered`, and the audit event
  is persisted. The webhook secret is not returned by the API.
- **PM-123**: a text upload is enqueued through the jobs API as
  `document_conversion`, executed by the registered local handler using the
  existing conversion helper, and audited with `job.queued`, `job.started`,
  `job.completed` and `file.converted`. The converted output downloads with
  the original bytes. The test also queues the same job type in two workspaces
  and proves a workspace-scoped run claims only its own job.
- **PM-141**: the published spec endpoint filters the live `app.openapi()`
  output to real `/documents` and `/storage` paths, preserving referenced
  schemas. The named test compares it with the real application schema and
  rejects fabricated paths.
- **PM-146**: over-limit document requests return HTTP 429 with the canonical
  `RATE_LIMIT_EXCEEDED` envelope, `Retry-After`, rate-limit headers and all
  security headers; non-document endpoints are unaffected. Auth-path limiter
  behaviour remains unchanged.

## UI wiring

`apps/web/app.js` now exposes a permission-gated **Preview watermark** control
on document detail. It creates a real per-view watermark record, fetches the
generated SVG through the authenticated API and displays it repeatedly over
three pages with the attribution string. `test_ui_wiring.py` checks that the
control and form each have exactly one dispatch handler.

## Migration

`apps/api/migrations/versions/b8f4c2d6e0a3_document_security_p1.py` is an
idempotent Alembic revision on former head `a1b2c3d4e5f7` for the three new
tables: `document_secrets`, `encrypted_document_blobs` and `watermark_views`.
Running the round-trip check exposed pre-existing drift (30 module tables added
after the earlier P1 migration), so
`apps/api/migrations/versions/c9f7e1b3a5d2_schema_drift_catch_up_2026_11_23.py`
adds those tables idempotently. `alembic check` is now clean and the full
upgrade → downgrade → upgrade preserves data.

## Honest limitations

- The encryption is clean-room application-level at-rest protection using
  HMAC-SHA256-derived CTR keystream and encrypt-then-MAC; it is not a KMS,
  full-disk encryption or a substitute for TLS at the transport layer. The dev
  key must be replaced in production via `NOVARA_DOCUMENT_ENCRYPTION_KEYS`.
- Rotation is implemented and tested for secrets; encrypted blobs keep their
  original key id until a separate migration is added. Old key ids must remain
  configured while any row still references them.
- The watermark is generated as a tiled SVG overlay for the viewer to apply to
  each displayed page; it is not composited into downloaded PDF bytes.
- Webhook URLs are validated as credential-free HTTP(S) URLs; there is no
  private-network allow-list, so deployments must restrict destinations.
- The browser evidence is a real API-generated preview rendered in Chromium,
  not a full Playwright walkthrough of the entire document workflow.
