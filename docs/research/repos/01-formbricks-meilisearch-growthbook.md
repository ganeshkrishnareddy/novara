# Deep repository audit — Formbricks, Meilisearch, GrowthBook

Task T-003. Research only: no application code was written, no third-party source was copied into NOVARA, and nothing was published by this task.

Verified 2026-11-22 from the public GitHub source trees at the commits named below, plus each repository's README/docs and the license texts. Repository references use paths relative to each repository root; URLs are public. Repository metadata (stars, language, default branch) is cross-referenced with `docs/research/REPOSITORY_AUDIT.md`, which records a GitHub API check at 2026-11-22 00:52 IST.

## Scope and sources

| Repository | Commit audited (default branch `main`) | Commit date | Stars (2026-11-22 00:52 IST) | GitHub classification |
|---|---|---|---:|---|
| `formbricks/formbricks` | `845176cf3e72b68493e03b4350534b52a6defa07` | 2026-11-20 | 13,288 | NOASSERTION / Other |
| `meilisearch/meilisearch` | `9a44a8e825f20a028f80d1c7f76ff2a146e743e7` | 2026-11-19 | 59,951 | NOASSERTION / Other |
| `growthbook/growthbook` | `fc116c6e41e5e0ebe98bcbad6d3092bceb45ae14` | 2026-11-20 | 8,639 | NOASSERTION / Other |

Public sources: <https://github.com/formbricks/formbricks>, <https://github.com/meilisearch/meilisearch>, <https://github.com/growthbook/growthbook>. License files are cited by repository-relative path and public URL in section 12 of each repository.

**Terminology.** "Advertised" is a claim in a README, docs site or product page. "Verified" means the feature, file, route or clause was read in the source tree at the commit above. Where a feature could not be confirmed in source, this report says so explicitly.

## Executive summary

| Repository | Community license (actual text) | Enterprise split | Recommendation | NOVARA module |
|---|---|---|---|---|
| Formbricks | AGPL-3.0 for most code; MIT for six SDK/client packages | `apps/web/modules/ee` — Formbricks Enterprise License, seat-based, production requires subscription, no redistribution | Clean-room implement the survey runtime; reuse only the MIT SDK packages under API/embed terms; exclude EE | Surveys, NPS/CSAT, feedback |
| Meilisearch | MIT core plus OpenLDAP for the LMDB connector; BUSL-1.1 for EE files | Files marked Enterprise Edition across `crates/` — production use requires a commercial license, converts to MIT four years after publication | Reuse via public API/SDK against a separately installed OSS engine; do not vendor EE; keep client adapter clean-room | Universal search |
| GrowthBook | MIT Expat for community code | `packages/back-end/src/enterprise`, `packages/front-end/enterprise`, `packages/shared/src/enterprise` — GrowthBook Enterprise License, seat-based, no redistribution | Reuse via public API/SDK; clean-room implement flag/experiment evaluation for the unified engine; exclude EE | Feature flags, experiments, product analytics |

Cross-cutting implications for NOVARA: none of these three repositories supports copying a whole application into a unified, network-served product without license consequences (AGPL §13 for Formbricks community code, BUSL production restriction for Meilisearch EE, commercial subscription terms for both enterprise splits). A single NOVARA identity and permission model must not be forked into per-module logins; the survey, search and experimentation adapters should consume NOVARA's workspace/role context and publish events to one internal event bus. Analytics from these modules must feed shared customer/workspace records rather than separate reporting silos.

---

## 1. formbricks/formbricks

_PLACEHOLDER_FORMBRICKS_

---

## 2. meilisearch/meilisearch

_PLACEHOLDER_MEILISEARCH_

---

## 3. growthbook/growthbook

_PLACEHOLDER_GROWTHBOOK_

---

## Cross-cutting integration decisions

1. **No whole-application embedding.** Every repository mixes a permissive or copyleft community core with separately licensed enterprise code. NOVARA must integrate capabilities, not embed three applications behind one navigation. The `docs/VISION.md` rule "one product, not ten" and "do not copy and paste code blindly" is reinforced by the license texts: Formbricks community core is AGPL-3.0 with a network source offer (§13), Meilisearch EE is BUSL-1.1 with no production use without a commercial agreement, and both Formbricks EE and GrowthBook Enterprise forbid copying or redistribution.
2. **Adapters over forks.** The viable reuse path is a thin, clean-room adapter in NOVARA that speaks the public REST/SDK contract of an externally installed engine (Meilisearch OSS binary, optional self-hosted GrowthBook, optional Formbricks instance for survey delivery). The MIT-licensed Formbricks client packages and GrowthBook SDKs may be consumed as dependencies with their copyright and permission notices preserved in `THIRD_PARTY_NOTICES.md`; no third-party source is vendored into NOVARA by this task.
3. **Shared identity, not three logins.** All three projects implement their own user, workspace/organisation and permission records. NOVARA adapters must translate one NOVARA identity and workspace role set into the external system's scoped API key or service account; they must never create a second user database or require separate end-user sign-in. Any external account IDs belong in a link table on the NOVARA workspace/user record.
4. **One event spine.** Survey responses, search queries/analytics and flag exposure/experiment events must be published to NOVARA's internal event bus with a common envelope (workspace, actor, subject, timestamp, source module, correlation ID). The upstream tools' own analytics are a supplement, not the system of record. This is what makes the founder's cross-module flows (form → CRM → campaign → notification → task) possible.
5. **One analytics model.** GrowthBook metrics and Formbricks response analytics must write dimensionally compatible facts into NOVARA's analytics store (workspace, user, customer, date, module). Meilisearch usage events should follow the same convention. No module-specific reporting silo.
6. **No paid dependency in the default install.** Self-hosted NOVARA must not require Formbricks EE, Meilisearch Cloud/Enterprise, GrowthBook Pro/Enterprise, an external data warehouse or an LLM API. Where an optional service is used, the UI must disclose its price and keep the local path functional. Published prices observed 2026-11-22: Meilisearch Cloud from USD 20/month with disk and bandwidth charges (<https://www.meilisearch.com/pricing>); GrowthBook Cloud Pro USD 40/seat/month and a free Starter tier (<https://www.growthbook.io/pricing>); Formbricks Experience Suite and managed cloud are quote-only, with Community Edition free (<https://formbricks.com/pricing>). These are advertised prices, not verified invoices or entitlements.
7. **Open question for the owner.** NOVARA's own licence is not yet chosen. Until it is, AGPL-3.0 code from Formbricks must not be combined into NOVARA's codebase; the survey capability should be clean-room implemented or reached through the public API. See `docs/research/LICENSE_COMPLIANCE.md`.
