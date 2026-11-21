# Repository audit — Papermark, Chatwoot, Novu (T-004)

Verified 2026-11-22 IST. Sources: live GitHub repository metadata, `README.md`, `LICENSE*` files, manifests, schemas, route/controller trees and deployment files on each repository's default branch; repository URLs are given per section. This is research only — no source was copied into NOVARA, nothing was published and no external system was changed. Facts that could not be confirmed from source are marked *unverified*.

## 1. `papermark/papermark`

Source: https://github.com/papermark/papermark (default branch `main`). All paths below are relative to that repository.

### 1.1 Identity, default branch, language, activity
- Open-source "DocSend alternative": secure document sharing, viewer tracking, custom domains, data rooms. Organization-owned, created 2023-05-29.
- Default branch `main`; primary language TypeScript; 9,441 stars, 1,448 forks, 241 open issues at audit time.
- Last push 2026-08-28 — materially staler than the other audited projects; freshness and maintenance capacity need caution. GitHub classifies the licence as `NOASSERTION` because of the mixed AGPL/commercial scheme (see 1.12).
- Source: GitHub REST API `repos/papermark/papermark`, verified 2026-11-22.

### 1.2 Actual features verified from source/docs
- **Advertised in `README.md`:** shareable links, custom branding/domain, document tracking analytics, self-hosting; "page-by-page analytics" is described as *soon*.
- **Verified in source:** documents and versions/pages (`prisma/schema/document.prisma`), links and visitor groups (`prisma/schema/link.prisma`), views/reactions/feedback/agreements (`prisma/schema/schema.prisma`), data-room models (`prisma/schema/dataroom.prisma`), viewer/visit capture (`app/api/views/route.ts`, `app/api/views/pages/route.ts`, `app/api/views-dataroom/route.ts`), cron jobs (`app/api/cron/`), outgoing/incoming webhooks (`lib/webhook/`, `lib/incoming-webhooks/`), AI chat and workflows (`app/(ee)/api/ai/`, `app/(ee)/api/workflows/`).
- **Enterprise boundary:** `ee/README.md` lists Data Rooms, Q&A conversations and Advanced Permissions as Enterprise Edition features, even though data-room *models* exist in the community Prisma schema. Treat the AGPL code and the EE feature set as different scopes; do not assume every model has a community UI.
- Page-by-page analytics UX is only partially verifiable (models + a `views/pages` route exist; README still calls it upcoming).

### 1.3 Frontend/backend technologies
- `package.json`: Next.js 14.2.35 (mixed Pages Router under `pages/` and App Router under `app/`), React 18.3.1, TypeScript, Tailwind CSS 3.4, shadcn/ui + Radix, TanStack Table, tRPC not present.
- Backend: Next.js route handlers/pages API, Prisma 6.5.0 ORM, PostgreSQL, Zod validation, NextAuth.js v4.
- Manifest declares Node `>=24`; `README.md` says Node `>=18.17.0` — conflicting requirements, resolve before any build.

### 1.4 Database schema and migrations summary
- Prisma schema split across 12 files under `prisma/schema/`: `schema`, `document`, `link`, `dataroom`, `team`, `conversation`, `annotation`, `brand`, `integration`, `notification`, `oauth`, `workflow`, `jackson` (SSO/Jackson tables). ~71 models in total, including `Document`, `DocumentVersion`, `DocumentPage`, `Link`, `View`, `Viewer`, `Dataroom`, `ViewerGroup`, `PermissionGroup`, `Team`, `UserTeam`, `Workflow`, `WorkflowStep`.
- `prisma/migrations/` contains 126 SQL migration directories; `npm run dev:prisma` runs `prisma generate && prisma migrate deploy`.
- PostgreSQL is required; Vercel Postgres/Blob are the documented defaults but self-hosted Postgres and S3-compatible storage are supported via environment variables.

