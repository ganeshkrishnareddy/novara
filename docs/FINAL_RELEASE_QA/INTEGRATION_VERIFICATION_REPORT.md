# NOVARA — Integration Verification Report

**Prepared by:** Skye (ProgVision Games)
**Report type:** Final release QA — integration verification
**Generated:** 2026-11-25, 11:22 IST
**Repository:** `D:\NOVARA` (Git HEAD `f1dcfefe162faac644e974f075a411eb0975f4cb`, branch `main`)
**Scope constraint:** Read-only compilation. No existing file was edited; no commit, push, deploy or external transaction was performed. Only this report and `TEN_SOURCE_PROJECT_COMPLETION_REPORT.md` were created.

## 1. Purpose

State, for every integration surface in NOVARA, what is implemented locally, what is a sandbox/mock, and what is a live provider that is **NOT VERIFIED**. List the credentials that would be required for any future live integration. Every claim traces to a named file in §7.

## 2. Method

1. Read `apps/api/novara_core/modules/integrations.py` and `apps/api/novara_core/modules/adapters.py` (the integration catalog and adapter seam).
2. Read `.env.example` (provider/secret configuration surface).
3. Read `docs/architecture/CONTRACTS.md` (approval/external-action boundary).
4. Read `docs/QA/MASTER_QA_REPORT.md`, `docs/QA/BLOCKED_FEATURES.md`, `docs/QA/KNOWN_LIMITATIONS.md`, `docs/evidence/external-dependency-boundary-p2-20261124.md`.
5. Cross-checked supported/blocked provider lists and counts from `adapters.py` (`SUPPORTED_PROVIDERS`, `BLOCKED_PROVIDERS`, `PROVIDER_KINDS`).
6. No network call, credential use or provider contact was made for this report.

## 3. Integration model (as implemented)

- **Local-first only.** SQLite is the default store; PostgreSQL is optional and was not used in QA.
- **No outbound network calls.** `adapters.py` states: "All adapters are local mocks in this build. No outbound network call is made, no credential is used, and no external delivery is claimed." `_mock_response(...)` always returns `delivered: False`.
- **Secrets rejected at the API boundary.** `integrations.py` rejects any config key whose normalised name is in `SECRET_FIELD_NAMES` (apikey, token, secret, password, credential, privatekey, authorization, …), including nested keys, with HTTP 422. Only non-sensitive settings are stored.
- **Configuration ≠ live adapter.** Recording an integration row stores non-sensitive config only; it does not activate a live adapter. `RECORDED_NOTE`: "configuration recorded; no outbound adapter is active in this build."
- **Approval boundary.** `CONTRACTS.md`: no code sends email, posts publicly or performs a destructive action; `OutreachDraft.status` is `draft` or `approved` only; a delivery adapter needs its own authorisation and audit event before it can be added.
- **Message records never claim delivery.** `MessageRecord.delivered` defaults to `False` and the note reads "local message record; no external delivery claimed"; duplicate transaction/channel raises 409.

## 4. Verification status legend

| Label | Meaning |
|---|---|
| Local implementation | Code exists in NOVARA and was exercised locally (tests/routes). |
| Sandbox / mock | A deterministic local stub records an `AdapterCall`/event; nothing is sent. |
| Live provider NOT VERIFIED | No real provider endpoint, credential or external transaction was used. |

## 5. Supported providers (11) — local config + mock only

