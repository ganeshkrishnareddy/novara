# External blocker resolution report (Campaign 2)

**Status:** read-only audit. No application code, tests, final registry or shared final report were modified. No commit, push, tag or deploy performed.
**Prepared:** 2026-11-25 12:19 IST (Asia/Calcutta).
**Repository:** `D:\NOVARA` (Git HEAD `f1dcfefe162faac644e974f075a411eb0975f4cb`, branch `main`).
**Source of blocked rows:** `docs/FINAL_RELEASE_QA/FEATURE_BY_FEATURE_ACCEPTANCE.csv` (1,488 rows total).

## 1. Method

1. Filtered `FEATURE_BY_FEATURE_ACCEPTANCE.csv` where `Final acceptance status = BLOCKED_EXTERNAL`: **221 rows**.
2. Grouped the 221 rows by `Test method` (the recorded external step that was not executed):
   - `Live experiment create/observe/analyze + governance route render` -> 82 rows -> dependency class `external experimentation`.
   - `Campaign create/schedule + studio route render; no send executed` -> 104 rows -> dependency class `email`.
   - `Live automation create/status + workflow trigger` -> 19 rows -> dependency class `webhooks`.
   - `Live agent run/approval + API surface sweep + UI route render` -> 16 rows -> dependency class `hosted AI`.
3. Cross-checked against:
   - `apps/api/novara_core/modules/adapters.py` (`SUPPORTED_PROVIDERS` = 11, `BLOCKED_PROVIDERS` = 10, `PROVIDER_KINDS`, capability states).
   - `apps/api/novara_core/modules/integrations.py` (secret-field rejection, non-sensitive config only).
   - `.env.example` (no provider credentials; local mocks only).
   - `docs/FINAL_RELEASE_QA/INTEGRATION_VERIFICATION_REPORT.md`.
   - `docs/QA/BLOCKED_FEATURES.md` and `docs/QA/KNOWN_LIMITATIONS.md`.
4. No real credentials were used, no messages were sent, and no provider was contacted. Only documented local deterministic behaviour and existing evidence were used.
5. Supporting machine-readable grouping: `docs/FINAL_RELEASE_QA/CAMPAIGN2/evidence/external_blocker_groups.csv` (221 data rows).

## 2. Group summary

| Dependency class | Rows | Test method(s) | Provisionable locally / deterministic contract test | Live provider status |
|---|---:|---|---|---|
| external experimentation | 82 | Live experiment create/observe/analyze + governance route render | Local two-variant experiment analyzed; access-governance defect found and corrected then re-verified. Hosted SDK/provider not contacted. | NOT VERIFIED |
| email | 104 | Campaign create/schedule + studio route render; no send executed | Local campaign create/schedule + studio route render; no send executed. Message ledger records `delivered: False`. | NOT VERIFIED |
| webhooks | 19 | Live automation create/status + workflow trigger | Local adapter mock + deterministic message records with `delivered: False`; no outbound call. | NOT VERIFIED |
| hosted AI | 16 | Live agent run/approval + API surface sweep + UI route render | Local simulated agent run held at approval gate; no provider call. | NOT VERIFIED |
| **Total** | **221** |  |  |  |

## 3. Group details

### 3.1 External experimentation (82 rows)

- **Source projects:** GrowthBook (77), Novu (1), Plane (2), Chatwoot (2).
- **Feature ID examples:** `GB-007`, `GB-012`, `GB-013`, `GB-014`, `GB-020`, `GB-021`, `GB-022`, `GB-023`, `GB-024`, `GB-025` (full list in supporting CSV).
- **What is implemented locally:** local two-variant experiment analyzed; access-governance defect found and corrected then re-verified.
- **What is NOT verified live:** GrowthBook hosted SDK/provider, hosted control plane, real experiment assignment/delivery, external flag service.
- **Required credentials/environment (if live):** GrowthBook SDK/API key, environment, feature/experiment definitions, hosted control plane.
- **Owner:** Release owner / integration owner.
- **Release impact:** Blocks live experiment create/observe/analyze and hosted governance; local experiment capability remains available.
- **Verification result:** local / sandbox only; live provider NOT VERIFIED.

### 3.2 Email (104 rows)

- **Source projects:** Mautic (51 campaigns + 1 automation + 2 agent), Marketing Skills (53).
- **Feature ID examples:** `MT-001`-range campaign rows and `MS-` campaign rows (full list in supporting CSV).
- **What is implemented locally:** local campaign create/schedule + studio route render; no send executed. Outreach approval changes local status and writes audit events; no send endpoint.
- **What is NOT verified live:** campaign delivery (email/SMS/WhatsApp/push), provider API calls, verified senders, templates, webhook signing secrets.
- **Required credentials/environment (if live):** provider account, verified sender, API key/token, templates, webhook signing secrets.
- **Owner:** Release owner / marketing operations owner.
- **Release impact:** Blocks campaign send/delivery; local campaign authoring and scheduling remain available.
- **Verification result:** local / sandbox only; live provider NOT VERIFIED.

### 3.3 Webhooks (19 rows)