### 1.5 API endpoints and integrations
- Pages Router API groups under `pages/api/`: `account`, `agreements`, `analytics`, `auth`, `conversations`, `feedback`, `file`, `internal`, `jobs`, `links`, `teams`, `webhooks`, plus view/click/reaction/video routes.
- App Router groups under `app/api/`: `views`, `views-dataroom`, `cron`, `webhooks`, `integrations/slack/oauth`, `feature-flags`, `og`, `verify`, `csp-report`.
- Enterprise API groups under `app/(ee)/api/`: `ai/chat`, `ai/store`, `auth/saml`, `scim`, `faqs`, `workflows`, `workflow-entry`, `teams/.../datarooms/.../freeze`.
- Webhook triggers are explicit in `lib/webhook/constants.ts`: `document.created/updated/deleted`, `dataroom.created`, `link.created/updated/deleted/viewed/downloaded`; signatures in `lib/webhook/signature.ts`.
- `package.json` declares a `generate:openapi` script; no generated public OpenAPI document or published client SDK was verified in the audited tree (*unverified*). Integration surface is primarily internal HTTP routes + webhooks, not a stable versioned external API.

### 1.6 Reusable SDKs/libraries
- No general-purpose public SDK verified. Reusable *components* exist as source: webhook payload Zod schemas (`lib/zod/schemas/webhooks.ts`), RBAC helper (`lib/api/rbac/permissions.ts`), link/session helpers (`lib/auth/link-session.ts`), file conversion and PDF tooling in `lib/trigger/`. All are licence-bound (AGPL or commercial) and should not be copied into NOVARA.

### 1.7 Installation and deployment requirements
- `README.md`: Node, PostgreSQL, blob storage (AWS S3 or Vercel Blob), Resend for email; clone, `npm install`, copy `.env.example`, `npm run dev:prisma`, `npm run dev`.
- `.env.example` additionally requires secrets for NextAuth, document-password encryption, verification URLs, Upstash QStash + Redis (queues/locks), Hanko passkeys (optional), Tinybird analytics token, Vercel domain automation variables, and AWS/CloudFront credentials when using S3.
- Tinybird setup uses its CLI plus `lib/tinybird/` datasources/pipes; `vercel.json` and Vercel-oriented variables show the project is optimised for Vercel even though self-hosting is advertised.

### 1.8 Background jobs and event system
- Trigger.dev v4 (`trigger.config.ts`, `lib/trigger/`, `ee/**/lib/trigger/`) handles async work: file conversion, PDF/image/video processing, bulk downloads, visit exports, dataroom notifications, cleanup, billing reminders and AI indexing.
- Upstash QStash + cron routes under `app/api/cron/` (dataroom digests, domain checks, welcome/year-in-review emails); Redis-backed job stores (`lib/redis-job-store.ts`, `lib/redis/dataroom-notification-queue.ts`).
- Event surface: outgoing webhook triggers listed in 1.5, signed webhook delivery, incoming webhook handlers at `pages/api/webhooks/services/[...path]/index.ts`.

### 1.9 Authentication and permissions model
- `lib/auth/auth-options.ts`: NextAuth with Google, LinkedIn, email magic links, Hanko passkeys and BoxyHQ SAML (`@boxyhq/saml-jackson`); Prisma adapter.
- `lib/api/rbac/permissions.ts`: roles `ADMIN`, `MANAGER`, `MEMBER`, `DATAROOM_MEMBER` mapped to fine-grained verbs such as `datarooms.read`, `documents.write`, `analytics.team`, `members.write`, `sso.write`; `DATAROOM_MEMBER` is scoped further by per-room entitlement checks (`lib/api/rbac/entitlements.ts`, `lib/dataroom/apply-permissions.ts`).
- Viewer-side security: link passwords/email verification, restricted tokens, document password encryption key, signed webhooks.