| Provider | Kind | Local implementation | Sandbox / mock | Live provider | Credentials that would be needed (not used) |
|---|---|---|---|---|---|
| Gmail | email | Yes — `integrations.py`, `adapters.py` | Yes — local mock, `delivered: False` | NOT VERIFIED | OAuth client ID/secret, refresh token, mailbox scopes; SMTP/IMAP or Gmail API credentials |
| Outlook | email | Yes | Yes | NOT VERIFIED | Microsoft Entra app client ID/secret, tenant, mailbox permissions, Graph/SMTP credentials |
| WhatsApp | whatsapp | Yes | Yes | NOT VERIFIED | WhatsApp Business API token, phone-number ID, webhook verify token, message templates |
| SMS | sms | Yes | Yes | NOT VERIFIED | SMS gateway account SID/auth token, sender ID/number, delivery receipts webhook |
| OpenAI | ai | Yes | Yes (returns `output: None`, `tokens: 0`) | NOT VERIFIED | OpenAI API key, model/endpoint, usage/billing controls |
| Local LLM | ai | Yes | Yes | NOT VERIFIED (local model not invoked) | Local model runtime endpoint and model weights (no secret, but runtime not wired) |
| Meilisearch | search | Yes | Yes (returns empty results) | NOT VERIFIED | Meilisearch host URL and API key (non-secret config only in this build) |
| GrowthBook | flags | Yes | Yes (returns `variation: None`) | NOT VERIFIED | GrowthBook API key/SDK key, environment, feature/experiment definitions |
| Chatwoot | support | Yes | Yes | NOT VERIFIED | Chatwoot base URL, API access token, inbox/webhook configuration |
| Novu | notification | Yes | Yes | NOT VERIFIED | Novu API key, environment, channel providers, workflow definitions |
| Plane (compatible adapter, opt-in) | project_management | Yes | Yes | NOT VERIFIED | Plane base URL, API token, workspace/project identifiers |

Counts: `configurable_provider_count = 11`, `local_adapter_count = 11` (from `provider_capabilities()` in `adapters.py`).

## 6. Blocked providers (10) — no local adapter exists

These are reported with status `blocked`; no outbound call is possible and no mock is available.

| Provider | Kind | Local implementation | Sandbox / mock | Live provider | Credentials that would be needed (not used) |
|---|---|---|---|---|---|
| SendGrid | email | No | No | NOT VERIFIED / blocked | SendGrid API key, verified sender, template IDs |
| Mailgun | email | No | No | NOT VERIFIED / blocked | Mailgun API key, domain, verified sender |
| Twilio | sms | No | No | NOT VERIFIED / blocked | Twilio account SID/auth token, messaging service SID |
| Pushpad | push | No | No | NOT VERIFIED / blocked | Pushpad auth token, project ID, VAPID keys |
| Firebase | push | No | No | NOT VERIFIED / blocked | Firebase service account, FCM server key, project ID |
| Slack | chat | No | No | NOT VERIFIED / blocked | Slack bot token, signing secret, channel IDs |
| Telegram | chat | No | No | NOT VERIFIED / blocked | Bot token, chat IDs, webhook secret |
| Discord | chat | No | No | NOT VERIFIED / blocked | Bot token, application ID, guild/channel IDs |
| PagerDuty | tool | No | No | NOT VERIFIED / blocked | API token, service/escalation policy IDs |
| Opsgenie | tool | No | No | NOT VERIFIED / blocked | API key, team/integration IDs |

`blocked_provider_count = 10`. Capability states are `configured`, `disabled`, `not_configured`, `blocked` (`CAPABILITY_STATES` in `adapters.py`).

## 7. What is implemented vs. not verified (summary)

**Implemented (local):**
- Integration catalog CRUD with non-sensitive config only (`integrations.py`: `list_integrations`, `upsert_integration`, `get_integration`, `disable_integration`, `list_capabilities`).
- Adapter invocation seam with four-state capability view (`adapters.py`: `invoke_adapter`, `provider_capabilities`, `list_adapters`, `list_calls`, `capabilities`).
- Per-channel message ledger with `delivered = False` always (`record_message`, `list_messages`, `get_message`, `delete_message`).
- External-dependency no-claim boundary covering 94 rows across Formbricks, Sellbird, GrowthBook, Chatwoot, Meilisearch, Papermark, Mautic, Novu (`docs/evidence/external-dependency-boundary-p2-20261124.md`).

