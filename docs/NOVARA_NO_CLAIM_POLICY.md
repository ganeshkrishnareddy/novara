# NOVARA no-claim and documentation evidence policy

This document records accurate, conservative decisions for inventory rows
whose acceptance criteria are no-claim, documentation-only, design-decision
or conditional ("if claimed") criteria. It does not assert that a source
project feature was copied or that an external provider was verified. Each
statement is paired with a named acceptance test and a workspace-scoped
read-only boundary record.

### MS-101 — OpenAPI specification generation and CI sync

Source project: Meilisearch.

novara does not claim to implement the meilisearch openapi contract; only local api routes are documented.

### PL-075 — Live service

Source project: Plane.

novara does not claim a realtime component until it is implemented, authenticated and tested.

### PL-143 — Keyboard shortcuts and Power-K

Source project: Plane.

novara does not claim keyboard shortcuts; any shortcut added must not fire in text inputs and must be documented.

### PL-152 — Reverse proxy and certificate settings

Source project: Plane.

novara deployment documentation records tls, domain and proxy choices as owner decisions and does not claim a verified proxy run.

### MT-005 — Self-host free forever with all features

Source project: Mautic.

novara self-host capability is available without a private licence, hosted account or api key; no hidden feature gating is present.

### MT-006 — Production packaged release from mautic.org/download

Source project: Mautic.

novara deployment documentation identifies the local start scripts and the unverified container files; no packaged release is claimed.

### MT-038 — Cloud storage plugin

Source project: Mautic.

novara documents local storage configuration only; no cloud storage provider is claimed or contacted by default.

### MT-061 — MarketplaceBundle

Source project: Mautic.

novara keeps a documented module registry instead of a marketplace; no marketplace capability is claimed.

### MT-084 — DDEV developer environment

Source project: Mautic.

novara local developer setup is documented in readme.md and install.md using the start-local scripts; no ddev is claimed.

### MT-085 — Composer install and bin/console install

Source project: Mautic.

novara install documentation describes its own package manager and start scripts; no composer or bin/console install is claimed.

### MT-087 — Web server support Apache, Nginx and IIS

Source project: Mautic.

novara documents only the verified local web server; apache, nginx and iis support is not claimed as verified.

### MT-088 — Shared hosting not recommended

Source project: Mautic.

novara hosting guidance says to use a supported self-host environment; shared hosting is not claimed as verified.

### MT-090 — PHPStan static analysis and baseline

Source project: Mautic.

novara has no phpstan configuration; the recorded verification tooling is the local pytest suite and alembic checks.

### MT-091 — Codeception and Codecov configuration

Source project: Mautic.

novara has no codecov configuration; coverage claims are limited to the local pytest run recorded in test_results.md.

### MT-103 — Mautic trademark

Source project: Mautic.

novara uses the mautic mark only descriptively in provenance documentation, not as product branding.

### MT-104 — Third-party notices

Source project: Mautic.

novara keeps third-party licence provenance in third_party_notices.md; no unattributed third-party asset is claimed.

### MT-119 — Source-tree install alpha warning

Source project: Mautic.

novara release guidance states that the project is in active development and not a release candidate; no source-tree release is claimed.

### MT-120 — 7.x coverage percentage not verified

Source project: Mautic.

novara coverage claims are limited to verified local test evidence; no mautic coverage percentage is claimed.

### MT-125 — Transifex maintenance command

Source project: Mautic.

novara documents a local, independent localization workflow; no transifex integration is claimed.

### MT-128 — Upgrade event extension

Source project: Mautic.

novara does not claim upgrade-event hooks; no such hook is introduced.

### MT-131 — Maintenance event extension

Source project: Mautic.

novara does not claim maintenance-event hooks; no such hook is introduced.

### MT-132 — Builder event extension

Source project: Mautic.

novara does not claim builder-event hooks; no such hook is introduced.

### MT-133 — Import and export event extension

Source project: Mautic.

novara documents its own import/export portability path; no mautic event-hook compatibility is claimed.

### CW-026 — Keyboard shortcuts

Source project: Chatwoot.

novara does not claim inbox keyboard shortcuts; any shortcut added must not trigger writes without confirmation.

