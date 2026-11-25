# GitHub README audit — completed

Scope: completed re-audit of the final redesigned `README.md` (543 lines, UTF-8) at the repository root of https://github.com/ganeshkrishnareddy/novara . The README was read directly after the five previously reported FAILs were closed and read again after section 13 was revised to list three MP4s; this document records the result of that fresh, evidence-based re-audit.

## Audit completed

Audit executed **2026-11-25** against the current `README.md`. Every row below was checked against that file; no status was inherited from the pre-rewrite framework draft or the earlier failed pass.

| Field | Value |
| --- | --- |
| Date of audit | 2026-11-25 |
| Git HEAD of audited README | `73e9f76f6c8dd3360b73f7c5c8abec98726f28f8` |
| README SHA-256 | `e3b18389a81816e43006d1667a6eff3fe6bf6ba2330168f2cfc9ba6a6767b64c` |
| Auditor | Local audit subagent (only `docs/GITHUB_README_AUDIT.md` was edited) |
| Overall result | PASSED — see Result below |
| Counts | **40 PASS / 0 FAIL / 0 N/A** across 40 rows: required criteria 27 PASS / 0 FAIL; banned items 8 PASS / 0 FAIL; cross-document checks 5 PASS / 0 FAIL |

## Method

1. Read the final `README.md` top to bottom; do not rely on the pre-rewrite version.
2. Check each of the 27 required sections below for presence and for the expected criterion.
3. Check the banned-items table independently: any banned item present is a `FAIL` even if all 27 sections pass.
4. Cross-check every number and status phrase against `docs/FEATURE_PARITY/COMPLETION_DASHBOARD.md`, `docs/evidence/t131-fullsuite-clean-20261124.txt` and `-exit.txt`, `docs/QA/MASTER_QA_REPORT.md`, and `docs/research/LICENSE_COMPLIANCE.md`.
5. Record results; re-audit after any subsequent README edit.

Status legend: `PASS` = verified in final README; `FAIL` = missing or non-conforming (a banned item scores `PASS` when the banned content is absent); `N/A` = not applicable with written reason. `PENDING` was retired by this audit.

## 27 required sections — audit checklist