**NOT verified (live):**
- Any real provider API call, webhook, OAuth/SSO or credential use.
- Campaign delivery (email/SMS/WhatsApp/push) — W2 record 17 labelled `NOT_EXECUTED` (`docs/QA/END_TO_END_WORKFLOW_RESULTS.md`).
- Public document link notification — local share-link record only; no recipient contacted (W4).
- Live AI model providers — agent run is simulated locally and held at the approval gate (W8).
- External experimentation SDK / hosted control plane / billing (W5).
- Production PostgreSQL, Docker, hosted deployment — QA used fresh local SQLite only.
- Real payment, identity provider, OAuth/SSO, live CRM/helpdesk — no external accounts or credentials used (`docs/QA/BLOCKED_FEATURES.md`).

**Credentials that would be needed (general, if live integration is ever pursued):** provider API keys/tokens, OAuth client secrets and refresh tokens, SMTP/IMAP credentials, webhook signing secrets, push-notification keys (VAPID/FCM), and any provider-specific account/project identifiers. These are not stored anywhere in this build: `.env.example` states "None. NOVARA adapters are local mocks in this build. There are no provider credentials, API keys, webhooks or outbound endpoints to configure." The application rejects secret-looking fields by design, so adding a live adapter would require deliberate new code with its own documented secret handling.

## 8. Named evidence files

Code (integration seam):
- `apps/api/novara_core/modules/integrations.py`
- `apps/api/novara_core/modules/adapters.py`
- `apps/api/novara_core/modules/external_dependency_boundary.py` (per `docs/evidence/external-dependency-boundary-p2-20261124.md`)
- `apps/api/novara_core/workflow.py` (outreach draft approval boundary)
- `apps/api/novara_core/CONTRACTS.md`-adjacent: `docs/architecture/CONTRACTS.md`

Configuration:
- `.env.example` (no provider credentials; local mocks only)

QA / boundary documents:
- `docs/QA/MASTER_QA_REPORT.md`
- `docs/QA/BLOCKED_FEATURES.md`
- `docs/QA/KNOWN_LIMITATIONS.md`
- `docs/QA/END_TO_END_WORKFLOW_RESULTS.md`
- `docs/evidence/external-dependency-boundary-p2-20261124.md`
- `docs/research/INTEGRATION_STRATEGY.md` (status: scaffold — pending architecture review T-008)

Test evidence:
- `apps/api/tests/test_external_dependency_boundary_p2.py` (94 named acceptance tests, per evidence doc)
- Full suite: `docs/evidence/t131-fullsuite-clean-20261124.txt` (`1641 passed, 4 warnings`, exit 0) and `docs/evidence/t131-fullsuite-clean-exit.txt`
- `docs/evidence/t125-fullsuite-clean-20261124.txt` (external-dependency boundary run)

## 9. What could not be verified

- No live provider was contacted; therefore no statement about provider availability, latency, rate limits, pricing or delivery success can be made.
- No credentials exist in this build, so credential flows (OAuth, token refresh, webhook verification) were not exercised.
- No production PostgreSQL/Docker/hosted environment was used; integration persistence behaviour on those engines is unverified.
- `docs/research/INTEGRATION_STRATEGY.md` is a scaffold pending architecture review (T-008); no integration architecture document beyond it was found (`INTEGRATION_ARCHITECTURE.md` does not exist in this repository).
- Counts of configured integrations in any workspace are data-dependent and were not measured (QA used synthetic identities with no integration rows).

## 10. Limitations of this report

- This is a compilation of existing evidence and source code, not new testing. No command was run to generate new results.
- All integration capabilities are local mocks or blocked entries; nothing here should be read as a live integration claim.
- Evidence file paths are relative to `D:\NOVARA`.
- Counts reflect the repository state at Git HEAD `f1dcfefe162faac644e974f075a411eb0975f4cb` (2026-11-25).
