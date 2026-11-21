# Plane and Mautic repository audit

Audit date: 2026-11-22. Audited refs: `makeplane/plane@preview` and `mautic/mautic@7.x`. Source of truth: live GitHub metadata, raw files at those refs, and public vendor docs. GitHub metadata is point-in-time and branches move.

Terminology: **Advertised** means README, pricing, or vendor docs. **Verified** means observed in source/manifests at the audited ref. Facts are not extrapolated into metrics; anything not verified is explicitly marked. No source code was copied into NOVARA and no application code was written for this task.

---

## 1. `makeplane/plane`

### 1.1 Identity, default branch, language, activity

- Repository: [makeplane/plane](https://api.github.com/repos/makeplane/plane), id `568098118`.
- Description: "Open-source Jira, Linear, Monday, and ClickUp alternative. Plane is a modern project management platform to manage tasks, sprints, docs, and triage."
- Default branch: `preview`. Primary language reported by GitHub: TypeScript. Not archived.
- Created `2022-11-19`; last push `2026-11-20` (UTC, from GitHub API).
- Popularity at audit time: 62,906 stars, 6,485 forks, 1,175 open issues **plus PRs** in the API count (GitHub HTML showed 764 issues and 411 PRs, which sums to 1,175).
- Source: [GitHub REST metadata](https://api.github.com/repos/makeplane/plane), [README](https://raw.githubusercontent.com/makeplane/plane/preview/README.md).

### 1.2 Actual features verified from source/docs

- Advertised by README: Work Items, Cycles, Modules, Views, Pages, Analytics; installation via Plane Cloud, self-host Docker/Kubernetes, all-in-one Docker.
- Verified in source: API URL families for projects, work items/issues, cycles, modules, states, labels, members, assets, intake, invites and stickies ([api/urls](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/api/urls/__init__.py)); workspace/project models and roles ([workspace.py](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/db/models/workspace.py)); background tasks for notifications, exports, webhooks, issue activities, page versions, file assets and workspace seeding ([bgtasks](https://github.com/makeplane/plane/tree/preview/apps/api/plane/bgtasks)).
- Verified auth methods in source: email/password, magic link, Google, GitHub, GitLab and Gitea OAuth ([authentication/urls.py](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/authentication/urls.py)). Self-host docs also describe SMTP unique codes and instance-level authentication configuration ([docs](https://developers.plane.so/self-hosting/govern/authentication)).
- Not verified from the community source alone: SAML, OIDC, LDAP, granular access control, audit logs, AI credits/agents, custom properties, dashboards, teamspaces, initiatives and integrations such as GitHub/Slack. These are **advertised paid/enterprise features** on [Plane pricing](https://plane.so/pricing); the source tree at `preview` only exposes `credentials` and `oauth` provider folders under [authentication/provider](https://github.com/makeplane/plane/tree/preview/apps/api/plane/authentication/provider). Entitlement enforcement for paid self-host features was not established.

### 1.3 Frontend and backend technologies

- Frontend: TypeScript monorepo driven by pnpm/Turbo; apps `web`, `admin`, `space`, `live`. Web app uses React Router (`react-router dev/build`), MobX stores (per `AGENTS.md`), shared `@plane/*` workspace packages, Tailwind config, Atlassian drag-and-drop, Base UI, and `@makeplane/propel` ([root package.json](https://raw.githubusercontent.com/makeplane/plane/preview/package.json), [web package.json](https://raw.githubusercontent.com/makeplane/plane/preview/apps/web/package.json), [AGENTS.md](https://raw.githubusercontent.com/makeplane/plane/preview/AGENTS.md)).
- Backend: Python/Django 5.2, Django REST Framework 3.18, Celery 5.5 with beat/results, Django Channels, PostgreSQL via psycopg, Redis via django-redis, optional OpenAI and Slack SDKs ([pyproject.toml](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/pyproject.toml)).
- API schema: `drf-spectacular` views for OpenAPI schema, Swagger UI and ReDoc when `ENABLE_DRF_SPECTACULAR` is set ([urls.py](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/urls.py)).

### 1.4 Database schema and migrations

- Django app `plane.db` contains `models/`, `migrations/` and `management/` subpackages ([db tree](https://github.com/makeplane/plane/tree/preview/apps/api/plane/db)). Migrations are a first-class workflow: `.github/workflows/migration-check.yml` exists ([workflows](https://github.com/makeplane/plane/tree/preview/.github/workflows)).
- Verified model examples: `Workspace` (`workspaces`), `WorkspaceMember` (`workspace_members`) with role choices Admin=20, Member=15, Guest=5, plus invites, teams, themes and user preferences ([workspace.py](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/db/models/workspace.py)).
- API modules evidence additional persisted entities: Project, WorkItem/Issue, Cycle, Module, State, Label, Intake, Asset, Sticky and Page-related records ([api/urls](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/api/urls/__init__.py)).
- PostgreSQL is the configured relational store; RabbitMQ appears in the example environment and compose stack, while Redis is required for cache/Channels/Celery ([.env.example](https://raw.githubusercontent.com/makeplane/plane/preview/.env.example)). Exact table count was not exhaustively enumerated.

### 1.5 API endpoints and integrations

- URL prefixes: `/api/`, `/api/public/`, `/api/instances/`, `/api/v1/`, `/auth/`, plus optional `/api/schema/`, `/api/schema/swagger-ui/` and `/api/schema/redoc/` ([urls.py](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/urls.py)).
- Example verified v1 patterns: `workspaces/<slug>/projects/`, `.../work-items/`, `.../issues/`, `.../cycles/`, `.../modules/`, `.../states/`, `.../labels/`, `.../members/`, `.../intake-issues/`, `assets/user-assets/` and `users/me/` ([api/urls](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/api/urls/__init__.py)).
- Documented public REST API: base `https://api.plane.so/`, `X-API-Key` personal tokens, OAuth bearer tokens, optional IdP tokens via OAuth Bridge, cursor pagination (`per_page`, `cursor`), 60 requests/minute, `fields`/`expand` parameters ([Plane API docs](https://developers.plane.so/api-reference/introduction)).
- Integration hooks visible in code: OAuth providers, webhook background task, Slack and OpenAI dependencies. Pricing advertises GitHub, GitLab, Slack, Sentry and Draw.io as paid integrations ([pricing](https://plane.so/pricing)).

### 1.6 Reusable SDKs/libraries

- Monorepo packages are internal workspace libraries, not a separately published NOVARA-facing SDK: `blocks`, `constants`, `editor`, `hooks`, `i18n`, `logger`, `services`, `shared-state`, `tailwind-config`, `types`, `typescript-config`, `utils`, `codemods` ([packages tree](https://github.com/makeplane/plane/tree/preview/packages)).
- Reusable integration surface is the documented REST API plus generated OpenAPI schema; no official standalone Plane client SDK was found in the audited repository. This is an absence-of-evidence statement, not a claim that none exists elsewhere.

### 1.7 Installation/deployment requirements

- Docker Compose defines separate `web`, `admin`, `space`, `api`, `worker`, `beat-worker`, `migrator`, `live`, `plane-db` (PostgreSQL), `plane-redis`, `plane-mq` (RabbitMQ), `plane-minio` and `proxy` services ([docker-compose.yml](https://raw.githubusercontent.com/makeplane/plane/preview/docker-compose.yml)).
- Example environment covers PostgreSQL, Redis, RabbitMQ, AWS/S3 or MinIO uploads, file size limit, SMTP/cert settings and deprecated OpenAI settings ([.env.example](https://raw.githubusercontent.com/makeplane/plane/preview/.env.example)).
- Self-host docs offer Docker Compose and Kubernetes/Helm paths ([docs](https://docs.plane.so/self-hosting/overview)). README also advertises Plane Cloud and an all-in-one image. Local development runs the API in Docker while web apps run on host ports ([AGENTS.md](https://raw.githubusercontent.com/makeplane/plane/preview/AGENTS.md)).

### 1.8 Background jobs and event system

- Celery is configured with `django_celery_beat` and `django-celery-results`; compose has dedicated `worker` and `beat-worker` containers ([pyproject](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/pyproject.toml), [compose](https://raw.githubusercontent.com/makeplane/plane/preview/docker-compose.yml)).
- Verified task modules include `email_notification_task`, `notification_task`, `webhook_task`, `issue_activities_task`, `issue_automation_task`, `export_task`, `analytic_plot_export`, `page_version_task`, `file_asset_task`, `project_invitation_task`, `workspace_seed_task` and cleanup/deletion tasks ([bgtasks](https://github.com/makeplane/plane/tree/preview/apps/api/plane/bgtasks)).
- Real-time transport is Django Channels ([pyproject](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/pyproject.toml)). The service named `live` in compose is consistent with live collaboration delivery.

### 1.9 Auth and permissions

- Authentication endpoints cover sign-in/up/out, CSRF token, magic links, forgot/change/set password, email checks and Google/GitHub/GitLab/Gitea OAuth callbacks ([authentication/urls.py](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/authentication/urls.py)).
- Authorization model includes workspace roles Admin/Member/Guest and workspace-member records; instance-level model defaults to `PLANE_COMMUNITY` edition with Admin role only in the license app ([workspace.py](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/db/models/workspace.py), [instance.py](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/license/models/instance.py)).
- API keys are documented as user-scoped and checked against the user's permissions ([API docs](https://developers.plane.so/api-reference/introduction)).

### 1.10 Tests, coverage, known limitations

- `AGENTS.md` says all features require unit tests using each package's existing framework. API dev dependencies include pytest, pytest-django, pytest-cov, pytest-xdist, pytest-mock and coverage ([pyproject](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/pyproject.toml)).
- CI includes CodeQL, copyright check, migration check, API build/lint and web-app build/lint workflows ([workflows](https://github.com/makeplane/plane/tree/preview/.github/workflows)). No dedicated test-coverage workflow was found in that directory.
- Limitations: no coverage percentage was verified; root `package.json` has no `test` script; local API requires Docker; enterprise entitlement behavior is not verifiable from the public license model alone.

### 1.11 Enterprise-only functionality

- Advertised paid tiers: Pro, Business and Enterprise Grid, with features including custom work item types/properties, dashboards, initiatives, teamspaces, integrations, SAML/OIDC, LDAP, granular access control, audit logs, custom SLAs and multiple workflows/approvals ([pricing](https://plane.so/pricing)).
- Verified community source: only `PLANE_COMMUNITY` in the instance edition enum and no SAML/OIDC/LDAP provider files in the audited provider folder ([instance.py](https://raw.githubusercontent.com/makeplane/plane/preview/apps/api/plane/license/models/instance.py), [provider tree](https://github.com/makeplane/plane/tree/preview/apps/api/plane/authentication/provider)).
- Caution: presence/absence of every paid feature in the deployed self-hosted binary was not exhaustively verified. Treat the pricing page as commercial entitlement evidence, not as proof of source absence.

### 1.12 Actual license terms, attribution, redistribution

- License: GNU Affero General Public License v3.0. Text: [LICENSE.txt](https://raw.githubusercontent.com/makeplane/plane/preview/LICENSE.txt). Copyright notice: `Copyright (c) 2023-present Plane Software, Inc. and contributors`, `SPDX-License-Identifier: AGPL-3.0-only` ([COPYRIGHT.txt](https://raw.githubusercontent.com/makeplane/plane/preview/COPYRIGHT.txt)). Source files carry matching SPDX headers.
- AGPL section 13 is the key network clause: modified versions offered to remote users must offer those users the Corresponding Source. Redistribution must preserve notices, state modifications and keep the work under AGPL.
- Attribution/redistribution restriction: retain copyright/license notices and comply with AGPL source obligations. No separate Plane trademark license was found in the audited files. This is research, not legal advice.

### 1.13 External dependencies and costs

- Runtime dependencies: PostgreSQL, Redis, RabbitMQ, MinIO/S3-compatible object storage, SMTP for invitations/notifications, reverse proxy and container platform ([compose](https://raw.githubusercontent.com/makeplane/plane/preview/docker-compose.yml), [docs](https://docs.plane.so/self-hosting/overview)).
- Optional external services: OpenAI (declared deprecated in `.env.example`) and Slack SDK. Cloud AI credits and paid integrations are commercial features.
- Advertised prices on 2026-11-22: Pro `$8/user/mo` monthly or `$6` annually; Business `$15` monthly or `$13` annually; Enterprise custom ([pricing](https://plane.so/pricing)). Self-hosting has no license fee but requires infrastructure/operations spend.

### 1.14 Recommendation

**Clean-room implement the NOVARA work-management module; use the public REST API only for explicit user-configured interoperability with an existing Plane instance.** Do not embed Plane, copy its source, or reuse its internal `@plane/*` packages.

Reason: AGPL-3.0 network/source obligations plus paid feature boundaries make source reuse risky for a unified NOVARA product. Embedding would also preserve Plane's workspace/role model instead of giving NOVARA native shared identity, permissions and event semantics. The documented API is sufficient for narrow data exchange without coupling NOVARA's architecture to Plane's.

### 1.15 NOVARA module informed and implication

- Informs: work items/issues, projects, cycles, modules, states/views, pages, intake, comments/activities, attachments and delivery analytics.
- Shared identity: map NOVARA users/groups to workspace membership rather than importing Plane's `Admin/Member/Guest` integers directly; define a translation layer for external Plane API keys.
- Permissions: NOVARA RBAC must own authorization; map Plane workspace/project roles only as external attributes, never as the source of truth.
- Events: emit NOVARA-native events for work item created/updated, state changed, cycle started/completed, module assigned and page published; adapt Plane webhooks/tasks at the boundary only.
- Analytics: reuse the *shape* of cycle/module progress and issue throughput thinking, but compute metrics in NOVARA from NOVARA events.

---

## 2. `mautic/mautic`

### 2.1 Identity, default branch, language, activity

- Repository: [mautic/mautic](https://api.github.com/repos/mautic/mautic), id `12204147`.
- Description: "Mautic: Open Source Marketing Automation Software."
- Default branch: `7.x`. Primary language reported by GitHub: PHP. Not archived.
- Created `2013-08-19`; last push `2026-11-20` (UTC, from GitHub API).
- Popularity at audit time: 11,067 stars, 3,563 forks, 364 open issues **plus PRs** in the API count (GitHub HTML showed 145 issues and 219 PRs).
- GitHub license metadata is `NOASSERTION/Other`; the checked-in `LICENSE.txt` text is GPL-3.0-or-later with third-party notices. Source: [GitHub REST metadata](https://api.github.com/repos/mautic/mautic), [README](https://raw.githubusercontent.com/mautic/mautic/7.x/README.md).

### 2.2 Actual features verified from source/docs

- Advertised by README: open-source marketing automation, privacy-focused, extendable, DPG governance since 2024, self-host free forever; production package from `mautic.org/download`.
- Verified in `app/bundles`: `LeadBundle` (contacts/segments), `EmailBundle`, `CampaignBundle` (journeys), `PageBundle` (landing pages), `FormBundle`, `PointBundle`, `StageBundle`, `DynamicContentBundle`, `AssetBundle`, `NotificationBundle`, `SmsBundle`, `ReportBundle`, `DashboardBundle`, `StatsBundle`, `WebhookBundle`, `IntegrationsBundle`, `MarketplaceBundle`, `ConfigBundle`, `UserBundle`, `CoreBundle`, `MessengerBundle` and a `QueueBundle/Config` path ([bundles tree](https://github.com/mautic/mautic/tree/7.x/app/bundles)).
- Verified plugins: GrapesJS builder, Clearbit, cloud storage, CRM, email marketing, Focus, FullContact, Gmail, Outlook, Social, Tag Manager and Zapier ([plugins tree](https://github.com/mautic/mautic/tree/7.x/plugins)).
- Community-license distinction: the source download is advertised as including "all features" for self-host use ([Start using Mautic](https://mautic.org/start-using-mautic/)). No separate enterprise source edition was found in `7.x`. Commercial hosting tiers are partner offerings, not evidence of withheld GPL features.

### 2.3 Frontend and backend technologies

- Backend: PHP (`AGENTS.md` states PHP 8.2+), Symfony 7.4, Doctrine ORM, bundle-based architecture; root `composer.json` requires `mautic/core-lib:^7.0` ([AGENTS.md](https://raw.githubusercontent.com/mautic/mautic/7.x/AGENTS.md), [composer.json](https://raw.githubusercontent.com/mautic/mautic/7.x/composer.json)).
- Frontend/build: npm assets, `webpack.config.js`, `importmap.php`, GrapesJS builder plugin, themes directory; Mautic 5+ requirements list npm ([root listing](https://github.com/mautic/mautic/tree/7.x), [requirements](https://mautic.org/mautic-requirements/)).
- API: REST API historically; in 7.x several entities also carry API Platform `ApiResource` attributes with operation-level security expressions, e.g. `Role` operations `user:roles:viewown`, `user:roles:create` ([Role.php](https://raw.githubusercontent.com/mautic/mautic/7.x/app/bundles/UserBundle/Entity/Role.php)).

### 2.4 Database schema and migrations

- Doctrine ORM mapping is defined in entity metadata methods; `Role` maps to table `roles` with `is_admin`, permissions, readable permissions and users relations ([Role.php](https://raw.githubusercontent.com/mautic/mautic/7.x/app/bundles/UserBundle/Entity/Role.php)).
- Migrations use Doctrine-style classes with `up()`/`down()` and `PreUpAssertionMigration`; `app/migrations/Migration.template` shows table-prefix-aware SQL via `getPrefixedTableName()` ([Migration.template](https://raw.githubusercontent.com/mautic/mautic/7.x/app/migrations/Migration.template)).
- Mautic 7 database support stated by vendor: MySQL 8.4+ (InnoDB) or MariaDB 10.11.0+ ([requirements](https://mautic.org/mautic-requirements/)).
- Full schema was not enumerated; bundle/entity names above indicate the major domains only.

### 2.5 API endpoints and integrations

- Documented external integration path: enable the API in Configuration, create API credentials, use OAuth 1.0a, OAuth 2 or Basic auth; base URL ends in `/api/`; contexts include contacts, forms and pages with `get`, `getList`, `create`, `edit`, `delete` ([api-library README](https://github.com/mautic/api-library)).
- 7.x source shows API Platform metadata on entities and `ApiBundle` subdirectories for ApiPlatform event listeners, controllers, OAuth2 entities, security, serializer and tests ([ApiBundle tree](https://github.com/mautic/mautic/tree/7.x/app/bundles/ApiBundle)). Complete endpoint list was not verified because the developer docs root states its content needs a major update and legacy pages may be outdated ([devdocs](https://devdocs.mautic.org/)).
- Webhooks are a first-class bundle ([bundles tree](https://github.com/mautic/mautic/tree/7.x/app/bundles)). Integration plugins listed in 2.2 cover CRM, email marketing, social, enrichment and Zapier.

### 2.6 Reusable SDKs/libraries

- Official separate client: [mautic/api-library](https://github.com/mautic/api-library), MIT licensed, PHP 8.2+, PSR-18 HTTP client, Packagist package `mautic/api-library`, with its own PHPUnit/Codecov setup. This is the cleanest externally reusable artifact found.
- Core bundles/plugins are GPL-licensed application code, not suitable as drop-in NOVARA libraries under the "no copy/paste" constraint.
- GrapesJS builder is shipped as a plugin; it is a UI editor integration, not a NOVARA-shared SDK.

### 2.7 Installation/deployment requirements

- Recommended developer setup: DDEV (`ddev start`), Composer, npm build, `bin/console mautic:install <site-url>`; prefer DDEV wrappers for PHP/Composer/console commands ([AGENTS.md](https://raw.githubusercontent.com/mautic/mautic/7.x/AGENTS.md)).
- Manual setup is documented; README also describes Composer, DDEV and zip + web installer flows. Source outside a tagged release is explicitly warned as "alpha"; production should use the packaged release ([README](https://raw.githubusercontent.com/mautic/mautic/7.x/README.md), [download](https://mautic.org/download/)).
- Vendor requirements: PHP 8.2–8.5 for Mautic 7.0, required PHP extensions, npm, MySQL 8.4+/MariaDB 10.11+, Apache 2.x/Nginx 1.x/IIS 7; shared hosting is not recommended ([requirements](https://mautic.org/mautic-requirements/)).

### 2.8 Background jobs and event system

- Cron/console commands exist in CoreBundle for maintenance, cleanup, imports/exports, anonymization, updates, Transifex and IP/Do-not-sell maintenance ([Command tree](https://github.com/mautic/mautic/tree/7.x/app/bundles/CoreBundle/Command)).
- Symfony Messenger is used via `MessengerBundle`; default transport is synchronous, with configurable async transports (Doctrine/AMQP examples) and `messenger:consume` consumers. Defined messages include `EmailHitNotification` and `PageHitNotification` ([MessengerBundle README](https://github.com/mautic/mautic/tree/7.x/app/bundles/MessengerBundle)).
- Event-driven extension is extensive: CoreBundle `Event/` contains builder, menu, route, token replacement, import/export, maintenance, search, stats and upgrade events ([Event tree](https://github.com/mautic/mautic/tree/7.x/app/bundles/CoreBundle/Event)); ApiBundle also exposes `ApiEvents.php`.

### 2.9 Auth and permissions

- User model includes roles and permissions; `Role` has `isAdmin`, `permissions`, `rawPermissions` and users, with API operations guarded by scoped expressions such as `user:roles:viewown`, `user:roles:editother` and `user:roles:deleteown` ([Role.php](https://raw.githubusercontent.com/mautic/mautic/7.x/app/bundles/UserBundle/Entity/Role.php)).
- API auth supports OAuth 1.0a, OAuth 2 and optional Basic Auth, enabled by administrator configuration ([api-library README](https://github.com/mautic/api-library)).
- Managed Enterprise hosting advertises SSO as part of the partner plan, not as a verified separate GPL core feature ([managed plans](https://mautic.org/pricing/)).

### 2.10 Tests, coverage, known limitations

- Developer commands include `ddev composer test`, PHPUnit via `app/phpunit.xml.dist`, PHPStan and targeted bundle tests ([AGENTS.md](https://raw.githubusercontent.com/mautic/mautic/7.x/AGENTS.md)).
- Root includes `codeception.yml`, `codecov.yml`, `phpstan.neon` and `phpstan-baseline.neon`. CI includes `tests.yml`, `e2e-tests.yml`, `coverage-check.yml` and `api-library-tests.yml` ([workflows](https://github.com/mautic/mautic/tree/7.x/.github/workflows)). README Codecov badge references the `6.x` branch, so current `7.x` coverage was not verified.
- Limitations: developer docs explicitly say content needs a major update and legacy pages may be outdated ([devdocs](https://devdocs.mautic.org/)); source-tree installs are alpha unless from a tagged release; exact coverage percentage not verified.

### 2.11 Enterprise-only functionality

- No separate enterprise edition flag was found in the `7.x` source. The verified download path says the self-host package includes all features ([Start using Mautic](https://mautic.org/start-using-mautic/)).
- Advertised paid offerings are service tiers from official hosting partner Dropsolid: Managed Mautic Essential, Professional and Enterprise, with dedicated infra/support, custom plugins, "enterprise-grade security + SSO" and higher sending limits ([managed plans](https://mautic.org/pricing/)).
- These hosting features are commercial services; they should not be recorded as GPL source features without separate verification.

### 2.12 Actual license terms, attribution, redistribution

- Core license: GPL v3 or later. `LICENSE.txt` states redistribution/modification under GPL version 3 or, at the option of the recipient, any later version; `composer.json` declares `GPL-3.0` ([LICENSE.txt](https://raw.githubusercontent.com/mautic/mautic/7.x/LICENSE.txt), [composer.json](https://raw.githubusercontent.com/mautic/mautic/7.x/composer.json)).
- Trademark: "Mautic is a trademark of the Mautic project of the Open Source Collective." The license file also lists third-party notices, e.g. Carbon Design System pictograms (Apache-2.0), Bootstrap and Chart.js (MIT).
- Redistribution obligations: preserve copyright/license notices, mark modified files, provide corresponding source under GPL when conveying binaries/source, and do not add conflicting restrictions. GPL does not contain AGPL's network-use source offer. Legal review is still required before any derivative distribution.

### 2.13 External dependencies and costs

- Self-host dependencies: PHP-FPM/web server, MySQL/MariaDB, Composer, npm-built assets, cron/scheduler, SMTP/email delivery, optional Messenger transport (Doctrine/AMQP) and object/CDN storage for assets ([requirements](https://mautic.org/mautic-requirements/), [MessengerBundle](https://github.com/mautic/mautic/tree/7.x/app/bundles/MessengerBundle)).
- No core license fee for self-hosting. Email delivery, hosting, support and deliverability tooling are separate costs.
- Advertised managed plans on 2026-11-22: Essential from €247.50/mo billed annually (€275 quarterly), Professional from €1237/mo, Enterprise custom pricing ([managed plans](https://mautic.org/pricing/)). These are partner hosting prices, not Mautic license fees.

### 2.14 Recommendation

**Clean-room implement the NOVARA marketing-automation module; optionally reuse the MIT-licensed `mautic/api-library` only for user-configured synchronization with an external Mautic instance.** Do not embed Mautic core or copy its bundles/plugins.

Reason: GPL core code would create derivative-distribution constraints and would not solve NOVARA's defining requirement of shared identity, permissions, events and analytics. The separate MIT client library is a narrow, lower-risk integration tool; the product logic should be NOVARA-native.

### 2.15 NOVARA module informed and implication

- Informs: contacts/segments, email campaigns, forms, landing pages, journeys/campaign flows, points/scoring, stages, webhooks, reports/dashboards and dynamic content.
- Shared identity: model a NOVARA contact/identity record with external IDs for Mautic contacts; do not make Mautic's `LeadBundle` the identity authority.
- Permissions: translate Mautic role scopes into NOVARA RBAC at an adapter boundary; NOVARA remains authoritative for who can view/edit/create/delete campaign and contact data.
- Events: emit NOVARA-native contact identified, contact segmented, campaign entered/exited, email sent/opened/clicked, form submitted, page visited and webhook received events; consume Mautic webhooks/API only as external inputs.
- Analytics: define funnel, engagement and attribution metrics in NOVARA's analytics layer from those events, rather than querying Mautic's reporting tables.

---

## Cross-cutting conclusion

Both repositories are valuable as **design references** and possible **external integration targets**, not as codebases to absorb into NOVARA. Plane's AGPL network clause and Mautic's GPL redistribution terms, combined with NOVARA's requirement for a genuinely unified identity/permission/event/analytics core, point to clean-room module implementation in both cases. The only lower-risk reuse candidate found is Mautic's separate MIT-licensed API client, used only at an explicit integration boundary.