| # | Required section | Expected criterion (PASS condition) | Status | Evidence / reason |
| --- | --- | --- | --- | --- |
| 1 | Title, tagline, repository and expected Pages URL | Product named NOVARA; tagline verbatim "Everything Connected. Everything Under Control."; repo URL present; Pages URL marked not configured/verified live | PASS | L5 `NOVARA`; L13 tagline verbatim; L29 repo link; L21–23 expected Pages URL shown as code only, "planned and subject to owner configuration, not as a live site". |
| 2 | Project overview | One local-first, self-hostable product; not ten separate apps | PASS | L38–39 "one self-hostable business operating system, not ten separate apps linked together"; L71–73 shared identity/workspace/permissions/events. |
| 3 | Honest status banner | States "active development" and "not a release candidate" prominently | PASS | L15 "Active development · Not a release candidate · Local-first by default"; reinforced L450. |
| 4 | Capability highlights | Module capabilities described without claiming external delivery or provider calls | PASS | L89–106 evidence-backed highlights; L51 "The core service does **not** send external messages"; L84 "No hosted AI or provider call is made by the core". |
| 5 | Architecture overview | Shared identity/workspace/permissions/event or timeline model; references `docs/architecture/` | PASS | L39–41 shared customer identity, workspace, permission, event spine; L79, L161–162 link `docs/architecture/MODULE_CONTRACT.md` and `CONTRACTS.md`. |
| 6 | Technology stack | Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite by default; vanilla JS light-theme web app | PASS | L168–175 table lists Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, SQLite default, "Vanilla JavaScript and CSS, light theme only"; L179 `apps/api/pyproject.toml`. |
| 7 | Local-first operation | Local SQLite, no required hosted account, API key or licence key; no native mobile apps claimed | PASS | L233–235 "No licence key, hosted account or API key is needed for local use"; L241–243 local SQLite/no telemetry; L177 "No native mobile apps". |
| 8 | Demo video section | Three local MP4s named with durations 00:03:12, 00:01:40 and 00:03:16; labelled local QA capture with synthetic data | PASS | L198–199 "Three real MP4 files were produced from local desktop screen recordings of the running application with synthetic data"; L203 `NOVARA_Product_Demo_2.0.mp4` `00:03:12`, L204 `NOVARA_Product_Demo_1.0.mp4` `00:01:40`, L205 `NOVARA_Complete_QA_Walkthrough.mp4` `00:03:16` labelled "QA Evidence Walkthrough"; L207–212 link `VIDEO_CHAPTER_INDEX.md`, `PRODUCT_DEMO_2_EVIDENCE.md` and `QA_EVIDENCE_WALKTHROUGH_1_1.md`; L213–214 deny per-feature acceptance and real customer/message/provider interaction. |
| 9 | Screenshot section | Any screenshots labelled local QA capture, not customer examples | PASS | L183–184 "genuine local QA captures using synthetic records, not interface concepts or fabricated data"; L186–191 screenshot links. |
| 10 | Quick start / run locally | Reproducible local start commands; no Docker requirement implied | PASS | L223–230 `.\scripts\start-local.ps1` and `sh scripts/start-local.sh`; L233 localhost first-run setup; Docker explicitly only "Prepared; container builds and runs unverified" at L249. |
| 11 | Prerequisites and configuration | Python 3.11+ and local setup documented; no secrets required | PASS | L218–219 Python 3.11+ and browser; L261–273 all `.env.example` variables optional; L280–281 "no provider credentials, API keys or outbound endpoints to configure". |
| 12 | API documentation entry point | Local API docs referenced (e.g. `/docs`); no hosted API claimed | PASS | L233–234 `http://localhost:8000/docs`; L321–327 local `/docs` and `curl http://localhost:8000/openapi.json`; L332–333 no external API key/hosted account. |
| 13 | Verification evidence | 1,488 rows / 1,418 VERIFIED_COMPLETE / 70 REPLACED; backend suite 1641 passed, 4 warnings in 1395.31s, EXIT=0; isolated QA 293 API PASS, 61 workflow records (52 PASS, 9 INFO, 0 FAIL), 17/17 security PASS, 50 routes, light theme only | PASS | L307 1,488 / 1,418 / 70; **L308 now reads "1,641 passed, 4 warnings in 1395.31s (0:23:15), exit 0"**; L309–312 293 API PASS, 61 (52/9/0), 17/17, 50 routes; L174 light theme only. Previously missing duration is now present. |
| 14 | Test reproduction commands | Commands and evidence paths given; no claim without a named file | PASS | L293–296 `python -m pytest apps/api/tests -q`, `node --check`; L305–312 each recorded result has a named evidence link; L317 `docs/TEST_RESULTS.md`. |
| 15 | Roadmap / current work | Forward work described as planned, not delivered | PASS | L411–419 priority counts "not progress percentages"; L421–425 "Next gates are evidence-gated module work", licence/domain/container/PostgreSQL/release decisions. |
| 16 | Known limitations | Container builds not verified, live PostgreSQL not verified, no native mobile apps, no outbound email/SMS/campaign delivery or hosted AI/provider calls executed | PASS | L249–251 unverified container builds/PostgreSQL, no native apps; L343–346 "No send endpoint", "Not executed by the core service"; L488–509 FAQ confirms each limit. |
| 17 | Release-readiness statement | Explicitly not a release candidate; no release tag or binary published | PASS | L15 "Not a release candidate"; L34 "No release tags or binaries have been published"; L450–451 "is not a release candidate and has no published installer, binary or release tag". |
| 18 | License and redistribution status | Exact wording "open-source foundation subject to final repository licensing review; licence file pending owner decision."; no "fully open source"; absence of root LICENSE acknowledged | PASS | L358–360 acknowledge no repository licence file and owner decision; **L362 exact blockquote "open-source foundation subject to final repository licensing review; licence file pending owner decision."**; L364 "Do not describe NOVARA as an openly licensed release"; FAQ L456–460 renamed and repeats exact phrase at L459. No occurrence of "fully open source" remains; no root `LICENSE` exists (verified locally). |
| 19 | Third-party notices | Links to `docs/research/LICENSE_COMPLIANCE.md` and `THIRD_PARTY_NOTICES.md`; states no source copied from the ten reference projects | PASS | L353–356 links both files and "No source code was copied or redistributed from the ten reference projects"; L538 repeats notices link. |
| 20 | Ten reference projects | Formbricks, Meilisearch, GrowthBook, Papermark, Plane, Mautic, Chatwoot, Novu, Marketing Skills, Sellbird — described as inspiration/functional alternatives only, no affiliation, no codebase redistribution | PASS | L531–534 names all ten as "functional alternatives and inspiration only", "no affiliation, partnership or endorsement", "no codebase … redistributed". |
| 21 | Documentation index | Links to key docs (status, install, QA, licensing, website plan) | PASS | Status L53/L436, install L237, QA L194/L312/L317, licensing L354; **L437 `docs/MARKETING_WEBSITE_PLAN.md`, L438 `docs/WEBSITE_CONTENT_CLAIMS_AUDIT.md`, L439 `docs/WEBSITE_HOSTING_GUIDE.md`**. Previously missing website-plan link is now present. |
| 22 | Repository structure | Brief layout description; does not imply published binaries or releases | PASS | L289–291 `apps/api/novara_core/`, `apps/web/`, `apps/api/novara_core/modules/`; L34 no published release tags or binaries. |
| 23 | Contributing | Links to `docs/COMMUNITY_CONTRIBUTION_PROGRAM.md`; human review; substantive contributions only | PASS | L395 link; L389–392 "substantive work under published criteria", "Review is human and evidence-based"; L401–407 adds privacy-conscious verification policy. |
| 24 | GitHub engagement policy | Stars/forks/watches are voluntary; no credits, tools, premium access, gifts or benefits in exchange; no automation; no gating; no implied GitHub endorsement | PASS | L441–443 "voluntary GitHub actions … no reward scheme … no automation, no feature gating and no implied endorsement"; L397–399 "no credits, tools, premium access or gifts"; L516–517. |
| 25 | Contributor identity verification | Optional GitHub OAuth with explicit consent, minimum scopes, secure server-side session, no unnecessary token storage, no passwords, account deletion controls; safe manual alternative; star is not a contribution | PASS | **L401–407** covers optional GitHub OAuth, "explicit consent", "minimum necessary scopes", "secure server-side session", "no unnecessary token storage", "no password collection", "account deletion and privacy controls", "safe manual verification path", "A star is never a qualifying contribution", human review and benefits only if "funded and approved". Previously missing criterion is now present. |
| 26 | Security, privacy and analytics | No analytics/tracking on site; no secrets in repo; responsible-disclosure channel described without claiming audits or certifications | PASS | Disclosure L368–370 via `docs/SECURITY_REPORT.md`; L375–376 "not a penetration test or finished audit"; no secrets L261/L280–281; **L383–385 "no analytics, tracking pixels, cookies, third-party scripts or secrets. It makes no external requests. This is a local preparation fact, not an audit or certification claim."** Previously missing no-analytics clause is now present. |
| 27 | Support, governance and owner authorization | Where to ask questions; no commit/push/tag/deploy without explicit owner authorization; "prepared locally, not published" | PASS | L432/L524 Discussions for questions; L300–301 "no commit, push, tag or deployment is part of this work"; L19 and L475 "not published", L540 "prepared locally". |

