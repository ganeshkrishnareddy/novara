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

### 1. Identity and activity

- Public repository: <https://github.com/formbricks/formbricks>. README positions it as "The Open Source Qualtrics Alternative" and a "free and open source surveying platform" for in-app, website, link and email surveys (<https://github.com/formbricks/formbricks/blob/main/README.md>).
- Audited commit `845176cf3e72b68493e03b4350534b52a6defa07` on `main`, dated 2026-11-20. Star count 13,288 and classification NOASSERTION/Other come from `docs/research/REPOSITORY_AUDIT.md` (GitHub check recorded 2026-11-22 00:52 IST).
- Root `package.json` is a private pnpm/Turbo monorepo (`"version": "0.0.0"`); there is no single root release number. Release activity is visible in `.github/workflows/formbricks-release.yml`, `release-docker-github.yml` and `release-helm-chart.yml`.
- Exact open-issue, pull-request and contributor counts were **not verified**: the public GitHub API returned HTTP 403 on 2026-11-22. No metric is inferred from badges.

### 2. Features actually present in source

Advertised in the README: no-code survey editor with several question types, best-practice templates, in-app targeting without application code changes, shareable link surveys, team collaboration, and integrations with Slack, Notion, Zapier and n8n. These are product claims; the source checks below show what exists in the tree.

Verified in the audited source:

- `packages/database/schema/main.prisma` defines `enum SurveyType { link app }`, `enum displayOptions { displayOnce displayMultiple displaySome respondMultiple }`, and survey visibility modes `workspace` and `restricted`. Models include `Survey`, `SurveyTrigger`, `SurveyAttributeFilter`, `SurveyQuota`, `ResponseQuotaLink`, `Display`, `Response`, `Contact`, `ContactAttribute`, `ContactAttributeKey`, `Tag`, `ActionClass`, `Integration`, `Webhook`, `Workspace`, `Organization` and `Membership`.
- Survey delivery packages `packages/surveys` and `packages/survey-ui` are present; `packages/ai`, `packages/creatives` and `packages/workflows` add enrichment and workflow capability.
- API surface (section 5) includes survey, response, contact, dashboard and workflow resources.
- An MCP endpoint exists at `apps/web/app/api/mcp`.

Limitation: individual presets named "NPS" or "CSAT" were **not** enumerated as first-class types; the verified schema types are `link` and `app`, with question definitions inside the survey packages. Treat NPS/CSAT as a UI template claim, not a verified schema feature.

### 3. Frontend and backend technology

| Layer | Verified from repository manifests and tree |
|---|---|
| Front end | Next.js application at `apps/web` (`next dev`, `next build` scripts in `apps/web/package.json`), React, TailwindCSS, Radix UI, Lexical editor, dnd-kit, Zod, OpenTelemetry, Sentry and PostHog. |
| Back end | Next.js route handlers under `apps/web/app/api/`; no separate API server directory was found. Supporting services are workspace packages: `packages/database`, `packages/cache`, `packages/storage`, `packages/email`, `packages/ai`, `packages/jobs`, `packages/workflows`, `packages/creatives`, `packages/redis-config`. |
| Data/permissions | Prisma client (`@prisma/client`), PostgreSQL, and SpiceDB via `@authzed/authzed-node` for fine-grained relations. Cube.js client (`@cubejs-client/core`) for analytics. |
| Authentication | `@authjs`-style flows plus `@better-auth/core`, `@better-auth/oauth-provider` and BoxyHQ SAML (`@boxyhq/saml-jackson`, `@boxyhq/saml20`). |
| Tooling | pnpm + Turbo workspace; Vitest, Playwright, TypeScript; OpenAPI generation scripts in `apps/web/scripts/openapi`. |

All versions quoted above are declared in the public repository manifests.

### 4. Database schema and migrations

- PostgreSQL with Prisma. Four schema files under `packages/database/schema/`: `main.prisma`, `creatives.prisma`, `retention.prisma` and `workflows.prisma` (`main.prisma` is roughly two thousand lines).
- Versioned SQL migrations live under `packages/database/migration/`; 259 migration directories were counted at this commit. Migration scripts are exposed at the root (`db:migrate:dev`, `db:migrate:deploy`, `db:push`, `db:seed`).
- `enum OrganizationRole` = `owner`, `manager`, `member`, `billing`, `dashboard_viewer`; schema comments tie `dashboard_viewer` to a SpiceDB relation (ADR-0025). `enum ApiKeyPermission` = `read`, `write`, `manage`, applied per workspace through the `ApiKeyWorkspace` model.
- `docker-compose.dev.yml` shows the full local dependency set: PostgreSQL, SpiceDB plus migration/bootstrap services, Valkey (Redis-compatible), RustFS (S3-compatible object storage), MailHog, a `hub`/`hub-worker` pair with its own database, VLLM for local AI, and Cube for analytics.
- Exact index definitions and a full model inventory were **not** exhaustively parsed; the models listed in section 2 are the ones directly read.

### 5. API surface and integrations

- REST route handlers are Next.js `route.ts` files under `apps/web/app/api/`: `v1` (30 files), `v2` (24 files) and `v3` groups including `surveys`, `responses`, `contacts`, `contact-attribute-keys`, `dashboards`, `workflows`, `creatives`, `segments`, `tags`, `action-classes`, `charts`, `feedbackRecords`, `unify-feedback`, `gateway` and `workspaces`.
- Additional route groups: `auth`, `billing`, `client`, `google-sheet`, `internal`, `mcp`.
- OpenAPI artefacts are generated by `apps/web/scripts/openapi/generate.sh` and `merge-client-endpoints.ts`; CI workflows `api-v3-spec.yml` and `api-v3-contract-tests.yml` enforce the contract.
- Advertised integrations (Slack, Notion, Zapier, n8n) are README claims; the source verifies an `Integration`/`ActionClass`/`Webhook` model set, a `google-sheet` route and an MCP route. Per-vendor credentials and behaviour were not individually verified.