### 1.10 Tests, coverage and known limitations
- No `test` script in `package.json` and no `*.spec.*`/`*.test.*` files were found in the audited tree: automated test coverage appears absent (*unverified as a formal claim; no test evidence found*).
- Known limitations from source/docs: last push 2026-08-28; conflicting Node requirements; Vercel/Tinybird/Upstash dependencies make a fully offline, beginner-friendly install non-trivial; page-by-page analytics still described as upcoming.

### 1.11 Enterprise-only functionality
- `ee/features/` contains: access-notifications, AI, billing, conversations, conversions, dataroom-freeze, dataroom-invitations, permissions, security, storage, templates, workflows. `app/(ee)/` mirrors EE API routes (SAML, SCIM, AI, workflows).
- `ee/README.md` explicitly names Data Rooms, Q&A conversations and Advanced Permissions as hosted/enterprise features and warns against hosting a competing app from this code without a licence.

### 1.12 Actual LICENSE terms, attribution and redistribution
- Root `LICENSE`: Copyright (c) 2023-present Papermark, Inc. Content outside `ee/` and `app/(ee)/` is **AGPL-3.0**; those two directories are under the commercial licence in `ee/LICENSE.md`. This mixed scheme explains GitHub's `NOASSERTION`.
- AGPL obligations: preserve copyright/licence notices, licence modified works as AGPL, provide Corresponding Source, and — for modified versions used over a network — offer users source access (AGPL §13). Attribution via the "how to apply" notice in each source file.
- `ee/LICENSE.md`: production use requires a signed agreement and a valid Enterprise Edition subscription for the correct number of hosts; copying, merging, publishing, distributing, sublicensing and selling are prohibited; Papermark retains title to modifications/patches. It also states that client-side JS/CSS/images/fonts produced from commercial source become AGPLv3.
- **Implication:** the commercial directories cannot be vendored into NOVARA, and AGPL files cannot be merged into a differently-licensed product without meeting copyleft obligations.

### 1.13 External dependencies and their costs
- Self-hostable/free: PostgreSQL, S3-compatible object storage.
- Commercial or usage-priced services referenced in `.env.example`: Vercel Blob/domains/hosting, Tinybird (analytics), Resend (email), Upstash QStash and Redis, Trigger.dev (jobs), Stripe (payments), Hanko (passkeys), Google/LinkedIn OAuth (free tiers), AWS S3/CloudFront. Current prices were not verified; check each vendor's pricing page before choosing. No claim about specific amounts is made here.

### 1.14 Recommendation — **clean-room implement** (exclude code reuse)
- Reason: AGPL-3.0 network copyleft on the core plus a commercial `ee/` tree make copying code into a unified NOVARA distribution a legal and architectural hazard; the repository is also less active than peers. The useful patterns (share links, per-viewer analytics, granular room ACLs) can be reimplemented independently. Public webhook payload shapes in `lib/zod/schemas/webhooks.ts` may be used as an interoperability reference only, not copied.

### 1.15 NOVARA module and cross-module implications
- Informs the **Documents / Data Rooms / Secure Sharing** module: link-scoped documents, viewer sessions, view/download events, per-object permission groups.
- Must use NOVARA's single identity and workspace model rather than NextAuth roles; map `ADMIN/MANAGER/MEMBER/DATAROOM_MEMBER` concepts into NOVARA's own RBAC. View/download events must flow into the shared event bus so a "proposal viewed" event can notify the assigned salesperson and write to the customer timeline.

---

## 2. `chatwoot/chatwoot`

Source: https://github.com/chatwoot/chatwoot (default branch `develop`, stable releases on `master`/`v1.x` tags). Paths below are repository-relative.

### 2.1 Identity, default branch, language, activity
- "Open-source live-chat, email support, omni-channel desk" positioned as an Intercom/Zendesk alternative. Created 2019-08-14.
- Default branch `develop` (git-flow); primary language Ruby; 40,298 stars, 9,812 forks, 1,630 open issues at audit time.
- Last push 2026-11-20 — active. GitHub licence classification is `NOASSERTION` because of the MIT + commercial `enterprise/` split (see 2.12).