## Banned items — independent failure check

| # | Banned item | Why it is banned | Status | Evidence / reason |
| --- | --- | --- | --- | --- |
| B1 | Fake or projected star/fork/watch counts | Engagement figures are voluntary user actions and are not evidence of quality | PASS | No counts displayed; L441–443 describes stars/forks/watches as voluntary, L543 denies user/download/uptime figures. |
| B2 | Download, install or user counts | No such measured figures exist for this locally prepared project | PASS | No claimed figures; L223–230 gives install commands only, L543 explicitly denies "user counts, download counts". |
| B3 | Customer names, logos, quotes or testimonials | No customers or testimonials have been supplied or verified | PASS | L183 synthetic records, L213–214 "no real customer, message or provider interaction appears", L543 "No testimonials". |
| B4 | Uptime, availability or SLA figures | No hosted service or monitoring exists; Pages is not enabled | PASS | No uptime/SLA figures; L19–23 Pages "not published" / "not as a live site", L543 "no … uptime figures". |
| B5 | Unverified badges (build, coverage, security, release, licence badges) | Badges imply externally verified state; no root LICENSE or published pipeline exists | PASS | No badges present; L2 is a local wordmark image, not a status badge; no root `LICENSE` exists and L358 acknowledges this. |
| B6 | Misleading completion claims ("100% complete", "production ready", "release candidate", "fully open source") | Evidence shows active development, 70 replaced rows, no release, licence file pending | PASS | Terminology appears only in negation: L15 "Not a release candidate", L450 "is not a release candidate", L362/L459 exact licensing wording and L364 "Do not describe NOVARA as an openly licensed release"; FAQ heading renamed at L456. No occurrence of "fully open source", "100% complete" or asserted "production ready". |
| B7 | Claims of container, live PostgreSQL, native mobile, outbound delivery or hosted AI verification | Explicitly not verified or not present per the fact sheet | PASS | L249–251 builds/PostgreSQL unverified and no native apps; L343–346 no send endpoint/provider calls; L488–509 FAQ repeats each limitation. |
| B8 | Incentivised stars/follows or automated engagement | Prohibited by the GitHub engagement policy | PASS | L397–399 "no credits, tools, premium access or gifts", "no automation", "no feature is gated"; L441–443 voluntary and no endorsement; L405–407 star not qualifying and benefits only if funded/approved; L516–517. |

