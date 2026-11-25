# NOVARA — Owner action checklist (Release Gate Closure)

**Date:** 2026-11-25 (IST). **Project:** `D:\NOVARA`. **Overall verdict:** `RELEASE_BLOCKED`.
**Purpose:** the exact decisions and actions only the owner (or an owner-authorised executor) can take. Nothing in this checklist has been decided, performed or assumed. No real external action, commit, push, tag, deploy or credential use has occurred.

---

## A. Decisions required from the owner

| ID | Decision required | Owner | Current state | Gate closes when | Evidence |
|---|---|---|---|---|---|
| **B-01** | Decide whether any of the 737 `NOT_TESTED` rows may be promoted. Default applied by the audit: **no promotion**. | Release owner | Open — 0 promotions, 0 `PARTIAL` granted | Written authorization naming the rows/criteria and a fresh acceptance decision is recorded | `FEATURE_ACCEPTANCE_PROMOTION_REPORT.md`, `FEATURE_STATUS_PROMOTION_AUDIT.csv` |
| **B-02** | For each provider group, authorize a **non-production** account, supply scoped credentials/config/test recipients, and separately authorize the live run. | Release owner + integration owner | Open — live verification **0/21**; 221 rows `BLOCKED_EXTERNAL` | Each group's live verification is authorized and executed with provider-specific evidence; only then may a promotion decision be revisited | `EXTERNAL_PROVIDER_GATE_REPORT.md`, `EXTERNAL_PROVIDER_VERIFICATION_MATRIX.csv` |
| **B-04** | Choose NOVARA's licence (reviewer: **MIT**; alternative Apache-2.0 if patent grant preferred) or explicitly keep B-04 open. | Release owner | Open — no root licence file or metadata | Written choice plus committed licence file, `pyproject.toml` metadata and notice/SBOM corrections | `LICENSE_AND_COMPLIANCE_GATE.md` §9–10 |
| **B-05** | Authorize Docker image build, container healthcheck, live PostgreSQL (`postgres` profile), hosted API/UI deployment and signed installers. | Release owner + infrastructure owner | Open — **0%** backend/hosted deployment verified | Each item is actually built/run/deployed and verified; no claim is made from files alone | `DEPLOYMENT_AND_PACKAGING_GATE.md`, `FINAL_RELEASE_BLOCKERS.md` |
| **B-06** | Commission name, trademark and domain availability review for "NOVARA". | Release owner | Open — not checked | Written review result and any resulting naming/domain action | `FINAL_RELEASE_BLOCKERS.md`, `LICENSE_AND_COMPLIANCE_GATE.md` §5.4 |
| **B-07** | Decide on README advisory gaps (explicit Star/Fork/PR URLs). Any edit is a **separate authorized task**; the audited README hash was not changed here. | Release owner | Open — README SHA-256 unchanged | Owner decision plus authorized edit, with the new hash recorded | `FINAL_RELEASE_BLOCKERS.md` |
| **B-08** | Commission non-Chromium browser checks and a formal penetration test. | Release owner | Open — Chromium only; no pentest | Results recorded for Firefox/Safari/Edge and a formal pentest report | `MARKETING_SITE_RELEASE_VERIFICATION.md`, `FINAL_RELEASE_BLOCKERS.md` |
| **B-03** | Marketing site owner gate. | Release owner | **CLOSED** — Pages enabled, workflow `45556726447` attempt 2 `success`, live URL/asset HTTP 200 | Already satisfied; no further action for the public page | `MARKETING_SITE_RELEASE_VERIFICATION.md` |

---

## B. Provider decisions, itemised (B-02)

| Group | Rows | Supply and authorize | Constraint for any later live run |
|---|---:|---|---|
| External experimentation | 82 | Non-production GrowthBook account; scoped SDK/API key, environment, feature/experiment definitions | No production flags, customer data or flag changes |
| Email | 104 | Non-production email account; verified sender/domain, scoped API token, templates, webhook signing secret, designated test recipients | Test recipients only; no real customers |
| Webhooks | 19 | Non-production webhook provider; scoped key, channel definitions, signing secret, test endpoints | No outbound calls to real recipients |
| Hosted AI | 16 | Non-production model account; scoped API key, model/endpoint, billing controls, approved test prompts/data | Must pass through the approval gate; no public action or unmetered spend |

Ten additional blocked families (**SendGrid, Mailgun, Twilio, Pushpad, Firebase, Slack, Telegram, Discord, PagerDuty, Opsgenie**) each need a separate build decision plus scoped non-production credentials before any live claim. Supplying credentials alone is **not** authorization to contact a provider, and local evidence alone is **not** authorization to promote a status.

---

## C. Implementation tasks to authorize after a decision (do not start without sign-off)

| Task | Depends on | Work to authorise |
|---|---|---|
| Licence implementation | B-04 | Add root `LICENSE`, set `pyproject.toml` metadata, correct stale "no source copied" statements (keep all MIT notices/provenance), update `PROVENANCE.md` to 53 skills / 400 files with the real manifest SHA |
| Distribution compliance | B-04, B-05 | Add notices to the Docker image, pin dependencies/lockfile, generate SBOM from the **built** image, review `psycopg[binary]` (LGPL-3.0-only) and `certifi` (MPL-2.0) |
| Provider adapters | B-02 | Deliberate secret storage/rotation and audit events (current config rejects secret-looking fields); then implement and verify each authorised live adapter |
| Status promotion | B-01 | Apply only the owner-authorized rows with explicit evidence; record who authorized and when |
| Deployment verification | B-05 | Build/run the image, exercise `/health`, run PostgreSQL profile, deploy hosted API/UI, build signed installers |
| Editorial / coverage | B-06, B-07, B-08 | README advisory edit (new hash recorded), trademark/domain review, non-Chromium checks, penetration test |

**Standing boundaries:** keep the clean-room posture (no AGPL/GPL/EE/proprietary source copying, no paid tier or EE credential as a dependency); obtain legal review before treating any AGPL/GPL upstream as a separate network service. Until the licence implementation completes, use exactly `open-source foundation subject to final repository licensing review; licence file pending owner decision.` — never "fully open source", "openly licensed release" or third-party endorsement.

---

## D. What can be performed next without a new owner decision

| Action | Status |
|---|---|
| Record the fresh full-suite result with the gate documents | In progress — `PHASE_H_REGRESSION_LOG.txt`; final figure inserted into the decision on completion |
| Re-run static validator, `node --check` and Alembic head check after any future site/frontend/migration change | Fresh runs already completed in this reconciliation: 35/0, exit 0, single head `b5c6d7e8f9a0` |
| Prepare (but do not execute) provider-verification plans and licence-implementation diffs for sign-off | Ready to prepare |
| Preserve all existing evidence and working-tree state; no reset, clean, stash or history rewrite | Maintained — HEAD and README hash unchanged; working tree preserved |

---

## E. Gate-closure rule

No gate is closed by this checklist. A gate closes only after the owner's explicit decision **and** verifiable evidence of completion. Until then the governing verdict is `RELEASE_BLOCKED`; the live marketing site and complete local evidence do not alter it.