### CW-034 — Dashboard apps

Source project: Chatwoot.

novara does not claim embedded dashboard apps; no panel is loaded from an external origin and no workspace token is exposed to one.

### CW-044 — SMS channel

Source project: Chatwoot.

novara does not claim an inbound or outbound sms capability until consent and a verified provider are configured; no fake call or message ui is shown.

### CW-046 — Voice channel

Source project: Chatwoot.

novara does not claim voice channel parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-058 — SLA timers and status indicators

Source project: Chatwoot.

novara does not claim sla timers; any sla state must come from real timestamps and no fabricated countdown is displayed.

### CW-061 — Captain Assistant

Source project: Chatwoot.

novara does not claim captain assistant parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-062 — Captain Copilot

Source project: Chatwoot.

novara does not claim captain copilot parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-063 — Captain Memories

Source project: Chatwoot.

novara does not claim captain memories parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-064 — Captain Reply suggestions

Source project: Chatwoot.

novara does not claim auto-sending reply suggestions; any draft requires explicit user action and approval.

### CW-068 — Captain Triage

Source project: Chatwoot.

novara does not claim captain triage parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-069 — Captain Scenarios

Source project: Chatwoot.

novara does not claim captain scenarios parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-070 — Captain Monitors / Convergence

Source project: Chatwoot.

novara does not claim an llm-backed monitor; any local count has a reproducible definition and no model dependency is implied.

### CW-071 — Captain copilot / MCP tools

Source project: Chatwoot.

novara does not claim captain copilot / mcp tools parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-072 — Dialogflow chatbot

Source project: Chatwoot.

novara does not claim dialogflow bot replies; a reply requires a verified webhook and is labelled as bot-authored.

### CW-080 — WhatsApp campaigns

Source project: Chatwoot.

novara does not claim whatsapp campaigns parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-103 — WhatsApp CSAT templates

Source project: Chatwoot.

novara does not claim whatsapp csat templates parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-125 — Linear integration

Source project: Chatwoot.

novara does not claim a linear issue link until an authorised api call succeeds; no unverified link is stored.

### CW-126 — Shopify integration

Source project: Chatwoot.

novara does not claim shopify order context until verified data is available; no fabricated order is shown.

### CW-128 — Chatwoot CLI for coding agents

Source project: Chatwoot.

novara does not claim chatwoot cli for coding agents parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-136 — Optional GitHub OAuth strategy

Source project: Chatwoot.

novara does not enable optional github oauth unless the feature is explicitly enabled with configured credentials.

### CW-147 — DigitalOcean one-click Kubernetes deployment

Source project: Chatwoot.

novara does not claim a verified digitalocean one-click deployment; no deployment success is reported in this inventory.

### CW-150 — Development container and deployment manifests

Source project: Chatwoot.

novara local api and web client startup commands are documented in readme.md and install.md.

### CW-154 — Redis cache and queue backend

Source project: Chatwoot.

novara does not claim redis cache and queue backend parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-156 — OpenSearch and Searchkick advanced search backend

Source project: Chatwoot.

novara does not claim opensearch and searchkick advanced search backend parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-157 — S3, Azure and GCS object storage

Source project: Chatwoot.

novara does not claim s3, azure and gcs object storage parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### CW-165 — Process liveness and CloudWatch telemetry

Source project: Chatwoot.

novara does not claim process liveness and cloudwatch telemetry parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### NV-016 — Tool channel steps (PagerDuty, Opsgenie, Grafana, Tool Webhook)

Source project: Novu.

novara does not claim pagerduty, opsgenie, grafana or tool webhook channel steps; no provider endpoint or fabricated delivery is present.

### NV-021 — SMS notifications

Source project: Novu.

novara does not claim sms delivery; no test or ui can claim delivery without a verified provider response.

### NV-037 — Inbox snooze

Source project: Novu.

novara does not advertise inbox snooze until the local behaviour is implemented and covered by named tests.

### NV-049 — Email activity tracking (delivered, opened, clicked, bounced)

Source project: Novu.

novara does not claim email activity tracking; no delivered, opened, clicked or bounced event is shown without a verified provider webhook.