### 6. Reusable SDKs

- Root `LICENSE` names six MIT-licensed directories: `packages/js/`, `packages/android/`, `packages/ios/`, `packages/api/`, `packages/surveys/` and `packages/survey-ui/`.
- In the audited tree, manifest `license: MIT` was confirmed for `@formbricks/js-core` (`packages/js-core`), `@formbricks/surveys` (`packages/surveys`), `@formbricks/survey-ui` (`packages/survey-ui`), plus `@formbricks/i18n-utils`, `@formbricks/logger` and `@formbricks/vite-plugins`. `apps/web/package.json` also consumes the published `@formbricks/js` client (v5.0.0 as declared).
- Discrepancy noted: the `packages/js`, `android`, `ios` and `api` paths named in `LICENSE` were not all present under `packages/` at this commit; `js-core` is the present JavaScript core. Do not assume the named directories exist in every release — verify against the exact tag before depending on them.
- Reuse route: consume the published MIT client packages as dependencies, preserve their copyright and permission notices, and keep NOVARA's server code clean-room.

### 7. Installation and deployment

- Self-hosting documentation is under `docs/self-hosting/`: `overview.mdx`, `deployment-components.mdx`, `configuration.mdx`, `configuration/environment-variables.mdx`, `configuration/docker-storage.mdx`, `configuration/file-uploads.mdx`, `configuration/cdn.mdx`, `configuration/custom-ssl.mdx`, `configuration/custom-subpath.mdx` and `configuration/authzed-operations.mdx`.
- Helm charts exist at `charts/formbricks` and `charts/spicedb-operator`; CI validates and publishes them (`helm-chart-validation.yml`, `release-helm-chart.yml`). Docker images are built and published by `release-docker-github.yml` and `build-docker-candidate.yml`.
- A production self-host therefore requires PostgreSQL, SpiceDB, a Redis-compatible queue/cache, S3-compatible object storage and an SMTP provider; AI features add a model endpoint or provider. The default install must not depend on any of the enterprise services in `apps/web/modules/ee`.

### 8. Background jobs and events

- `packages/jobs` contains `queue.ts`, `processors.ts`, `definitions.ts`, `recurring.ts`, `schedules.ts`, `runtime.ts`, `connection.ts` and `upgrade.ts`, each with colocated tests (for example `schedules.test.ts`, `processors.test.ts`). `packages/workflows` provides survey-triggered workflows.
- The Prisma schema models asynchronous side effects through `Webhook` with a `WebhookSource` enum, `SurveyTrigger`, `ActionClass`, `Integration`, and `OutboundEmailAudit` plus `OutboundEmailAuditErasureIntent` for email auditing and erasure requests.
- Valkey is the queue/cache backing service in the development compose stack. Job throughput, success rates and latency were **not** measured; no performance metric is claimed.

### 9. Authentication and permissions

- Local accounts and sessions are modelled by `Account`, `Session`, `VerificationToken`, `TwoFactor` and `jwks` in `main.prisma`; authentication uses `@better-auth/*` and BoxyHQ SAML components.
- Fine-grained authorisation is delegated to SpiceDB (`@authzed/authzed-node`), with backfill/outbox scripts (`authzed:backfill`, `authzed:outbox`) and operations documentation in `docs/self-hosting/configuration/authzed-operations.mdx`.
- Coarse roles are the `OrganizationRole` enum (`owner`, `manager`, `member`, `billing`, `dashboard_viewer`); API keys are workspace-scoped with `read`/`write`/`manage` permission levels; survey visibility is `workspace` or `restricted`.
- Enterprise-only auth features live under `apps/web/modules/ee/sso`, `ee/two-factor-auth`, `ee/role-management`, `ee/teams` and `ee/audit-logs` (section 11).

### 10. Tests, CI and limitations

- Unit tests use Vitest (`apps/web` scripts `test` and `test:coverage`, plus `vitest.integration.config.mts`). End-to-end tests use Playwright under `apps/web/playwright`.
- CI workflows include `lint.yml`, `typecheck.yml`, `test.yml`, `integration-tests.yml`, `e2e.yml`, `api-v3-contract-tests.yml`, `api-v3-spec.yml`, `sonarqube.yml`, `container-security.yml` and `docker-security-scan.yml`.
- Audit limitations: a single commit was inspected, so history, contributor counts and long-term cadence were not analysed. No tests were executed. Feature presence was determined by reading files and routes, not by running the application. Star count is taken from the earlier recorded API check because the live API call failed with HTTP 403.

### 11. Enterprise-only and gated features

Everything under `apps/web/modules/ee/` is carved out of AGPL by the root licence. Directories present at this commit: `ai-translation`, `analysis`, `audit-logs`, `auth`, `billing`, `contacts`, `creatives`, `data-retention`, `feedback-directory`, `license-check`, `mailing`, `quotas`, `role-management`, `sso`, `teams`, `two-factor-auth`, `unify-feedback`, `whitelabel` and `workflows`.

Enforcement is implemented in `apps/web/modules/ee/license-check/` (`actions.ts`, `lib/license.ts`, `lib/lite-license.ts`, `lib/contacts-api-guard.ts`, `lib/recheck-authorization.ts`). Self-host guidance is in `docs/self-hosting/advanced/license.mdx` and `license-activation.mdx`.

Practical effect: SSO, teams, role management, two-factor auth, audit logging, quotas, white-labelling, data retention and contact/creative/workflow extras are **not** available under the community licence. Code presence in the public tree is not a grant of production rights.

### 12. Actual licence terms, attribution and redistribution