## Cross-document consistency checks

| Check | Status | Evidence / reason |
| --- | --- | --- |
| README status wording matches `MARKETING_WEBSITE_PLAN.md` and `WEBSITE_CONTENT_CLAIMS_AUDIT.md` | PASS | README L15/L17–23/L450–451 matches plan L24/L33/L148 and claims audit C4 L12 / C3 L11: active development, not a release candidate, Pages planned only. |
| Licensing wording matches `WEBSITE_CONTENT_CLAIMS_AUDIT.md` exactly | PASS | Claims audit C11 L19 and §3 L46 require the verbatim phrase; README **L362** and FAQ **L459** now contain exactly "open-source foundation subject to final repository licensing review; licence file pending owner decision."; L364 forbids describing NOVARA as an openly licensed release. |
| Contribution and verification wording matches `COMMUNITY_CONTRIBUTION_PROGRAM.md` | PASS | README L389–394 matches program L10–15/L31/L43 (substantive work, human review, no engagement rewards); **README L401–407** matches program §5 L67–77 (optional OAuth, explicit consent, minimum scopes, secure server-side session, no unnecessary tokens/passwords, deletion/privacy controls, manual fallback; human review decides and benefits require approval). |
| Video and screenshot labels match `WEBSITE_CONTENT_CLAIMS_AUDIT.md` | PASS | README L183–184 and L198–214 convey the same labelling as claims audit §4 L56–62: local QA capture, synthetic data, no customer footage. The claims audit's C9 L17 and §4 L58–61 enumerate the two older MP4s (1:40/3:16); README now also lists Product Demo 2.0 (00:03:12) at L203, labelled on the same basis at L198–199 and L213–214 and backed by `docs/QA/VIDEO_CHAPTER_INDEX.md` L3–8/L57–76, `docs/QA/PRODUCT_DEMO_2_EVIDENCE.md` L3–6/L30 and `docs/QA/QA_EVIDENCE_WALKTHROUGH_1_1.md` L3–12, so the extra video does not contradict the claims audit's labelling rules. |
| No claim in README appears without a named evidence file | PASS | Numeric claims map to named files at L307–312; qualitative claims link named docs at L108–109, L161–162, L348–349, L536–538; the previously missing duration was added at L308 with the named evidence link retained; the three videos and their evidence records are named at L203–205 and L207–212. |

## Result

**Publication gate: PASSED.** All 8 banned-item rows are PASS and there is no FAIL in the 27 required rows (27/27 PASS); all 5 cross-document consistency rows are also PASS. Final audited file: SHA-256 `e3b18389a81816e43006d1667a6eff3fe6bf6ba2330168f2cfc9ba6a6767b64c`, Git HEAD `73e9f76f6c8dd3360b73f7c5c8abec98726f28f8`, audited 2026-11-25. This is a **LOCAL audit only**: nothing was published, committed, pushed, tagged or deployed, and explicit owner authorization remains required before any README publication or Git operation.

No README file was created or edited by this audit; `README.md` was read and audited read-only.
