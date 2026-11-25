# NOVARA website content claims audit

Scope: every factual statement on the locally prepared launch portal. Status: **audit completed against the final `site/index.html` on 2026-11-24**. Claims were checked against the rendered page and against `artifacts/marketing_site_qa/validator-final.txt`, `verify_site.json` and `verify_subpath.json`. All approved claims below were confirmed, and all prohibited claims were confirmed absent. No claim here authorises publication; owner authorization is still required.

## 1. Approved claims and exact evidence

| # | Claim as it may appear on the site | Exact supporting evidence | Condition / wording rule |
| --- | --- | --- | --- |
| C1 | Product name NOVARA; tagline "Everything Connected. Everything Under Control." | Owner product brief; `README.md` | Use verbatim |
| C2 | Repository: https://github.com/ganeshkrishnareddy/novara | Owner product brief | Plain link, no engagement bait |
| C3 | Expected Pages URL https://ganeshkrishnareddy.github.io/novara/ | Owner product brief | Must be labelled **not configured or verified live; site prepared locally only** |
| C4 | Active development, NOT a release candidate | Owner fact sheet; `docs/PROJECT_STATUS.md` | Must appear prominently; no "released", "production ready", or "launch" as achieved state |
| C5 | Local-first: Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite by default; vanilla JS light-theme web app | Owner fact sheet; `README.md`; `docs/QA/MASTER_QA_REPORT.md` (light theme only) | Do not imply hosted service, dark mode, or native mobile apps |
| C6 | 1,488 catalogued feature rows: 1,418 `VERIFIED_COMPLETE`, 70 `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION`, 0 `NOT_IMPLEMENTED` / `PARTIALLY_IMPLEMENTED` / `EXTERNAL_DEPENDENCY_BLOCKED` / `LICENSING_RESTRICTED` | `docs/FEATURE_PARITY/COMPLETION_DASHBOARD.md` | Quote exactly; never restate as "100% complete" or "all features accepted" |
| C7 | Backend suite: 1641 passed, 4 warnings in 1395.31s, EXIT=0 | `docs/evidence/t131-fullsuite-clean-20261124.txt` and `-exit.txt` | Quote exactly; do not convert into uptime or quality percentage |
| C8 | Isolated QA: 293 API records all PASS; 61 end-to-end records (52 PASS, 9 INFO, 0 FAIL); 17/17 security checks PASS; 50 module routes rendered; light theme only | `docs/QA/MASTER_QA_REPORT.md`, `docs/QA/MODULE_TEST_RESULTS.md`, `docs/QA/END_TO_END_WORKFLOW_RESULTS.md`, `docs/QA/SECURITY_TEST_RESULTS.md` | 17/17 checks are smoke-level negative checks, not a penetration test; a rendered route is not per-feature acceptance |
| C9 | Two real MP4s: `NOVARA_Product_Demo_1.0.mp4` (1:40) and `NOVARA_Complete_QA_Walkthrough.mp4` (3:16) in `artifacts/final_qa_2026-11-24/videos/` | `docs/QA/VIDEO_CHAPTER_INDEX.md`; files observed present | Label local QA capture with synthetic data; no customer claims |
| C10 | Licensing review complete in `docs/research/LICENSE_COMPLIANCE.md` and `THIRD_PARTY_NOTICES.md`; no source copied from the ten reference projects | Those two documents | Must be paired with the required licensing wording in C11 |
| C11 | Required wording: "open-source foundation subject to final repository licensing review; licence file pending owner decision." | Owner fact sheet; `docs/research/LICENSE_COMPLIANCE.md` (no NOVARA LICENSE file yet) | Use verbatim. Do **not** say "fully open source" |
| C12 | Ten inspiration projects: Formbricks, Meilisearch, GrowthBook, Papermark, Plane, Mautic, Chatwoot, Novu, Marketing Skills, Sellbird | `docs/VISION.md`; `docs/FEATURE_PARITY/COMPLETION_DASHBOARD.md`; `docs/research/LICENSE_COMPLIANCE.md` | Describe as functional alternatives/inspiration only; no affiliation; no codebase redistribution; no third-party logos or marks |
| C13 | Contributions are reviewed by humans; stars/forks/watches are voluntary; no engagement incentives | `docs/COMMUNITY_CONTRIBUTION_PROGRAM.md`; `docs/MARKETING_WEBSITE_PLAN.md` | Do not promise benefits; any benefit is subject to approved budget and availability |
| C14 | No analytics, cookies, trackers, or secrets on the site | `docs/MARKETING_WEBSITE_PLAN.md` (decision); `docs/WEBSITE_HOSTING_GUIDE.md` | Must be verified against final page source before publication |
| C15 | Local-first boundaries: no native mobile apps; container builds not verified; live PostgreSQL not verified; no outbound email/SMS/campaign delivery or hosted AI/provider calls executed | Owner fact sheet; `docs/QA/KNOWN_LIMITATIONS.md`; `docs/QA/MASTER_QA_REPORT.md` | State as limitations, not achievements |

## 2. Prohibited claims — excluded and why

