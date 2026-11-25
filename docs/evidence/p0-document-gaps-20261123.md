# Evidence — P0 document/storage gaps (2026-11-23)

## Scope

Fourteen P0 rows were promoted from IMPLEMENTED_UNVERIFIED / PARTIALLY_IMPLEMENTED
to VERIFIED_COMPLETE by a single named acceptance suite:
`apps/api/tests/test_p0_document_gaps.py` (14 tests, all passing against the real
FastAPI app through the shared `client`/`db_session` fixtures). Every assertion
exercises real storage, real link/session rows, real permission checks and real
event writes; no route or figure is mocked.

The implementation lives in `modules/document_links.py`, `modules/storage.py`
and `modules/documents.py`; the additive migration for viewer identities and
link sessions is `a7c3e9f1b5d8`.

## Row-to-test mapping

| Row | Named test | What is proven |
| --- | --- | --- |
| PM-002 | `test_pm002_presigned_upload_url_is_real_and_tamper_proof` | presign issues a signed HMAC-style token/URL; PUT uploads real bytes; tampered token is rejected 403 |
| PM-012 | `test_pm012_pdf_preview_returns_real_extracted_pages` | a real uploaded PDF is parsed and its page count/content returned by the preview route |
| PM-015 | `test_pm015_blob_storage_round_trips_bytes_and_isolates_workspaces` | byte-for-byte round trip, SHA-256 checksum match, cross-workspace download denied |
| PM-028 | `test_pm028_shareable_link_resolves_to_document_metadata` | a random link token resolves to the real document with policy flags |
| PM-029 | `test_pm029_link_management_list_get_patch_and_revoke` | list/get/patch/revoke of a link are persisted and reflected |
| PM-030 | `test_pm030_password_protected_link_unlock_is_enforced` | wrong password 403, right password issues a real link session |
| PM-032 | `test_pm032_link_expiry_is_enforced_at_resolution` | a link whose stored expiry is past is refused with 410 at resolution |
| PM-033 | `test_pm033_view_only_and_download_policy_is_enforced` | view-only/download flags are advertised and download is refused until enabled |
| PM-039 | `test_pm039_restricted_session_token_is_scoped_to_its_link` | restricted session authorises only its own link; cross-link use 403; anonymous 401 |
| PM-042 | `test_pm042_instant_revocation_kills_live_sessions` | instant revoke marks the link and invalidates an already-live session |
| PM-072 | `test_pm072_viewer_and_visit_capture` | visitor name/email/IP/user-agent are captured on a real visit and readable from the workspace |
| PM-074 | `test_pm074_page_by_page_analytics` | per-page views, unique viewers and total durations are computed from real page-view rows |
| PM-080 | `test_pm080_verified_visitor_identification_and_consent` | verification is distinct from consent; PII is disclosed only with active consent and scrubbed on revoke |
| PM-125 | `test_pm125_document_conversion_job_produces_a_result_file` | a conversion job runs through the real storage path and produces a retrievable result file |

## Verification

- Targeted: `pytest apps/api/tests/test_p0_document_gaps.py -q` — 14 passed.
- Full API suite executed after integration; see `docs/TEST_RESULTS.md` and the
  execution record for the authoritative count.
- Migration chain: `a7c3e9d14b62` -> `a7c3e9f1b5d8` is a single head; both
  migrations are additive and preserve pre-existing workspace data.

## Honest limits

Document content is metadata and locally stored bytes; PDF/image/video
*processing* is the real local conversion/preview path, not a hosted rendering
service. No S3 provider, third-party conversion API or external identity
provider is claimed. Signed URLs are HMAC tokens produced and verified locally.