### 2.2 Actual features verified from source/docs
- **Advertised and source-verified in community code:** website live chat widget, email/facebook/instagram/twitter/telegram/line/SMS/WhatsApp channels (`db/schema.rb` channel_* tables and channel gems in `Gemfile`), shared inbox, contacts/companies, conversations and messages, labels, canned responses, custom attributes, teams, CSAT, dashboards/reports, help centre/portals/articles, automation rules, agent bots, webhooks, dashboard apps.
- Captain AI (assistants, documents, FAQ suggestions, copilot/MCP tools) is present in core routes under `config/routes.rb` (`namespace :captain`) with LLM gems in `Gemfile`; **Convergence/monitors are explicitly enterprise-gated** in `config/routes.rb` via `if ChatwootApp.enterprise?` (`resources :monitors`).
- Source: `README.md`, `config/routes.rb`, `db/schema.rb`, `Gemfile`. Exact feature-by-feature paywall boundary beyond the `enterprise/` directory is *unverified*.

### 2.3 Frontend/backend technologies
- `Gemfile`: Ruby 3.4.13, Rails 8.0.5.2, Puma, PostgreSQL (`pg`), Redis, Sidekiq, Active Storage (S3/Azure/GCS), Action Mailbox, OpenSearch/Searchkick, pgvector.
- `package.json`: Vue 3.5, Vite 6.4.2, Pinia/Vuex, Tailwind CSS, TypeScript tooling, Vitest 3.0.5; version 4.20.1; pnpm 10.x declared.
- Auth gems: Devise, devise_token_auth, devise-two-factor, JWT, Pundit; authorization also via `audited`, `administrate` (super admin).