- **Source projects:** Novu (13 automations + 4 agent + 1 experiment), Plane (3), Papermark (1), Chatwoot (1), Mautic (1).
- **What is implemented locally:** local adapter mock + deterministic message records with `delivered: False`; no outbound call. `MessageRecord.delivered` defaults to `False`.
- **What is NOT verified live:** webhook delivery, multi-channel delivery, provider API calls, webhook verification.
- **Required credentials/environment (if live):** provider API key, environment, channel providers, workflow definitions, webhook secrets.
- **Owner:** Release owner / notification owner.
- **Release impact:** Blocks live multi-channel delivery and webhook-driven automation; local notification records and mock adapters remain available.
- **Verification result:** local / sandbox only; live provider NOT VERIFIED.

### 3.4 Hosted AI (16 rows)

- **Source projects:** GrowthBook (3), Novu (4), Papermark (2), Plane (2), Mautic (2), Sellbird (3).
- **What is implemented locally:** local simulated agent run held at approval gate; no provider call. API surface sweep and UI route render recorded.
- **What is NOT verified live:** hosted model providers, external experimentation SDK, hosted control plane, billing.
- **Required credentials/environment (if live):** hosted model API key, model/endpoint, usage/billing controls.
- **Owner:** Release owner / integration owner.
- **Release impact:** Blocks live provider-backed agent execution; local governed agent run and approval gate remain available.
- **Verification result:** local / sandbox only; live provider NOT VERIFIED.

## 4. Dependency classes with zero blocked rows in this set

The following classes from the requested list have **no** rows in the 221 `BLOCKED_EXTERNAL` acceptance set. They are documented as scope boundaries in `docs/QA/KNOWN_LIMITATIONS.md` and `docs/QA/BLOCKED_FEATURES.md`, not as external-provider acceptance rows:

- external credentials (generic) — no dedicated acceptance rows; provider-specific credentials listed per group above.
- SMS/WhatsApp — no dedicated acceptance rows; covered by provider adapter boundary (`BLOCKED_PROVIDERS` includes twilio; supported providers include whatsapp/sms as local mocks only).
- push — no dedicated acceptance rows; `BLOCKED_PROVIDERS` includes pushpad, firebase.
- OAuth/identity — no dedicated acceptance rows; no OAuth/SSO exercised.
- payments — no dedicated acceptance rows; no payment provider exercised.
- PostgreSQL — no dedicated acceptance rows; live PostgreSQL unverified (local SQLite only).
- Docker — no dedicated acceptance rows; container builds unverified.
- hosted deployment — no dedicated acceptance rows; no hosted deployment used.
- native/mobile builds — no dedicated acceptance rows; no mobile installer produced.
- app stores — no dedicated acceptance rows; no store submission.
- third-party CRM/helpdesk — represented by Plane/Chatwoot/Papermark/Sellbird rows, grouped above under their external step (experimentation/webhooks/hosted AI) rather than as a separate acceptance class.

## 5. What can be provisioned locally or via deterministic contract tests

- **Deterministic local adapter seam:** `adapters.py` local mocks only; `_mock_response(...)` always returns `delivered: False`; no network client, no credential use.
- **Secret rejection:** `integrations.py` rejects secret-looking fields (HTTP 422), including nested keys.
- **External-dependency no-claim boundary:** 94 named acceptance tests in `apps/api/tests/test_external_dependency_boundary_p2.py`; boundary module has no SDK import, no client, no socket, no endpoint.
- **Message ledger:** `MessageRecord.delivered` defaults to `False`; duplicate transaction/channel raises 409.
- **Campaign delivery:** explicitly `NOT_EXECUTED` (E2E record 17).
- **Agent runs:** simulated locally and held at approval gate.
- No real provider credential, webhook, OAuth, payment, PostgreSQL, Docker, hosted deployment, mobile build or store submission was used or verified.

## 6. Evidence references

- `docs/FINAL_RELEASE_QA/FEATURE_BY_FEATURE_ACCEPTANCE.csv` (1,488 rows; 221 `BLOCKED_EXTERNAL`).
- `docs/FINAL_RELEASE_QA/INTEGRATION_VERIFICATION_REPORT.md`.
- `apps/api/novara_core/modules/adapters.py`.
- `apps/api/novara_core/modules/integrations.py`.
- `.env.example`.
- `docs/QA/BLOCKED_FEATURES.md`.
- `docs/QA/KNOWN_LIMITATIONS.md`.
- `docs/evidence/external-dependency-boundary-p2-20261124.md`.
- `docs/evidence/t125-fullsuite-clean-20261124.txt`.
- `docs/evidence/t131-fullsuite-clean-20261124.txt`.
- Supporting CSV: `docs/FINAL_RELEASE_QA/CAMPAIGN2/evidence/external_blocker_groups.csv`.

## 7. Limitations

- Read-only audit only; no new tests were run and no files were edited.
- Grouping is by recorded `Test method`, which reflects the external step not executed; source-project distribution is recorded in the supporting CSV.
- No live provider availability, latency, rate limit, pricing or delivery success was verified.
- Counts reflect repository state at Git HEAD `f1dcfefe162faac644e974f075a411eb0975f4cb` (2026-11-25).
- No legal or licensing opinion is expressed.
- This report does not authorise any external integration, credential use or provider contact.
