# T-057 evidence — P0 Mautic consent and identity (2026-11-22)

## Scope

| ID | Source feature | Acceptance evidence |
| --- | --- | --- |
| MT-019 | Email unsubscribe and preference centre tokens | `test_mautic_consent_identity_p0.py::test_unsubscribe_link_updates_consent_and_blocks_future_recipients`, `::test_resubscribe_and_dnc_links_are_signed_scoped_and_reversible`, `::test_preference_centre_updates_only_supported_channels`, `::test_dnc_after_unsubscribe_reuses_one_suppression_entry` |
| MT-113 | Contact identity with external IDs | `::test_external_id_is_preserved_without_replacing_novara_identity`, `::test_external_identity_validation_and_workspace_scoping` |

Clean-room implementation only; no Mautic code, instance, bundle or schema was
copied.

## What was built

- `modules/email_campaigns.py`: generalized HMAC-signed, expiring,
  workspace-bound consent links for four actions — unsubscribe, resubscribe,
  global do-not-contact (DNC) and preference centre. A tampered token returns
  400 and a token from another workspace returns 403.
- Unsubscribe now records a `ConsentRecord(granted=False, source=unsubscribe)`
  in the same transaction as the suppression entry. This is the explicit
  MT-019 acceptance criterion: the flow itself updates consent.
- Resubscribe removes suppression, clears DNC and grants consent. DNC sets the
  new contact flag and blocks every channel. Preference-centre GET returns the
  current channel state; POST records only supported channel changes and cannot
  override an active DNC.
- `models.py` / migration `a9c4e2f6b815`: `Contact.external_id`,
  `Contact.external_source` and `Contact.do_not_contact`. The external pair is
  validated as present-together, non-blank and unique per workspace and source;
  NOVARA's own contact id never changes and a `contact.external_id_updated`
  event records each provenance change.
- Recipient enforcement: a suppressed, unconsented or DNC contact is skipped
  before any recipient is queued. No external email is sent anywhere in this
  cluster.
- `apps/web/app.js`: the contact profile has a Consent & preferences card with
  external-identity provenance and unsubscribe, resubscribe, DNC and preference
  controls. Signed tokens are generated on demand, kept only in JS memory and
  never interpolated into rendered markup.
- `scripts/runtime_smoke.py`: section [11] exercises the whole cluster over HTTP.

## Commands and results

From `D:\NOVARA\apps\api` (Python at `D:\NOVARA\.venv\Scripts\python.exe`):

```
python -m pytest tests/test_mautic_consent_identity_p0.py -q -rs
  5 passed, 1 warning in 1.74s   (later 6 with the suppression regression)

python -m pytest tests/test_ui_wiring.py tests/test_mautic_consent_identity_p0.py -q -rs
  15 passed, 1 warning in 1.83s

python -m pytest -q -rs
  229 passed, 1 warning in 78.14s
```

From `D:\NOVARA`:

```
node --check apps\web\app.js                    -> no syntax errors
python -m compileall -q apps\api\novara_core    -> no errors
python scripts\runtime_smoke.py                 -> RUNTIME SMOKE: PASS (sections 1-11)
python C:\...\novara_migrate_check.py
  upgrade -> downgrade -> upgrade                -> ROUND TRIP PASS, sample contact preserved
```

The only warning is the known Starlette/httpx TestClient deprecation notice.
No signed tokens, bearer tokens, response bodies or credentials were printed.

## Behavior proved

- Four signed link kinds are generated for one contact; a trailing-character
  tamper is rejected and a valid token used against a different workspace is
  rejected.
- Unsubscribe adds one suppression entry and a revoked email consent record;
  a later broadcast skips that contact with no second manual step.
- DNC is reflected on the contact record and blocks recipients across channels;
  resubscribe clears both and restores consent.
- DNC following an unsubscribe does not create a second suppression row (the
  table is unique per workspace and email).
- Preference updates accept only email/sms/push and refuse to override DNC.
- External ids survive patching, are unique per workspace and source, and are
  invisible from another workspace. The NOVARA id is stable throughout.

## Matrix accounting

Only MT-019 and MT-113 were changed in `MASTER_FEATURE_MATRIX.csv`; all seven
FEATURE_PARITY deliverables were regenerated:

- 1,488 permanent IDs, zero omissions
- VERIFIED_COMPLETE 68 (was 66)
- complete-like 153 / 1,488 = 10.28% (was 151 / 10.15%)
- PARTIALLY_IMPLEMENTED 144 (was 146)
- P0: 111 rows — 61 verified, 9 partial, 32 replacement, 9 restricted

## Not claimed

- No real email, SMS or push delivery; all flows are local records.
- No live Mautic instance, license, or external sync.
- No commit, push, tag, deployment or public publishing. Git HEAD remains
  `73e9f76`.

## Next

T-058: select the next group from the 9 remaining P0 partial rows (Plane 4,
Mautic 4, Novu 1).