### 2.4 Database schema and migrations summary
- `db/schema.rb` is an ActiveRecord dump (`ActiveRecord::Schema[7.1].define(version: 2026_11_16_211055)`) containing **112 tables**, including `accounts`, `users`, `account_users`, `contacts`, `conversations`, `messages`, `inboxes`, `channel_*` tables, `teams`, `labels`, `automation_rules`, `campaigns`, `csat_survey_responses`, `custom_roles`, `portals`, `articles`, `webhooks`, `notifications`, `integration_hooks`, `captain_*`, `copilot_*` and enterprise-related monitors/SLA tables.
- `db/migrate/` holds Rails migrations; `db/seeds.rb` seeds sample data. Schema load via `bin/rails db:schema:load` is the fast path for a fresh database (per the file's own header).

### 2.5 API endpoints and integrations
- `swagger/index.yml` is OpenAPI 3.1.0; a full generated spec is checked in as `swagger/swagger.json`. Tags cover Platform, Application, Client (public), Help Center, CSAT and others.
- Route families in `config/routes.rb`: `/api/v1/...` (account-scoped application API), `/platform/api/v1/...` (accounts, users, agent bots), `/public/api/v1/inboxes/...` (widget/contact/conversation/message APIs), `/survey/responses/...`, `/auth` (Devise token auth), `/health`, `/api`.
- Authentication in `swagger/index.yml`: bearer tokens for user, agent-bot and platform-app (available from v4.19.0); legacy `api_access_token` header supported but slated for deprecation.
- Integrations declared in README/Gemfile: Slack, Dialogflow, Shopify, Linear, Google Translate, Twilio, Meta channels, Telegram, Line,email ingress (Mailgun/Mandrill/Postmark/Sendgrid/SES), plus generic webhooks.

### 2.6 Reusable SDKs/libraries
- Chatwoot publishes a JavaScript SDK built from `vite.lib.config.ts` (`pnpm build:sdk`, size-limited to 40 KB) and a widget bundle; `@chatwoot/*` packages (utils, prosemirror-schema, viz, pico-search) are dependencies.
- Consumers should use the documented REST API + webhooks; no reason to vendor Rails/Vue source into NOVARA.

### 2.7 Installation and deployment requirements
- README documents Heroku one-click, DigitalOcean 1-click Kubernetes, Docker, Helm (Artifact Hub) and a deployment page; repository includes `docker-compose.yaml`, `docker-compose.production.yaml`, `Procfile*` and `.devcontainer/`.
- `.env.example` requires `SECRET_KEY_BASE`, Postgres host/user/password, `REDIS_URL`/password, `FRONTEND_URL`, mailer sender and SMTP settings; optional OpenSearch URL/keys, inbound-email service credentials, CDN host, encryption keys for MFA, `CW_API_ONLY_SERVER`, and numerous channel/AI keys.
- Advanced search needs OpenSearch/Elasticsearch; AI/Captain needs an LLM provider configured in Super Admin.

### 2.8 Background jobs and event system
- Sidekiq 7.3 + `sidekiq-cron` for scheduled work; `sidekiq_alive`, `speedshop-cloudwatch` (opt-in), ActiveJob/ActionCable for realtime.
- `wisper` pub/sub gem is present for domain events; `webhooks` table plus webhook APIs deliver events externally; `integrations_hooks` and `automation_rules` tables support rule-driven actions and third-party hooks.

### 2.9 Authentication and permissions model
- Devise + devise_token_auth (`mount_devise_token_auth_for 'User'` in `config/routes.rb`), Devise secure password, two-factor auth, JWT, SAML/Google OAuth via OmniAuth, optional GitHub strategy.
- Pundit policies (`app/policies/`, `enterprise/app/policies/`); roles/permissions backed by `account_users`, `custom_roles`, `agent_bots`, `platform_app_permissibles` tables; super admin via Administrate. API tokens are scoped by user/agent-bot/platform-app type.

### 2.10 Tests, coverage and known limitations
- Testing stack is real: RSpec (`rspec-rails`, `factory_bot_rails`, `simplecov`, `webmock`, `database_cleaner`) for Ruby and Vitest with `@vitest/coverage-v8` for JS (`pnpm test`, `pnpm test:coverage`); CI badge on CircleCI.
- Coverage percentages and pass rates were not executed/verified here — *unverified*.
- Limitations: very large codebase and 1,630 open issues; heavy runtime requirements (Ruby, Rails, Postgres, Redis, Node, optional OpenSearch); enterprise features gated separately.

### 2.11 Enterprise-only functionality
- `enterprise/` contains `app/`, `config/`, `lib/`, `LICENSE` and `tasks_railtie.rb`; `enterprise/app/` includes controllers, jobs, models, policies, services, listeners, mailers and views.
- `config/routes.rb` shows at least one explicit enterprise gate: conversation monitors. SSO/advanced compliance features are commonly enterprise in this product, but the precise list is *unverified* from the audited files.

### 2.12 Actual LICENSE terms, attribution and redistribution
- Root `LICENSE`: Copyright (c) 2017-2026 Chatwoot Inc.; everything outside `enterprise/` is **MIT Expat**. MIT requires the copyright and permission notice in all copies or substantial portions; no copyleft.
- `enterprise/LICENSE`: production use requires compliance with Chatwoot Subscription Terms and a valid Enterprise License **per user seat**; copy/merge/publish/distribute/sublicense/sell prohibited; Chatwoot retains title to modifications; development/testing use without a subscription is allowed. Third-party components keep their own licences.
- **Implication:** the MIT core can be reused with attribution; the `enterprise/` tree cannot be redistributed or used in production without a licence.

### 2.13 External dependencies and their costs
- Self-hostable/free core: PostgreSQL, Redis, Puma, optional OpenSearch, S3/Azure/GCS storage.
- Usage-priced/third-party: Twilio and other channel carriers, Meta/WhatsApp business messaging, LLM APIs for Captain/copilot, Google Translate/Dialogflow, Slack, Shopify, Stripe (billing), Sentry/Datadog/New Relic/Scout APM (optional), hosting on Heroku/DigitalOcean. Specific prices were not verified; check vendor pricing pages.

### 2.14 Recommendation — **reuse via public API/SDK** for channel connectivity; **clean-room implement** the shared inbox and UI
- Reason: MIT core permits attribution-based reuse, and the OpenAPI 3.1 spec plus bearer-token API make integration clean; but a Rails/Vue monolith cannot be embedded in NOVARA's unified stack, and the `enterprise/` tree is licensed. Prefer API/webhook interoperability and reimplement the conversation model natively.

### 2.15 NOVARA module and cross-module implications
- Informs the **Support / Shared Inbox / Omnichannel Conversations** module: channel adapters, conversation timeline, CSAT, automation rules, help centre.
- Must map contacts and conversations into NOVARA's existing CRM identity (no second user store), emit shared events on message/reply/CSAT, and reuse NOVARA permissions instead of Pundit roles. Incoming webhooks must be authenticated and rate-limited under NOVARA's own controls.

---

## 3. `novuhq/novu`

Source: https://github.com/novuhq/novu (default branch `next`). Paths below are repository-relative.

### 3.1 Identity, default branch, language, activity
- Described as "the open-source communication infrastructure for agents and products": one API/unified conversation model for Inbox, Email, SMS, Push, Chat (Slack, Teams, Telegram, WhatsApp, etc.). Created 2021-08-26.
- Default branch `next`; primary language TypeScript; 40,399 stars, 4,565 forks, 103 open issues at audit time.
- Last push 2026-11-21 — active. GitHub licence `NOASSERTION` because of the MIT/proprietary open-core split (see 3.12).

### 3.2 Actual features verified from source/docs
- **Advertised and source-verified in MIT/core code:** multi-channel notification API, workflow engine with branching/conditions and digests, embeddable `<Inbox />` (`packages/js`, `packages/react`), subscriber preferences, no-code editor (`libs/maily-*`), 20 email / 37 SMS / 8 push / 13 chat providers listed in `README.md` with source folders under `packages/providers/src/lib/`, event triggers (`apps/api/src/app/events/`), Agent Communication Infrastructure packages (`packages/agent-inbox`, `packages/agent-toolkit`, `packages/agent-event-protocol`, `apps/agent-inbox-mcp`, `apps/mcp-server`).
- Core API surface is broad: 43 NestJS controllers under `apps/api/src/app/` covering events, workflows-v1/v2, subscribers-v1/v2, inbox, integrations, messages, notifications, topics-v1/v2, preferences, feeds, layouts, environments, webhooks, bridge, auth, organization and user.
- The managed cloud service ("Create a free account") is separate from self-hosting and is not required by the MIT core (*deployment details below*).

### 3.3 Frontend/backend technologies
- Nx/pnpm monorepo (`nx.json`, `pnpm-workspace.yaml`); TypeScript 6.0.3; NestJS 11 for `apps/api`, `apps/worker`, `apps/ws`, `apps/webhook`, `apps/inbound-mail`; React dashboard apps.
- Data: MongoDB via Mongoose 8 (`libs/dal/package.json`); Redis + BullMQ (`libs/application-generic/src/services/bull-mq/`); S3-compatible storage; JWT auth via Passport.
- Apps present: `api`, `worker`, `ws`, `webhook`, `inbound-mail`, `dashboard`, `human-dashboard`, `mcp-server`, `agent-inbox-mcp`.

### 3.4 Database schema and migrations summary
- No relational schema. `@novu/dal` uses Mongoose models/collections (subscribers, workflows, jobs, messages, integrations, environments, organizations, members, preferences, topics, layouts, feeds, notifications, execution details).
- `apps/api/migrations/` contains ad-hoc data/encryption migration scripts (e.g. `encrypt-api-keys`, `encrypt-credentials`, `expire-at`, `dedupe subscribers`, `subtopic normalization`) with adjacent `*.spec.ts` tests — not a declarative migration framework.
- `MONGO_AUTO_CREATE_INDEXES=true` in `docker/community/.env.example`: indexes are created at runtime rather than via checked-in DDL. This matters for operational control and upgrades.

### 3.5 API endpoints and integrations
- `apps/api/src/app/*/**.controller.ts` (43 controllers) plus generated client `@novu/api` in `libs/internal-sdk/package.json`; `apps/api/exportOpenAPIJSON.ts` exports an OpenAPI document.
- Public SDKs: `@novu/api` (generated API client), `@novu/js` (Inbox UI core), `@novu/react`, `@novu/react-native`, `@novu/framework` (code-first workflow SDK), `@novu/nextjs`, CLI `@novu/novu`, `packages/agent-toolkit`, `apps/mcp-server`.
- Provider integrations: 78 provider folders across Email/SMS/Push/Chat/In-App as enumerated in `README.md`; inbound parsing via `apps/inbound-mail` and `apps/api/src/app/inbound-parse/`.

### 3.6 Reusable SDKs/libraries
- Strongest reuse candidate set in this audit: `@novu/api`, `@novu/js`, `@novu/react`, `@novu/framework`, `@novu/stateless`, `@novu/providers` (provider adapters), `libs/maily-*` (email editor/render). These are published packages for integrators.
- Licence caveat: package manifests mark some as `ISC`; the repository-level MIT grant covers non-enterprise code, while `enterprise/packages/*` is proprietary (3.12). Verify package-level licences before redistribution.

### 3.7 Installation and deployment requirements
- `docker/community/docker-compose.yml` defines MongoDB 8.0.17, Redis, and the `api`, `worker`, `ws`, `web`, `webhook`, `inbound-mail` services (container images `ghcr.io/novuhq/novu/*:3.19.0`); health checks and depends-on conditions are included. A local S3 stack (`S3_LOCAL_STACK`) is used for storage in the sample environment.
- `docker/community/.env.example` requires `JWT_SECRET`, `STORE_ENCRYPTION_KEY` (32 chars), `NOVU_SECRET_KEY`, Mongo credentials/URL, Redis host/port/password, S3 settings and ports (API 3000, WS 3002, worker 3004). Optional Sentry/New Relic settings, idempotency/rate limiting flags and `IS_SELF_HOSTED=true`.
- Self-hosting is viable but requires multiple services; NOVARA's "one installation" goal must hide this complexity behind its own installer/service manager.

### 3.8 Background jobs and event system
- BullMQ queues in `libs/application-generic/src/services/queues/`: standard, workflow, web-sockets, subscriber-process, inbound-parse, active-jobs-metric; health indicators for each; NestJS Schedule in the worker.
- Worker use cases under `apps/worker/src/app/workflow/usecases/` implement add-job, digest merging, queue-next-job, run-job, failed-job handling and status updates.
- Event ingress: `apps/api/src/app/events/` (`trigger-event`, bulk trigger, topic trigger); outbound via webhooks (`apps/api/src/app/webhooks/`) and WebSocket delivery (`apps/ws`). Digest and preference engines are part of the core.

### 3.9 Authentication and permissions model
- `apps/api/src/app/auth/community.auth.module.config.ts`: Passport with `JwtStrategy`, `ApiKeyStrategy`, `JwtSubscriberStrategy`, optional GitHub OAuth; JWT secret and expiry configured there.
- `packages/shared/src/entities/organization/member.enum.ts`: `MemberRoleEnum` = `org:owner`, `org:admin`, `org:author`, `org:viewer` plus deprecated OSS `member`/`admin`; `PermissionsGuard` and `@Permissions()` decorator in `libs/application-generic/src/decorators/permissions.decorator.ts`.
- Environment scoping (`RootEnvironmentGuard`), API keys and subscriber tokens complete the community auth model. `enterprise/packages/auth` supplies additional (proprietary) auth such as Clerk.

### 3.10 Tests, coverage and known limitations
- 389 `*.spec.ts`/`*.e2e.ts` files found across API, DAL, worker, framework and dashboard; Jest, Mocha and Vitest are configured (`jest.config.js`, app-level `test` scripts, `packages/framework` Vitest).
- Coverage percentages and CI pass state were not executed — *unverified*.
- Limitations: Mongo + Redis + S3 + several Node services make local setup heavy; runtime-created indexes; licence split; `enterprise/packages` unavailable under MIT.

### 3.11 Enterprise-only functionality
- Root `enterprise/` contains only `packages/` with `auth`, `billing`, `dal`, `shared-services`, `translation`.
- Additional EE UI code exists under `apps/web/src/ee/` (billing, Clerk auth, translations, editor controls) — note that the README's blanket statement that the whole `enterprise` folder is commercial conflicts slightly with the licence text naming `enterprise/packages` and `EE-PACKAGES-LICENSE`; treat all `*ee*` paths as licence-sensitive until reviewed by counsel.

### 3.12 Actual LICENSE terms, attribution and redistribution
- `LICENSE-MIT`: MIT License, Copyright (c) 2019 Noti-fire Apps Ltd. — permissive, requires the copyright and permission notice in copies/substantial portions.
- `LICENSE-ENTERPRISE` and `EE-PACKAGES-LICENSE`: "Novu Proprietary Software License" — internal operations only; no rent/lease/lend/sell/redistribute/sublicense/commercial hosting; **prior written approval from Novu required**; no modification, adaptation or reverse engineering; auto-termination on breach. This is far more restrictive than AGPL or Chatwoot's EE licence. `README.md` states `enterprise/` is commercial; some package manifests declare `ISC`, which does not override the repository licence.
- **Implication:** MIT core and published SDKs may be reused with attribution; proprietary EE packages must be excluded entirely from NOVARA.

### 3.13 External dependencies and their costs
- Self-hostable/free: MongoDB, Redis, S3-compatible storage (localstack in the sample compose).
- Per-message or subscription costs belong to the chosen providers: Resend, SES, SendGrid, Mailgun and other email providers; Twilio/Vonage/MessageBird and other SMS providers; FCM/APNS/OneSignal push; Slack/Teams/Telegram/WhatsApp chat. Optional Sentry and New Relic are paid beyond free tiers; Novu's managed cloud and Enterprise licence are commercial. Verify current prices with each vendor; no amounts are asserted here.

### 3.14 Recommendation — **reuse via public API/SDK** (core/SDKs); **clean-room implement** if deeper control is needed; **exclude** `enterprise/packages`
- Reason: the MIT core and published clients (`@novu/api`, `@novu/js`, `@novu/react`, `@novu/framework`) are designed for external consumption, so adaptation is low-risk; however, self-hosting means operating Mongo/Redis/BullMQ and multiple services, and the proprietary EE packages cannot be shipped. If NOVARA needs one-process local installation, implement a small native notification dispatcher and use provider SDKs directly instead of embedding Novu.

### 3.15 NOVARA module and cross-module implications
- Informs the **Notifications / Multi-channel Delivery** module: workflow steps, digesting, preferences, inbox feed, provider abstraction.
- Must map NOVARA users/subscribers to Novu subscribers under NOVARA identity (no separate login), route all delivery through NOVARA's permission and approval gates (external email/SMS/public posts require authorisation), and feed notification events into the shared event bus and analytics. Provider credentials must be stored in NOVARA's encrypted secret store, not a separate Novu environment.

---

## Cross-cutting conclusion

All three projects implement their own identity, roles and event systems. NOVARA must remain the single source of truth for identity, workspaces, permissions, audit logs and analytics; each capability should be reached through adapters (public API, webhook or clean-room reimplementation) rather than embedding these applications. Licence posture, from most to least restrictive for a unified redistribution: Papermark (AGPL core + commercial EE) → Novu (MIT core + proprietary EE) → Chatwoot (MIT core + commercial EE). Chatwoot and Novu MIT cores are attribution-only obligations; Papermark requires either full AGPL compliance or a clean-room design.
