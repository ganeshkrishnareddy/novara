# Evidence — clean-room email content and engagement (T-101)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Eleven named acceptance tests were added in
`apps/api/tests/test_email_engagement_p2.py` (one per MT row plus contract,
isolation and permission checks) and one static UI wiring guard in
`apps/api/tests/test_ui_wiring.py`. Every test drives the real FastAPI app with
real persisted, workspace-scoped rows. `socket.socket.connect` is patched to
raise in every test, so any attempted outbound traffic fails the test.

The clean-room module `apps/api/novara_core/modules/email_engagement.py` owns
seven additive workspace-scoped tables created by Alembic revision
`f2b3c4d5e6f7` (down revisions `a1b2c3d4e5f6` and `e0f2a3b4c5d6`). This merge
point also unified a pre-existing two-head divergence in the migration graph,
restoring a single head. No existing table is altered.

## Delivery boundary (important)

This is a clean-room implementation written from each feature's documented
behaviour, not from Mautic's Symfony bundles or upstream source. No Mautic
source, Symfony bundle, hosted service, real email delivery, outbound HTTP,
tracking domain or mail provider is used.

- **Tracking tokens** are opaque locally generated sha256 identifiers. A
  tracking endpoint only records an event when it is called; NOVARA never
  fetches a target URL. Click target URLs are stored as data and returned in
  the local response for the caller to interpret — there is no redirect to an
  external host and no outbound request.
- **Open pixel** is a hard-coded locally generated 1x1 transparent GIF, not
  fetched from any CDN.
- **Bounces/replies** are recorded from caller-supplied local events; no
  mailbox polling or provider webhook receiver is implemented or claimed.
- **Online version** is a deterministic local render assembled from stored
  HTML/text, validated base64 inline images and the caller's signature.
- **A/B selection** is deterministic from an integer bucket and the stored
  weights; no remote experimentation service is contacted.

The API contract reports `version: 1`, `legacy_versions: []`,
`external_calls: false`, `external_delivery: false`, `email_sent: false` and
`vendor_sdk_used: false`.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| MT-014 | `test_mt014_email_html_and_text_formats` | Templates store and return both HTML and plain-text bodies; empty bodies are rejected. |
| MT-015 | `test_mt015_translations_and_ab_variants` | Locale translations are unique per template; weighted A/B variants select deterministically by bucket. |
| MT-017 | `test_mt017_open_tracking_pixel_records_locally` | Open token records a local open event and returns a locally generated 1x1 GIF; token-kind mismatches fail 422. |
| MT-018 | `test_mt018_click_tracking_never_redirects_externally` | Click token records a local click; the target URL is returned as inert data with no outbound request. |
| MT-020 | `test_mt020_bounce_management` | Bounce events carry local reasons/codes and are filterable by kind. |
| MT-021 | `test_mt021_reply_monitoring_is_local_only` | Reply events are recorded locally with no mailbox access. |
| MT-022 | `test_mt022_mailer_identity_and_signatures` | One signature per user is upserted with a default flag. |
| MT-023 | `test_mt023_base64_inline_images_are_validated` | Base64 payloads are decoded and validated, stored by Content-ID, and duplicates/invalid data fail. |
| MT-024 | `test_mt024_online_version_is_a_local_render` | Online render includes HTML, inline image data URIs and the signature, with a sha256 hash. |
| Robustness | `test_email_engagement_contract_and_workspace_isolation` | Contract denies external delivery and a second workspace sees no templates, signatures or engagement rows. |
| Permission | `test_email_engagement_writes_require_contact_write` | Reads use CONTACT_READ; unauthenticated writes are refused. |
| UI | `test_email_engagement_route_controls_are_rendered_and_dispatched` | The `email-engagement` Operations route renders every feature panel; all controls have one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_email_engagement_p2.py` -> **11 passed, 1 warning**.
- `pytest apps/api/tests/test_email_engagement_p2.py apps/api/tests/test_ui_wiring.py`
  -> **48 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `f2b3c4d5e6f7` (merges the previous two heads).
- `scripts/migration_roundtrip_check.py e0f2a3b4c5d6` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md`.

## Not claimed

No Mautic source, Symfony bundle, hosted service, real email send, tracking
domain, mail-provider integration, webhook receiver, mailbox polling or outbound
HTTP is claimed. Other Mautic rows remain in their existing matrix states.