| # | Prohibited claim | Reason for exclusion | Required action |
| --- | --- | --- | --- |
| P1 | "100% complete", "all features implemented", "fully finished" | Evidence shows active development and 70 replaced rows; parity accounting is not acceptance | Use C6 verbatim with status C4 |
| P2 | "Fully open source", "OSI-approved", "licensed under MIT/GPL/AGPL" | No root LICENSE file; licence choice is an owner decision | Use C11 verbatim only |
| P3 | Star/fork/watch/download counts, badges, or "trending" language | No such measured figures; engagement figures are voluntary actions and cannot be incentivised | Never display; no dynamic badge services |
| P4 | Customer counts, named customers, logos, quotes, testimonials, case studies | None supplied or verified | Omit entirely; no placeholder testimonials |
| P5 | Uptime, availability, SLA, "always on", response-time or performance figures | No hosted service or monitoring; Pages not enabled | Omit; no invented performance metrics |
| P6 | "Production ready", "release candidate", "v1.0 released", "public beta live" | Explicitly active development, not a release candidate; no release/tag/binary published | Use C4 |
| P7 | "Deployed", "live at …", "available now" with the Pages URL as fact | Pages not configured or verified live; nothing published | Use C3 conditional wording |
| P8 | "Real email/SMS/campaigns sent", "AI agents call providers", "hosted AI integrated" | No outbound delivery or hosted provider calls executed; QA records are local/simulated | Use C15; describe drafts/local records only |
| P9 | "Docker verified", "PostgreSQL tested", "mobile apps available", "security audited/pentested" | Container builds and live PostgreSQL unverified; no native mobile apps; 17 checks are smoke-level only | Use C15; omit audit/certification language |
| P10 | Endorsement or affiliation with the ten reference projects, or their logos/marks | Inspiration/functional alternatives only; no affiliation; third-party marks not licensed | Use C12 |
| P11 | "Verified testimonials from users", "awards", "press coverage" | No evidence exists | Omit entirely |
| P12 | "Stars/follows unlock premium tools or features" | Prohibited by engagement policy; app features are never gated | Use C13 |

## 3. Licensing wording review

| Check | Required | Result |
| --- | --- | --- |
| Exact licensing phrase present | "open-source foundation subject to final repository licensing review; licence file pending owner decision." | **PASS** — present verbatim in `site/index.html` (self-hosting callout and FAQ) and in `README.md` |
| "fully open source" absent | Must not appear anywhere | **PASS** — not present in final site text (literal string check) or README |
| No specific licence claimed | No MIT/GPL/AGPL badge or statement about NOVARA itself | **PASS** — no licence badge or named NOVARA licence on the site; validator found no unverified badges |
| No root LICENSE implied | Absence acknowledged; owner decision pending | **PASS** — site says the repository licence file is an owner decision |
| No source-copy claim contradicted | Review states no source copied from ten reference projects | **PASS** — supported by `docs/research/LICENSE_COMPLIANCE.md`, `THIRD_PARTY_NOTICES.md` |
| Reference projects described correctly | Inspiration/functional alternatives, no affiliation or redistribution | **PASS** — section D labels them functional alternatives and inspiration sources |
| Third-party notices linked | Links to `docs/research/LICENSE_COMPLIANCE.md` and `THIRD_PARTY_NOTICES.md` | **PASS** — both linked in the site body and footer |

## 4. Video and screenshot labelling

Both MP4s are real files produced from local desktop capture, with generated chapter cards and narration. They evidence visible UI behaviour, not product adoption or per-feature acceptance.

| Asset | Label that must accompany it |
| --- | --- |
| `NOVARA_Product_Demo_1.0.mp4` (1:40) | "Local product demo — captured in a local QA environment using synthetic data; not customer footage." |
| `NOVARA_Complete_QA_Walkthrough.mp4` (3:16) | "Local QA walkthrough — captured in a local QA environment using synthetic data; demonstrates observed flows, not acceptance of every feature." |
| Any screenshot under `site/assets/img/*` | "Local QA capture (synthetic data); light theme; not a customer deployment." |

Additional rules:

- Do not crop or caption media in a way that suggests real customers, real messages sent, uptime, or external integrations.
- No real email, SMS, WhatsApp, payment, provider, hosted AI, or external transaction appears as if executed; anything of that kind is labelled local/simulated/`NOT_EXECUTED`.
- 17/17 security checks and 50 rendered routes remain scope-limited; media must not imply a penetration test or full feature acceptance.

## 5. Claims that must remain conditional

| Claim | Why conditional | Condition to lift |
| --- | --- | --- |
| Site available at the expected Pages URL | Pages not configured or verified live | Owner enables and verifies Pages; then update the completion report |
| Canonical URL / sitemap entries point to that URL | URL is a placeholder | Hosting verified |
| Validator passes / browser checks pass | Were conditional while the site was being built | **LIFTED locally** — validator 35 passed / 0 failed, exit 0; 20/20 browser checks at root and under `/novara/`. Still conditional on real Pages hosting |
| README audit passes | Was conditional while the redesign was in progress | **LIFTED locally** — final README audited per `docs/GITHUB_README_AUDIT.md`; see that file for the gate result |
| NOVARA is open source under a named licence | No root LICENSE; owner decision pending | Owner selects and adds a licence, then wording is re-audited |
| Container builds / live PostgreSQL work | Not verified | Named verification evidence exists |
| Contributions receive benefits | No approved budget or published criteria | Owner approval under `docs/COMMUNITY_CONTRIBUTION_PROGRAM.md` |
| Any outbound delivery or hosted AI integration | Not executed | Named evidence of an authorised execution |

## 6. Final gate

Conditions (a) final HTML checked against this table and (b) validator and browser results recorded are **complete** for the local portal. Condition (c), explicit owner authorization for commit, push, Pages enablement and deployment, is **not complete**. **Not published.** No external requests were made during verification; all checks ran against local files and `127.0.0.1`.