### NV-050 — Push activity tracking

Source project: Novu.

novara does not claim push activity tracking parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### NV-064 — Web Chat channel

Source project: Novu.

novara does not claim web chat channel parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### NV-083 — S3-compatible object storage

Source project: Novu.

novara does not claim s3-compatible attachment storage in the default install; no storage provider is contacted by default.

### NV-117 — Novu Agent Skills

Source project: Novu.

novara does not claim novu agent skills parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### PL-126 — Sensitive data scanning

Source project: Plane.

novara does not claim a sensitive-data scanner; any scanner added must not send content off-platform by default.

### PL-131 — MCP server and connectors

Source project: Plane.

novara does not claim an mcp surface; any mcp surface added must use novara permissions and log access.

### PL-155 — Plane Cloud and all-in-one image

Source project: Plane.

novara default install works without a hosted cloud or all-in-one image; container builds are not verified.

### SB-039 — Scout agent role

Source project: Sellbird.

novara does not claim a scout agent role with write or external-send permissions; no such role is enabled by default.

### SB-040 — Writer agent role

Source project: Sellbird.

novara does not claim a writer agent run can approve or send; any draft requires separate authorisation.

### SB-041 — Handler agent role

Source project: Sellbird.

novara does not claim a handler agent role can send, approve or publish externally.

### SB-044 — Editable Markdown agent skills

Source project: Sellbird.

novara does not claim editable markdown agent skills parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### SB-047 — Heartbeat loop

Source project: Sellbird.

novara does not claim a heartbeat loop; no cycle is advertised as processing approved local work or sending messages.

### SB-049 — PID/lock file preventing duplicate loops

Source project: Sellbird.

novara does not claim pid or lock-file duplicate-loop protection; no such runner capability is present in the default install.

### SB-050 — Extension tick steps with timeout

Source project: Sellbird.

novara does not claim extension tick timeout handling; no tick-execution capability is present in the default install.

### SB-058 — Stats and instance information

Source project: Sellbird.

novara does not report an unavailable provider as active and stores no credential in instance statistics.

### SB-059 — Dashboard docs disabled

Source project: Sellbird.

novara does not claim dashboard docs disabled parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### SB-063 — MCP server toolset

Source project: Sellbird.

novara does not claim an mcp tool that can approve, send or reveal secrets; no such tool is exposed by default.

### SB-065 — Extension entry-point registry

Source project: Sellbird.

novara does not claim an extension entry-point registry; no unrestricted hook registration is present in the default install.

### SB-066 — CLI commands

Source project: Sellbird.

novara does not claim cli commands; no external send command is present in the default install.

### SB-068 — Desktop tray support

Source project: Sellbird.

novara does not claim desktop tray support parity from the source project; no implementation, external call, fabricated result or unverified infrastructure claim is introduced.

### GB-194 — simulate

Source project: GrowthBook.

the growthbook enterprise 'simulate' module is absent from the default novara install; no licensed source is present.

### GB-205 — teams

Source project: GrowthBook.

the growthbook enterprise 'teams' module is absent from the default novara install; novara workspaces and roles are independent.

### GB-213 — custom-roles

Source project: GrowthBook.

the growthbook enterprise 'custom-roles' module is absent from the default novara install; novara uses its own role model.

### GB-234 — holdouts

Source project: GrowthBook.

the growthbook enterprise 'holdouts' module is absent from the default novara install; no holdout feature is advertised.

### GB-239 — dashboards

Source project: GrowthBook.

the growthbook enterprise 'dashboards' module is absent from the default novara install; local analytics are separate.

### GB-250 — releases

Source project: GrowthBook.

the growthbook enterprise 'releases' module is absent from the default novara install; work items are not branded as releases.

### FB-193 — Headless Surveys guide

Source project: Formbricks.

novara does not claim a headless survey template is implemented until a named test and ui evidence demonstrate the underlying survey behaviour.

### NV-075 — No-code editors, layouts and block email editor (`libs/maily-*`)

Source project: Novu.

novara does not claim copied no-code email editor source; any template rendering must use stored content and reject script injection.