- Root `LICENSE` (<https://github.com/formbricks/formbricks/blob/main/LICENSE>): "Copyright (c) 2024 Formbricks GmbH". AGPLv3 applies to all content outside the named carve-outs; the six MIT directories listed in section 6 are excluded, as is `apps/web/modules/ee`.
- AGPLv3 §13 requires an offer of Corresponding Source to users interacting with the software over a network. Copying Formbricks server code into a network-served NOVARA would trigger that obligation.
- EE licence (<https://github.com/formbricks/formbricks/blob/main/apps/web/modules/ee/LICENSE>): "Copyright (c) 2020-present Formbricks GmbH". Production use requires the Formbricks Subscription Terms (<https://formbricks.com/terms>) **and** a valid Enterprise licence for the correct number of seats. Copying, merging, publishing, distributing, sublicensing and selling are forbidden; development/testing copies are allowed; modifications remain Formbricks' property; the full EE text must accompany copies.
- Attribution: MIT packages require preservation of the copyright notice and permission text. Any consumed SDK must be recorded in `THIRD_PARTY_NOTICES.md`; no third-party source was copied into NOVARA by this task.

### 13. External dependencies and costs

- Advertised pricing observed 2026-11-22: Community Edition free; a hosted free plan; Experience Suite and managed cloud are quote-only (<https://formbricks.com/pricing>). These are page claims, not verified invoices or entitlements.
- Self-host cost drivers: PostgreSQL, SpiceDB, Valkey, S3-compatible storage, SMTP delivery, compute for the Next.js app and workers, and an optional AI/model endpoint. CDN and custom domains appear in configuration docs.
- Commercial third-party components declared in `apps/web/package.json` include AWS SDKs, PostHog, Sentry and BoxyHQ SAML. Each carries its own licence and possible service cost; a per-dependency legal inventory was **not** completed by this audit.

### 14. Reuse decision

**Clean-room implement; reuse only MIT client packages.** Do not copy AGPL-licensed Formbricks server code into NOVARA because §13 would attach a network source offer to the combined work. The published MIT survey client packages may be consumed as dependencies under their notices, and a NOVARA adapter may speak Formbricks' public REST/API contract to a separately installed instance if a self-hosted survey engine is ever needed. Exclude `apps/web/modules/ee` entirely and do not design any NOVARA feature that requires an EE entitlement in the default install.

### 15. Implications for NOVARA modules

- Fits the surveys, NPS/CSAT, feedback and in-app micro-survey modules.
- Embed through a NOVARA-owned survey runtime or the MIT JS client; do not expose a second Formbricks login to end users.
- Map NOVARA workspace and role context onto the external API key/workspace scope (roles `read`/`write`/`manage`); keep external IDs in a link table on the NOVARA workspace record.
- Publish every response and display event to the NOVARA event spine with a common envelope; feed response analytics into the shared analytics model rather than a Formbricks-only dashboard.
- Enterprise-only capabilities (SSO, teams, audit logs, quotas, white-labelling, retention) must be either implemented natively in NOVARA or explicitly declared out of scope — not assumed available.

---

## 2. meilisearch/meilisearch

### 1. Identity and activity

- Public repository: <https://github.com/meilisearch/meilisearch>. README describes a "search engine for fast, relevant full-text, semantic, and hybrid search" (<https://github.com/meilisearch/meilisearch/blob/main/README.md>).
- Audited commit `9a44a8e825f20a028f80d1c7f76ff2a146e743e7` on `main`, dated 2026-11-19. Star count 59,951 and classification NOASSERTION/Other come from `docs/research/REPOSITORY_AUDIT.md` (GitHub check 2026-11-22 00:52 IST).
- `Cargo.toml` declares workspace version `1.57.0`, homepage `https://meilisearch.com`, edition 2021 and `license = "MIT"` for the workspace package, with the overall repository SPDX expression `MIT AND OpenLDAP AND BUSL-1.1` in `LICENSE`.
- Activity signals: the repository has dedicated CI for benchmarks, flaky tests, SDK tests, OpenAPI checks, Docker image publication and release assets (`.github/workflows/`). Exact issue, PR and contributor counts were **not verified** — the public GitHub API returned HTTP 403 on 2026-11-22.

### 2. Features actually present in source

Advertised in the README: hybrid (semantic + full-text) search, search-as-you-type, typo tolerance, filtering and faceted search, sorting, synonyms, geosearch, broad language support, API-key security, multi-tenancy via tenant tokens, RESTful API, conversational search, personalisation, search rules, document relations, replication/sharding, LangChain and MCP support.

Verified in the audited source:

- Full-text and vector search code in `crates/milli/src/search/` and `crates/milli/src/vector/`; filtering, facets, field maps, snapshots and sharding under `crates/milli/src/`.
- HTTP routes under `crates/meilisearch/src/routes/` including `indexes/` (documents, search, settings, facet_search, similar, fields), `tasks`, `batches`, `dump`, `snapshot`, `export`, `metrics`, `logs`, `multi_search`, `webhooks`, `mcp` and `chat_completions`.
- Federated/multi-search and experimental search-rule code under `crates/meilisearch/src/search/federated/` and `crates/milli/src/dynamic_search_rules/`.
- Indexing is asynchronous: the README quick start warns to retry after indexing; the task system is implemented in `crates/index-scheduler/` and task kinds in `crates/meilisearch-types/src/tasks/mod.rs` include `DocumentAdditionOrUpdate`, `SettingsUpdate`, `IndexCreation`, `IndexDeletion`, `DumpCreation` and `SnapshotCreation`.

Availability caveat: sharding, S3-streaming snapshots, search-rule previews and network/leader features are advertised but flagged Enterprise Edition in source (section 11). They are present in the tree but **not** usable in production under the community licence.

### 3. Frontend and backend technology

| Layer | Verified from repository files |
|---|---|
| Core engine | Rust 2021 workspace (`Cargo.toml`) with crates `meilisearch`, `milli`, `index-scheduler`, `meilisearch-types`, `meilisearch-auth`, `file-store`, `dump`, `routes`, `permission...` equivalents, plus vendored `external-crates/async-openai`. |
| Storage | LMDB through the `heed` connector; the repository licence adds the OpenLDAP license for that connector. No SQL database is used by the engine. |
| API | HTTP server with generated OpenAPI artefacts; workflows `check-openapi-file.yml` and `openapi-generator` crate keep the spec in sync. |
| Search internals | `crates/milli/src/` modules: `documents`, `facet`, `search`, `vector`, `snapshots`, `sharding`, `update`, `dynamic_search_rules`. |
| Integrations | Native MCP route (`crates/meilisearch/src/routes/mcp.rs`), chat completions, analytics export routes, LangChain support documented in the README. |
| Packaging | `Dockerfile`, published Docker images, APT/Brew packages, install script, and Cloud deployment. |

### 4. Database schema and migrations

- Meilisearch is a document store over LMDB; there is no SQL schema and no relational migration system in the audited tree. Data is organised into indexes and documents, with settings persisted per index.
- Persistence and recovery mechanisms are files and snapshots: `crates/milli/src/snapshots/`, `crates/dump/`, `crates/file-store/`, and environment options `MEILI_DB_PATH`, `MEILI_IMPORT_SNAPSHOT`, `MEILI_SNAPSHOT_DIR`, `MEILI_IGNORE_MISSING_SNAPSHOT` read from `crates/meilisearch/src/option.rs`.
- Schema-like structure is code-defined in `crates/meilisearch-types/src/` (task and setting types). Exact on-disk key layout and index definitions were **not** reverse-engineered; no claim is made about internal record format.

### 5. API surface and integrations

- REST API under `/indexes`, `/tasks`, `/batches`, `/multi-search`, `/export`, `/dump`, `/snapshot`, `/metrics`, `/logs`, `/webhooks`, `/mcp` and `/chats`, implemented across `crates/meilisearch/src/routes/`.
- API keys and tenant tokens are documented security features; the master key is configured with `MEILI_MASTER_KEY` (`crates/meilisearch/src/option.rs`) and key management is implemented in `crates/meilisearch/src/routes/api_key.rs` with the store in `crates/meilisearch-auth/src/store.rs`.
- Webhooks are configurable with `MEILI_TASK_WEBHOOK_URL` and `MEILI_TASK_WEBHOOK_AUTHORIZATION_HEADER` (`option.rs`; route in `routes/webhooks.rs`).
- Official SDKs are advertised for JavaScript, Python, PHP, Ruby, Go, Rust and React/Instant Meilisearch, with a full integration list in the documentation (<https://www.meilisearch.com/docs/learn/what_is_meilisearch/sdks>).
- AI integrations: native MCP server at `/mcp` (marked experimental in the README), LangChain vector-store support, conversational search and a published `llms.txt`.

### 6. Reusable SDKs

- Engine clients are separate repositories, not vendored here. The README quick start links JavaScript, Python, PHP, Ruby, Go, Rust and React SDK guides; the integration list covers more frameworks and CMS/platform plugins.
- The in-repository `external-crates/async-openai` and `external-crates/async-openai-macros` are MIT-licensed forks vendored with modifications to use the shared HTTP client; README section "External crates" names them explicitly.
- The engine's HTTP API is stable and versioned, so the lowest-risk reuse path for NOVARA is a clean-room client adapter using an official SDK against a separately installed OSS engine. Individual SDK licences were **not** separately verified; they must be checked before redistribution.

### 7. Installation and deployment

- Community Edition: self-host the MIT engine. README quick start uses `docker run -p 7700:7700 -v <data>:/meili_data getmeili/meilisearch:latest`, or a binary via the install script, or local/Cloud install guides.
- Configuration is environment-driven: `MEILI_ENV`, `MEILI_HTTP_ADDR`, `MEILI_DB_PATH`, `MEILI_MASTER_KEY`, `MEILI_NO_ANALYTICS`, SSL certificate/key options, snapshot and dump paths, and task webhook settings are all declared in `crates/meilisearch/src/option.rs`.
- Meilisearch Cloud is the managed alternative (no servers to maintain; monitoring, analytics and team management added). Cloud regions include Frankfurt and Paris with an EU sovereign option, per README FAQ.
- Production hardening, TLS, backup/snapshot strategy and resource sizing must be handled by the operator; no default K8s chart is present in this repository.

### 8. Background jobs and events

- `crates/index-scheduler/` owns the asynchronous task queue: modules `queue`, `scheduler`, `index_mapper`, `dynamic_search_rules` and `upgrade`, plus `enterprise_edition/` for sharding/network and S3 snapshots.
- Task types in `crates/meilisearch-types/src/tasks/mod.rs` include document additions/updates, settings updates, index creation/deletion, dumps and snapshots. Tasks are persisted and observable through `/tasks` and `/batches`.
- Event hooks: task webhooks via `MEILI_TASK_WEBHOOK_URL`; per-index analytics routes (`search_analytics.rs`, `multi_search_analytics.rs`, `mcp_analytics.rs`, and others) expose usage data.
- Operational limits, throughput benchmarks and queue latency were **not** measured; benchmark workflows exist but no results are asserted here.

### 9. Authentication and permissions

- `MEILI_MASTER_KEY` bootstraps the instance; API keys are created and scoped through `/keys` with action and index restrictions (`crates/meilisearch/src/routes/api_key.rs`, `crates/meilisearch-auth/src/`).
- Multi-tenancy is supported through signed tenant tokens, allowing per-tenant document filtering on a shared index (README feature list and documentation link).
- Search rules, network/leader topology and federated `useNetwork` paths carry explicit EE checks in source (section 11).
- No end-user account system exists in the engine: identity must be supplied by the calling application, which is a good fit for NOVARA's shared identity model.

### 10. Tests, CI and limitations

- Integration test suites live under `crates/meilisearch/tests/` with directories for `auth`, `documents`, `search`, `settings`, `index`, `vector`, `similar`, `dumps`, `snapshot`, `tasks`, `network`, `dynamic_search_rules`, `upgrade`, `batches`, `stats`, `logs` and others.
- CI includes `test-suite.yml`, `flaky-tests.yml`, `sdks-tests.yml`, `check-openapi-file.yml`, `db-change-comments.yml`, `db-change-missing.yml`, benchmark workflows and `fuzzer-indexing.yml`.
- Limitations: one commit was inspected; no tests were executed; historical cadence, contributor counts and live issue counts were not verified (GitHub API HTTP 403). Benchmarks are workflow definitions only — no performance number is claimed.

### 11. Enterprise-only and gated features

There is no single top-level enterprise directory. EE code is marked in file headers and resides across the crate tree. Files explicitly labelled "This file is part of Meilisearch Enterprise Edition" at this commit include:

- `crates/index-scheduler/src/dynamic_search_rules/enterprise_edition.rs`
- `crates/index-scheduler/src/scheduler/enterprise_edition/mod.rs`, `network.rs`, `s3.rs`
- `crates/meilisearch/src/proxy/enterprise_edition.rs`
- `crates/meilisearch/src/routes/network/enterprise_edition.rs`
- `crates/meilisearch/src/search/federated/network/enterprise_edition.rs`
- `crates/meilisearch-types/src/enterprise_edition/mod.rs`, `network.rs`
- `crates/meilisearch-types/src/tasks/network/enterprise_edition.rs`
- `crates/milli/src/dynamic_search_rules/preview/enterprise_edition.rs`
- `crates/milli/src/sharding/enterprise_edition.rs`

Source errors confirm gating: `crates/index-scheduler/src/error.rs` defines `"{action} requires the Enterprise Edition"`, and tests in `crates/meilisearch/tests/dynamic_search_rules/` assert messages such as "Meilisearch Enterprise Edition is required to use `inlineRule`". README EE section lists sharding, S3-streaming snapshots and search-rule previews. These features are **not** available for production without a commercial agreement.

### 12. Actual licence terms, attribution and redistribution

- Root `LICENSE` (<https://github.com/meilisearch/meilisearch/blob/main/LICENSE>): "Copyright (c) 2019-2025 Meili SAS"; SPDX `MIT AND OpenLDAP AND BUSL-1.1`. Community code is MIT; the LMDB connector (`heed`) carries the additional OpenLDAP Public License 2.8 (<https://github.com/meilisearch/meilisearch/blob/main/LICENSE-OPENLDAP>).
- EE licence (<https://github.com/meilisearch/meilisearch/blob/main/LICENSE-EE>): Business Source License 1.1 adapted for Meili SAS. It covers files explicitly marked Enterprise Edition or governed by BUSL. Additional Use Grant permits use, modification and distribution for **non-production purposes only** (testing, development, evaluation). Production use requires a commercial licence agreement with Meilisearch. Change Licence is MIT; Change Date is four years from publication of each version.
- Attribution: MIT and OpenLDAP notices must be preserved when redistributing community code or binaries that include the LMDB connector. No EE file may be vendored into NOVARA.
- Pricing and licence pages: <https://www.meilisearch.com/pricing>, <https://www.meilisearch.com/cloud>.

### 13. External dependencies and costs

- Advertised 2026-11-22: Meilisearch Cloud from USD 20/month with additional disk and bandwidth charges; a 14-day trial is offered (<https://www.meilisearch.com/pricing>). These are advertised figures, not verified invoices.
- Self-host cost drivers: compute and storage for the engine, backups/snapshots, TLS/domain infrastructure, and the optional Cloud service. Sharding and S3 snapshots add multi-node and object-storage cost and require EE.
- Vendored external crates (`external-crates/async-openai`, `external-crates/async-openai-macros`, `external-crates/reqwest-eventsource`) are MIT with modifications; AI features that call external model providers may incur provider charges. Per-provider pricing was not verified.

### 14. Reuse decision

**Reuse through the public API/SDK against a separately installed OSS engine.** NOVARA should implement its own thin search adapter (index mapping, query translation, event publication) using an official client, and operate the MIT-licensed engine as an external service. Do not vendor the engine, do not use EE code, and do not make Meilisearch Cloud a default dependency. Keep the adapter clean-room so an alternative engine can be substituted.

### 15. Implications for NOVARA modules

- Fits the universal search module across datasets, records, reports and help content.
- Supply NOVARA workspace/role context as API-key scoping and tenant tokens; never create a separate end-user account store in the search layer.
- Publish query, click and indexing events to the NOVARA event spine with the common envelope; add usage facts to the shared analytics model.
- Keep hybrid/semantic search optional: it may require an embedding/model provider and therefore a disclosed cost and a local fallback.
- Treat sharding, S3 snapshots, network topology and search-rule previews as out of scope for the default install because they are EE/Commercial.

---

## 3. growthbook/growthbook

### 1. Identity and activity

- Public repository: <https://github.com/growthbook/growthbook>. Landing page title: "Open Source Feature Flags, Experimentation, and Product Analytics" (<https://github.com/growthbook/growthbook>).
- Audited commit `fc116c6e41e5e0ebe98bcbad6d3092bceb45ae14` on `main`, dated 2026-11-20. Star count 8,639 and classification NOASSERTION/Other come from `docs/research/REPOSITORY_AUDIT.md` (GitHub check 2026-11-22 00:52 IST).
- Root `package.json` declares `growthbook-app` v5.2.0, `"license": "Mixed"`, a pnpm workspace, TypeScript and a Node engine floor; the site headline at audit time was "GrowthBook 5.2 — Interleaving and Human in the Loop for agents".
- The pricing page claims "Trusted by 4,000+ companies worldwide" — an **advertised marketing claim**, verified only as page text. Exact issue, PR and contributor counts were **not verified** because the public GitHub API returned HTTP 403 on 2026-11-22.

### 2. Features actually present in source

Advertised: feature flags and remote config, experimentation, product analytics, visual editor, bandits, interleaving and human-in-the-loop agent features.

Verified in the audited source tree:

- Flag CRUD, environments, revisions and SDK-connection revisions; payload delivery through `/api/sdk-payload/:key`.
- Experimentation: A/B tests, holdouts, interleavings, multi-armed and contextual bandits, ramp schedules, sequential testing, CUPED/variance reduction, Bayesian and frequentist engines, SRM detection and post-stratification — implemented in `packages/stats` (Python `gbstats`) and query runners under `packages/back-end/src/`.
- Analytics: metrics (proportion, mean, ratio, funnel, retention, quantile), fact tables, dimensions, segments, populations, saved groups, SQL explorer, metric groups and discovery queries.
- Product analytics dashboards, insights and exec reports are present in front-end components.
- Warehouse-native, read-only SQL against BigQuery, Snowflake, Redshift, PostgreSQL, MySQL, MSSQL, Athena, ClickHouse, Databricks, Presto and Vertica, plus Google Analytics, Mixpanel and Adobe Experience Platform integrations under `packages/back-end/src/integrations/`.
- Event delivery: event webhooks, SDK webhooks, Slack notifier and global webhook fan-out.
- Management: organisations, projects, teams, templates, code references, dbt sync and audit logs.

Reality check: many of these features exist in code but are gated by the commercial feature map (section 11). "Present in tree" does not mean "available on the OSS plan".

### 3. Frontend and backend technology

| Layer | Verified from repository manifests and docs |
|---|---|
| Front end | Next.js and React with Radix UI, ECharts, visx, Lexical and Tiptap editors; Vitest for front-end tests. |
| Back end | Express with Mongoose and the MongoDB driver; Agenda job queue; Stripe; Python bridge for statistics; OpenTelemetry and Sentry. |
| Statistics | `packages/stats` uses Python with pandas, scipy, numpy and pydantic; CI pins the Python version. |
| Shared | `packages/shared` holds types, permissions and the enterprise feature map (`"license": "Mixed"`). |
| SDKs in repo | `packages/sdk-js` (`@growthbook/growthbook`, MIT, no runtime dependencies) and `packages/sdk-react`. |
| Deployment shape | Self-host docs describe a Next.js front end, an Express API and a Python stats engine bundled in one Docker image. |

Versions quoted above are declared in the public repository manifests and CI configuration.

### 4. Database schema and migrations

- Primary store is MongoDB. `docker-compose.yml` uses a MongoDB service with `MONGODB_URI` and a persistent uploads volume.
- Schema is defined in code by roughly one hundred Mongoose model files under `packages/back-end/src/models/` — for example `ExperimentModel`, `FeatureModel`, `MetricModel`, `OrganizationModel`, `UserModel`, `WebhookModel`, `SSOConnectionModel`, `TeamModel` and revision/fact-table models. There is no SQL DDL.
- Migrations are just-in-time document upgrades in `packages/back-end/src/util/migrations.ts` (legacy experiment snapshots, feature v1→v2, metric overrides, organisation roles, encryption of data-source parameters, analysis-key backfills). No separate versioned migration table or SQL migration tool was found.
- Agenda shares the same MongoDB connection for job state. Production self-host docs recommend a managed MongoDB-compatible service rather than the bundled container.
- Caveat: schema enforcement is application-level; an exact model/index inventory was **not** exhaustively parsed.

### 5. API surface and integrations

- REST API mounted at `/api/v1` and `/api/v2` in `packages/back-end/src/api.router.ts`; a public spec is served at `/v1/openapi.yaml` and generated into `docs/openapi.yaml`. CI enforces that generation produces no diff.
- Around forty route modules cover features, experiments, metrics, dimensions, fact tables, data sources, SDK connections and payloads, webhooks, queries, snapshots, segments, projects, organisations, members, teams, dashboards, contextual bandits, interleavings and holdouts. Some endpoints depend directly on enterprise-backed models.
- Data-source integrations: Athena, BigQuery, ClickHouse, Databricks, Google Analytics, Mixpanel, MSSQL, MySQL, PostgreSQL, Presto, Redshift, Snowflake, SQL integration, Vertica and Adobe Experience Platform Query Service.
- Documented event trackers include Amplitude, CleverTap, custom, Firebase, Freshpaint, FullStory, Heap, Jitsu, Keen IO, Langfuse, mParticle, Phoenix, Segment and Snowplow.
- Delivery integrations: Slack notifier, webhooks, SDK streaming updates, CDN/cache purge, GrowthBook Proxy Server, dbt sync, REST API, MCP server and Agent Skills.

### 6. Reusable SDKs

- Twenty-four SDKs are advertised, covering JavaScript, React, Next.js, Vue, Node, React Native, Python, Go, Java, Kotlin/JVM, Android Kotlin, Swift, Flutter, PHP, Ruby, Rust, C#, Elixir, Roku, script tag, OpenFeature, edge and build-your-own.
- `packages/sdk-js` (`@growthbook/growthbook` v2.2.0, MIT) has no external dependencies, performs local targeting/evaluation with no HTTP requests, supports namespaces for mutually exclusive experiments, remote configuration and visual experiments. Its README claims 100% test coverage; that claim was **not** independently re-measured.
- Local evaluation is broadly available. Remote evaluation, SDK streaming updates and encrypted SDK endpoints are commercial features (section 11).
- Only `sdk-js` and `sdk-react` live in this monorepo; individual licences of the other SDKs were **not** verified.

### 7. Installation and deployment

- Quickstart uses `docker-compose.yml` with a `growthbook/growthbook` service (front end on one port, API on another) and a MongoDB service, with uploads persisted in a volume.
- A single container image bundles the Next.js front end, Express API and Python stats engine; a hardened non-root distroless image is published. The `latest` tag tracks `main`.
- Configuration is environment-driven: `APP_ORIGIN`, `API_HOST`, `MONGODB_URI` and many others are documented under `docs/self-host/env.mdx`; front end and back end must use distinct ports on one domain. The full variable list was **not** enumerated.
- Production guidance covers Kubernetes/Helm, CDN, proxy, remote evaluation, FerretDB as an alternative store, configuration and hardening. JIT migrations reduce manual database steps; automated backup/restore tooling was **not** verified.

### 8. Background jobs and events

- Agenda, backed by MongoDB, is the scheduler (`packages/back-end/src/services/queueing.ts`). Jobs run with a system request context.
- Around thirty job files under `packages/back-end/src/jobs/` include experiment-result and metric refresh, webhooks, SDK webhooks, licence updates, information-schema creation, scheduled features and proxy updates.
- Webhook fan-out queues per-connection deliveries, fires global SDK webhooks, purges the CDN cache and queues proxy updates. Event handlers for Slack and webhooks live under `events/handlers/`.
- OpenTelemetry instrumentation and trace ingestion are initialised at server start. Job success rates and SLAs were **not** measured.

### 9. Authentication and permissions

- Local email/password accounts, organisations, personal access tokens and API keys are available in community code.
- SSO is OIDC only, and self-hosted SSO requires an active licence key; source enforces this by throwing when SSO configuration is present without the `sso` entitlement. Generic OIDC, Okta, Google and Azure AD are documented.
- RBAC uses permission policies mapped to atomic permissions, with default roles such as `noaccess`, `readonly`, `collaborator`, `engineer`, `analyst`, `admin`, plus project-admin and visual-editor variants. Custom roles and teams are gated.
- Gated auth capabilities include `sso`, `scim`, `custom-roles`, `role-management`, `advanced-permissions`, `teams`, `multi-org`, `no-access-role`, `project-admin-role` and `require-approvals`.
- Air-gapped licence keys are supported with a 14-day expiration grace. No built-in MFA or password-policy controls were verified.

### 10. Tests, CI and limitations

- CI jobs cover formatting, licence checks, type-aware lint, Python statistics lint/tests, OpenAPI generation cleanliness, TypeScript type-check, sharded Jest back-end tests (with a MongoDB test version pinned in CI), Vitest front-end tests and package tests.
- `scripts/check-licenses.mjs` scans the installed production dependency tree against an allow-list with case-by-case exceptions (for example LGPL-3.0 `sharp-libvips` and MPL-2.0 `resvg-wasm`).
- Limitations: one commit was inspected; no tests were executed; coverage figures beyond the sdk-js README claim are not verified. GitHub API HTTP 403 prevents live issue/PR/fork statistics. Pricing comparison tables are rendered as icon images, so entitlement availability was inferred from plan text plus the source feature map, not machine-readable cells.

### 11. Enterprise-only and gated features

Authoritative source: `packages/shared/src/enterprise/license-consts.ts`. Plans are `oss | starter | pro | pro_sso | enterprise`, with roughly eighty named commercial features.

- `oss` has **zero** commercial features.
- `pro` (~36 features) includes advanced permissions, role management, encrypted feature endpoints, scheduled flags, sequential testing, visual editor, remote evaluation, sticky bucketing, code references, prerequisites, redirects, quantile/retention/funnel/compound metrics, metric populations, multi-armed bandits, safe rollouts, ramp schedules, precomputed dimensions, product-analytics dashboards and cluster experiments.
- `pro_sso` adds SSO. `enterprise` adds roughly forty more, including AI suggestions, unlimited projects, custom environments, SCIM, audit logging, post-stratification, multi-org, teams, custom roles, approvals, holdouts, metric effects/correlations, incremental refresh, contextual bandits, interleaving, releases and human-in-the-loop.
- `licenseUtil.ts` contacts the default licence server `https://central-license-server.growthbook.io/api/v1/`; self-hosted instances without a licence resolve to the `oss` plan. SSO and multi-org throw explicit errors without entitlement.
- Conclusion: the OSS plan covers the core flag/experiment stack but none of the commercial features. Advanced statistics, bandits, no-code editing, enterprise auth and analytics dashboards require Pro or Enterprise even when self-hosted.

### 12. Actual licence terms, attribution and redistribution

- Root `LICENSE` (<https://github.com/growthbook/growthbook/blob/main/LICENSE>): MIT (Expat), "Copyright (c) 2025 GrowthBook, Inc." — use, copy, modify, merge, publish, distribute, sublicense and sell are permitted with the attribution clause.
- Carve-out: `packages/back-end/src/enterprise`, `packages/front-end/enterprise` and `packages/shared/src/enterprise` are excluded from MIT and governed by the GrowthBook Enterprise License (<https://github.com/growthbook/growthbook/blob/main/packages/back-end/src/enterprise/LICENSE>). Production use requires compliance with the Subscription Terms (<https://www.growthbook.io/terms>) **and** a valid Enterprise or Pro licence for the correct number of seats. Copying, merging, publishing, distributing, sublicensing and selling are forbidden; development/testing copies and modifications are allowed but rights remain with GrowthBook; the full licence text must accompany copies.
- Other MIT packages include `packages/stats` and `packages/remote-saved-groups-csv-parser`, each with its own copyright notice.
- Customer Agreement highlights (fetched 2026-11-22): limited, revocable, non-transferable internal-use right during the subscription term; restrictions on circumventing plan limits, competitive analysis, shared logins and benchmark publication; automatic annual renewals with notice; California law and Santa Clara County venue; liability cap of the lesser of twelve months' fees or USD 100,000; broad feedback licence; GrowthBook rights in aggregated data and use of customer data to improve AI algorithms. Legal review is required before relying on it.
- Practical effect: the MIT grant covers the bulk of the codebase, but licensing the enterprise directories for production is a contractual obligation, and redistribution of a build containing them is restricted.

### 13. External dependencies and costs

- Advertised 2026-11-22 (<https://www.growthbook.io/pricing>): Open Source self-host free with one project and community support; Cloud Starter free up to three users and one project; Cloud Pro USD 40/seat/month up to thirty users and three projects; Enterprise custom pricing. Metered add-ons include managed warehouse and event forwarder (USD 30 per million events after included tiers), CDN requests (USD 10 per million) and CDN bandwidth (USD 1/GB). These are advertised prices, not verified invoices.
- Self-host cost drivers: a managed MongoDB-compatible cluster, container compute for the bundled image, warehouse compute for read-only SELECT queries, CDN/cache/proxy infrastructure, object storage for uploads, and a paid GrowthBook licence for any gated feature.
- Licence-server egress to the default endpoint (or a valid air-gapped key) is part of operating a licensed self-hosted instance. Stripe, Sentry, OpenTelemetry, Slack and warehouse drivers add further dependencies; per-dependency licences are automated by the repository's licence check, not enumerated here.

### 14. Reuse decision

**Reuse via public API/SDK; clean-room the evaluation core.** NOVARA may consume the MIT JavaScript/React SDKs under their notices and may speak GrowthBook's public API to a separately installed OSS instance. Do not vendor or redistribute the three enterprise directories. Do not depend on Pro/Enterprise features in the default install. If unified flag evaluation is needed inside NOVARA's own engine, implement it clean-room rather than copying GrowthBook's evaluation code.

### 15. Implications for NOVARA modules

- Fits feature flags, remote config, A/B experimentation and product analytics.
- Core free capability: flag CRUD, kill switch, percentage rollout, targeting, archiving/history, basic metrics, fact tables, SQL explorer, SRM and Bayesian/frequentist analysis with local SDK evaluation.
- Advanced statistics (sequential testing, CUPED, post-stratification), bandits, interleaving, holdouts, visual editor, remote evaluation/streaming, advanced RBAC, SSO/SCIM, audit logs and dashboards are **commercial** — implement natively in NOVARA or declare out of scope.
- Map NOVARA workspace roles onto GrowthBook organisations/projects; keep external IDs in a link table and avoid a second end-user login.
- Publish flag exposure and experiment assignment events to the NOVARA event spine and write metric facts into the shared analytics model.
- Treat the vendor's compliance claims (SOC 2, GDPR, HIPAA/BAA, SLA) as cloud/enterprise claims that do not transfer to a self-hosted NOVARA deployment.

---

## Cross-cutting integration decisions

1. **No whole-application embedding.** Every repository mixes a permissive or copyleft community core with separately licensed enterprise code. NOVARA must integrate capabilities, not embed three applications behind one navigation. The `docs/VISION.md` rule "one product, not ten" and "do not copy and paste code blindly" is reinforced by the license texts: Formbricks community core is AGPL-3.0 with a network source offer (§13), Meilisearch EE is BUSL-1.1 with no production use without a commercial agreement, and both Formbricks EE and GrowthBook Enterprise forbid copying or redistribution.
2. **Adapters over forks.** The viable reuse path is a thin, clean-room adapter in NOVARA that speaks the public REST/SDK contract of an externally installed engine (Meilisearch OSS binary, optional self-hosted GrowthBook, optional Formbricks instance for survey delivery). The MIT-licensed Formbricks client packages and GrowthBook SDKs may be consumed as dependencies with their copyright and permission notices preserved in `THIRD_PARTY_NOTICES.md`; no third-party source is vendored into NOVARA by this task.
3. **Shared identity, not three logins.** All three projects implement their own user, workspace/organisation and permission records. NOVARA adapters must translate one NOVARA identity and workspace role set into the external system's scoped API key or service account; they must never create a second user database or require separate end-user sign-in. Any external account IDs belong in a link table on the NOVARA workspace/user record.
4. **One event spine.** Survey responses, search queries/analytics and flag exposure/experiment events must be published to NOVARA's internal event bus with a common envelope (workspace, actor, subject, timestamp, source module, correlation ID). The upstream tools' own analytics are a supplement, not the system of record. This is what makes the founder's cross-module flows (form → CRM → campaign → notification → task) possible.
5. **One analytics model.** GrowthBook metrics and Formbricks response analytics must write dimensionally compatible facts into NOVARA's analytics store (workspace, user, customer, date, module). Meilisearch usage events should follow the same convention. No module-specific reporting silo.
6. **No paid dependency in the default install.** Self-hosted NOVARA must not require Formbricks EE, Meilisearch Cloud/Enterprise, GrowthBook Pro/Enterprise, an external data warehouse or an LLM API. Where an optional service is used, the UI must disclose its price and keep the local path functional. Published prices observed 2026-11-22: Meilisearch Cloud from USD 20/month with disk and bandwidth charges (<https://www.meilisearch.com/pricing>); GrowthBook Cloud Pro USD 40/seat/month and a free Starter tier (<https://www.growthbook.io/pricing>); Formbricks Experience Suite and managed cloud are quote-only, with Community Edition free (<https://formbricks.com/pricing>). These are advertised prices, not verified invoices or entitlements.
7. **Open question for the owner.** NOVARA's own licence is not yet chosen. Until it is, AGPL-3.0 code from Formbricks must not be combined into NOVARA's codebase; the survey capability should be clean-room implemented or reached through the public API. See `docs/research/LICENSE_COMPLIANCE.md`.
