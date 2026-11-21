# NOVARA research: Marketing Skills and Sellbird

Audited 2026-11-22 for T-006. Context: `docs/VISION.md` and `docs/research/REPOSITORY_AUDIT.md`. Evidence came from the GitHub REST API, raw repository files, and the public product sites listed below. Paths such as `skills/product-marketing/SKILL.md` are repository-relative to the audited repository; NOVARA paths are relative to the NOVARA repository root. This is research only: no source was copied into NOVARA.

Primary sources checked: [marketingskills API](https://api.github.com/repos/coreyhaines31/marketingskills), [marketingskills tree](https://api.github.com/repos/coreyhaines31/marketingskills/git/trees/main?recursive=1), [marketingskills README](https://raw.githubusercontent.com/coreyhaines31/marketingskills/main/README.md), [sellbird API](https://api.github.com/repos/ethanplusai/sellbird), [sellbird tree](https://api.github.com/repos/ethanplusai/sellbird/git/trees/main?recursive=1), [sellbird README](https://raw.githubusercontent.com/ethanplusai/sellbird/main/README.md).

## coreyhaines31/marketingskills

### 1. Identity, default branch, language, activity

- Repository: `coreyhaines31/marketingskills`; homepage <https://marketing-skills.com>; described as "A collection of AI agent skills focused on marketing tasks".
- GitHub metadata observed 2026-11-22 via [API](https://api.github.com/repos/coreyhaines31/marketingskills): default branch `main`, language JavaScript, 61,851 stars, 9,024 forks, 39 open issues, created 2026-01-15T19:45:23Z, pushed 2026-11-20T02:15:08Z, not archived, MIT.
- Current plugin manifests report version `2.14.25` (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`). `VERSIONS.md` records the 2.14.25 release on 2026-11-19.
- Maintenance is active; the tree has 1,098 entries, including 53 skill definitions and a release/versioning workflow set.

### 2. Actual features available under the community license

- Advertised: a free, MIT-licensed skill pack usable with Claude Code, OpenAI Codex, Cursor, Windsurf, or any Agent Skills-spec agent. README wording: "Use these however you want."
- Actually present in the repo:
  - 53 skills under `skills/*/SKILL.md`, each with YAML frontmatter; examples include `product-marketing`, `cro`, `copywriting`, `seo-audit`, `ads`, `cold-email`, `analytics`, `conversion-tracking`, and `marketing-plan`.
  - `product-marketing` is the foundation skill other skills read first, per README.
  - 53 per-skill `evals/evals.json` files plus `evals/tool-awareness/` and `evals/triggers/`.
  - 128 integration guides under `tools/integrations/` and 69 standalone Node CLIs under `tools/clis/`.
  - Claude and Codex plugin manifests, a partner registry (`partners.json`), and governance docs (`tools/PARTNERS.md`, `CONTRIBUTING.md`).
- There is no separate "community edition"; the whole repository is MIT-licensed. Partner markers (◆) are disclosed sponsorship presence, not a paid feature tier.

### 3. Frontend and backend technology

- No application frontend or backend exists in the repository. The product is Markdown instructions plus helper scripts.
- Languages/files: Markdown skills; JavaScript/`.mjs` CLI and automation scripts; shell validators (`validate-skills.sh`, `validate-skills-official.sh`); Python packaging/eval helpers (`scripts/package_skills.py`); JSON manifests and registries.
- No root `package.json`, server framework, ORM, or runtime service is present. Some skills ship browser-side JS snippets, e.g. `skills/conversion-tracking/scripts/`, but those are examples/snippets for the user's site, not a hosted app.
- Cannot verify the implementation of `marketing-skills.com`; `partners.json` says the site fetches that file from raw GitHub, but the site source is not in this repo.

### 4. Database schema and migrations

- None. No database file, schema, migration directory, or persistence layer appears in the repository tree.
- Third-party CLIs may write data to the user's own SaaS accounts via APIs, but the repo defines no local database or shared data model.
- Any state needed by NOVARA would have to be supplied by NOVARA itself (e.g. skill-version pinning, evaluation results, user preferences).

### 5. API endpoints and integrations

- No first-party HTTP API endpoints are implemented in the repo.
- Integration surface is documentation + zero-dependency Node CLIs. `tools/REGISTRY.md` indexes tools across analytics, SEO, CRM, payments, email, SMS, ads, CRO, scheduling, sales engagement, competitive intelligence, and automation.
- Representative CLI files: `tools/clis/ga4.js`, `ahrefs.js`, `google-ads.js`, `apollo.js`, `hubspot` is documented but uses API/MCP (no local CLI file), `resend.js`, `instantly.js`, `zapier.js`, `segment.js`.
- `tools/SETUP.md` distinguishes local CLI setup from hosted MCP connectors; hosted MCP servers are external services, not code shipped here.
- `tools/REGISTRY.md` marks five Verified Partners: Converly, Ploy, AIsa, Omnia, Livestorm. `tools/PARTNERS.md` says sponsorship buys disclosed placement and never edits skill recommendations.

### 6. Reusable SDKs/libraries

- No importable SDK package. Reuse units are:
  - Skill folders (`SKILL.md`, `references/`, `scripts/`, `evals/`) following the Agent Skills format.
  - Plugin manifests for Claude Code and Codex (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`).
  - Standalone CLIs under `tools/clis/`, which `tools/PARTNERS.md` describes as zero-dependency Node 18+ scripts with `--dry-run` support.
  - Eval harnesses `scripts/tool-awareness-eval.mjs` and `scripts/trigger-eval.mjs`.
- For NOVARA, these are content/protocol artifacts rather than linked libraries.

### 7. Install/deployment

- README install paths: `npx skills add coreyhaines31/marketingskills`; Claude Code plugin; Codex plugin; clone/copy selected skills; git submodule; fork; SkillKit; Claude Web skill ZIPs; Perplexity Computer skill ZIPs.
- `tools/SETUP.md` says repository CLIs require Node 18+ and no dependency installation; `--env-file` examples require Node 20.6+.
- No server deployment, containers, migrations, or infrastructure-as-code are required for the core skill pack.
- Upgrades are tracked through `VERSIONS.md` and plugin version manifests.

### 8. Background jobs/events

- No runtime scheduler, queue, event bus, or background worker exists.
- GitHub Actions provide CI/release automation: `.github/workflows/` includes `regression-tests.yml`, `validate-skill.yml`, `check-hidden-content.yml`, `check-versions.yml`, `sync-skills.yml`, `skill-packaging.yml`, and `release.yml`.
- Eval scripts call headless Claude Code when invoked manually; `evals/tool-awareness/README.md` states each run costs one Claude Code request per prompt per repeat (default 3). This is a test cost, not a product feature.

### 9. Auth/permissions

- No application authentication, authorization, users, roles, or tenant model.
- Credentials for third-party tools are collected and stored locally by the user's agent according to `tools/SETUP.md`; the repo warns not to paste credentials into chat.
- Governance rules in `tools/PARTNERS.md` are editorial rules (disclosure, neutrality, no forced endorsement), not software permissions.

### 10. Tests/coverage/limitations

- Tests: `tests/run-regression.sh`, `tests/run-official-validator-regression.sh`, `tests/test_skill_packaging.py`, many `tests/clis/*.test.cjs` contract tests, hidden-content checks, and 53 skill eval files.
- CI: `.github/workflows/regression-tests.yml` runs validator regressions, CLI contract tests, and hidden-content checks on pushes/PRs affecting relevant paths.
- No code-coverage metric or threshold was found. Quality is largely structural validation, contract tests, and prompt/trigger evals.
- Limitations: skill quality depends on the consuming agent; third-party API behavior can drift; partner-funded placement is governed by policy but not cryptographically verifiable from the repo; the website implementation cannot be audited here.

### 11. Enterprise-only or paid-hosted boundary

- No enterprise-only feature gating exists in the repository. All skills, CLIs, docs, and evals are MIT-licensed.
- Sponsorship tiers are funding, not access control: `tools/PARTNERS.md` lists Supporter $1–199/mo, Sponsor $200/mo, Skill Partner $500/mo, and Category Partner $1,500/mo. These fund maintenance and disclosed placement; they do not unlock code.
- Cannot verify any private enterprise features on `marketing-skills.com` because the site source is not in the repo.

### 12. LICENSE terms, attribution, redistribution

- `LICENSE`: MIT License, Copyright (c) 2025 Corey Haines.
- Requires retaining the copyright and permission notice in copies or substantial portions. No copyleft or source-disclosure obligation.
- README says "Free and MIT licensed" and "Use these however you want"; `CONTRIBUTING.md` defaults skill `license` frontmatter to MIT.
- NOVARA can vendor or adapt skills with notice preservation. Partner disclosure headers in `tools/integrations/*.md` and `partners.json` should survive redistribution because they are part of the governance artifact.

### 13. External dependencies and costs

- Runtime dependency for CLIs: Node 18+; no package installation for the CLIs themselves.
- Optional paid third-party accounts/API keys for tools named in guides (Semrush, Ahrefs, DataForSEO, Apollo, ZoomInfo, mail/ads/CRM platforms, etc.). The repo itself does not charge.
- Eval runs consume Claude Code requests, as documented in `evals/tool-awareness/README.md`.
- Sponsorship/partner fees listed in `tools/PARTNERS.md` are optional project funding, not a user requirement.

### 14. Recommendation

- Adopt as the content foundation for NOVARA's Marketing Skills module, with version pinning and notice preservation.
- Prefer consuming skills through a defined local path or plugin mechanism rather than copy-pasting ad hoc into core code; this keeps upgrades and partner disclosures traceable.
- Do not assume tool guides imply free API access: keep credentialing and cost disclosure in NOVARA's integration layer.
- Low legal risk under MIT; main risks are content drift and maintaining evaluation quality.

### 15. NOVARA module implications

- Maps directly to the Marketing Skills module in `docs/VISION.md`: 53 editable skills, consistent frontmatter, per-skill evals, and a published version history.
- No database, auth, or background jobs to reconcile with NOVARA's "one identity/permissions/analytics model"; NOVARA should supply those concerns externally.
- Preserve `LICENSE`, skill frontmatter, partner disclosure headers, and `partners.json` provenance if bundled.
- Reuse the repo's integrity rubric (`CONTRIBUTING.md`, `tools/PARTNERS.md`) as a policy template for how NOVARA names and sponsors third-party tools.

## ethanplusai/sellbird

### 1. Identity, default branch, language, activity

- Repository: `ethanplusai/sellbird`; homepage <https://sellbird.ai>; formerly Harvey, renamed at 0.4.0.
- GitHub metadata observed 2026-11-22 via [API](https://api.github.com/repos/ethanplusai/sellbird): default branch `main`, language Python, 6,879 stars, 1,434 forks, 77 open issues, created 2026-03-12T01:24:50Z, pushed 2026-11-18T08:10:00Z, not archived, AGPL-3.0.
- `pyproject.toml` reports version `0.4.0`, requires Python >=3.11, and classifies the project as Beta.
- The tree has 295 entries: 57 files/directories under `sellbird/`, 17 under `docs/`, and 119 entries under `tests/`.

### 2. Actual features available under the community license

- Advertised: "The open-source outreach platform that runs on your Claude or ChatGPT plan" — finds companies and decision makers, verifies email, writes personal cold email, sends, and handles replies.
- Actually present and implemented in the repo:
  - Multi-agent pipeline: Scout, Writer, Handler, Sender, and LinkedIn-related roles; agent skills are editable Markdown under `skills/`.
  - 29-signal catalog in `sellbird/signals.py`; 26 are free and paid ones require explicit confirmation. Signals are stored as observation rows, not columns.
  - Discovery providers, website profiling, email pattern finding/verification, campaign/sequence drafting, Outbox approval, sending, reply classification, opt-out handling, suppression, bounce handling, usage tracking, MCP server, FastAPI dashboard, CSV export.
  - Extension entry points for dashboard routes, tick steps, CLI commands, send rules, headers, agent routes, MCP tools, and mailbox connections (`sellbird/extensions.py`, `docs/extensions.md`).
- The entire repository is AGPL-3.0-only; there is no reduced community edition in the repo. Hosted `sellbird.ai` is a separate private-beta service described below.

### 3. Frontend and backend technology

- Backend: Python 3.11+, FastAPI and Uvicorn for the local dashboard; SQLite through `aiosqlite`; `httpx`, BeautifulSoup, Playwright, dnspython, aiosmtplib, keyring, pydantic, pytz; `mcp` for the MCP server; `pystray`/Pillow for macOS/Windows tray support.
- Dashboard frontend: static HTML/JavaScript/CSS served by FastAPI from `sellbird/web/`; no React/Next.js app found. `dashboard.py` explicitly disables `/docs`, `/redoc`, and `/openapi.json`.
- Model layer: `sellbird/brain.py` invokes the user's Claude Code or Codex CLI with model tools disabled; README and `docs/how-it-works.md` state there is no separate model-API bill.
- Deployment helper: `Dockerfile` and `docker-compose.yml` for Linux; docs recommend pip install on macOS/Windows.

### 4. Database schema and migrations

- Local SQLite database at `data/sellbird.db`, with home-directory precedence `SELLBIRD_HOME`, checkout, then OS user data folder (README).
- `sellbird/state.py` uses linear, idempotent migrations tracked by `PRAGMA user_version`; migrations must be appended, not edited/reordered. `PRAGMA journal_mode=WAL` and a 30-second busy timeout are set.
- Core tables include `companies`, `prospects`, `campaigns`, `conversations`, `feedback`, `actions`, `usage_log`, `processed_replies`, `usage_events`, `email_patterns`, `outbox`, `settings`, `signal_codes`, `observations`, `runs`, `suppressions`, `mailboxes`, and `campaign_mailboxes`, with numerous indexes.
- Design note in `sellbird/signals.py`: every signal is an `observations` row, so adding a signal needs no column migration and history/provenance travel with the fact.
- `sellbird/storage.py` defines a `connect/check_schema/exists` backend boundary so an external storage backend can own its schema; SQLite remains the default.

### 5. API endpoints and integrations

- Local dashboard API in `sellbird/dashboard.py`, e.g. `/api/setup-status`, `/api/settings`, `/api/companies`, `/api/prospects`, `/api/outbox`, `/api/conversations`, `/api/signals`, `/api/discover/estimate`, `/api/discover/run`, `/api/sellbird/start|stop|logs`, `/api/sending-mode`, `/api/cohort`, `/api/export/prospects.csv`, `/api/usage`, `/api/activity`, `/api/today`, `/api/instance`.
- MCP tools in `sellbird/mcp_server.py` include `today`, `stats`, `activity`, `usage`, `campaigns_list`, `prospects_list`, `companies_list`, `company_profile`, `conversations_list`, `outbox_list`, `signals_list`, `discover_providers`, `discover_estimate`, `sending_status`, `sending_pause`, `offer_suggest`, `inboxes_list`, and `inbox_pause`.
- Mail integrations: Gmail API, Microsoft 365 via Graph OAuth, generic SMTP/IMAP, and legacy Instantly API. Multiple inboxes are supported.
- Data/verification integrations from `.env.example`: DataForSEO, Serper.dev, Scavio, TinyFish, Reoon, ZeroBounce, Hunter, Precleared, TrulyInbox, Cloudflare Workers (for local rank), Calendly.
- `sellbird/public_http.py` resolves and checks every IP on each request/redirect before connecting, disables environment proxies, and rejects special-use networks to limit SSRF when reading untrusted websites.

### 6. Reusable SDKs/libraries

- Not marketed as a general SDK, but reusable surfaces exist:
  - `sellbird.extensions` Python entry-point group with a registry for routes, tick steps, commands, send rules, headers, agent routes, MCP tools, and mailbox connections.
  - `sellbird/mcp_server.py` exposes a read/pause-oriented MCP toolset to coding agents.
  - `skills/*.md` are plain Markdown prompt modules; `docs/skills-and-agents.md` says they are concatenated into prompts with no fine-tuning or vector store.
  - `sellbird/storage.py` is a small storage-backend abstraction.
- Anything derived from or linked into these modules remains subject to AGPL-3.0 terms.

### 7. Install/deployment

- Local: Python 3.11+, `pip install -e .` (or requirements.txt), Claude Pro/Max with Claude CLI or a ChatGPT plan with Codex CLI, plus a mailbox. Run `sellbird setup`, then commands such as `sellbird signals --confirm free`, `sellbird discover`, `sellbird dashboard`, `sellbird run`, `sellbird export`.
- Dashboard default: <http://127.0.0.1:5555>; `sellbird dashboard` prints a private unlock link.
- Docker: `docs/docker.md` supports native Linux via Compose, host networking, non-root execution, and SSH tunneling for remote access; the image ships Claude CLI only, not Codex.
- Hosted: `sellbird.ai` was in private beta as of 2026-11-22 and redirects `/pricing` to an early-access request page. The site advertises managed domains, inboxes, warmup, DNS, and sending, but no public pricing, SLA, or enterprise tier was verifiable.

### 8. Background jobs/events

- `sellbird/main.py` implements the heartbeat loop: wake, read replies, profile/discover/write, send from the Outbox in a second phase, log actions, run extension tick steps, then sleep. It respects quiet hours, interruptible sleeps, and a PID/lock file to prevent two loops draining the same Outbox.
- Extensions' tick steps run once per heartbeat cycle with a 120-second timeout; failures are isolated.
- The `outbox` SQLite table acts as a durable send queue with status ladder and approval state; there is no Redis/RabbitMQ/Kafka broker found.
- `docs/roadmap.md` lists the heartbeat loop, observation model, governed signal vocabulary, cohort builder, discovery cost estimates, outbox approval ladder, pre-send gate, bounce kill switch, reply handling, quota tracking, dashboard, and CSV export as done.

### 9. Auth/permissions

- Dashboard: random token in `data/dashboard-token`; first-open URL carries it in the fragment, then the browser keeps it per tab. All API requests require `Authorization: Bearer <token>`; cookies and query strings are rejected. `sellbird/dashboard_auth.py` enforces loopback bind, loopback `Host` header, origin checks, and security headers. Delete the token file and restart to rotate it.
- MCP agent uses a separate `data/agent-token`. `sellbird/mcp_server.py` states the agent can read data, estimate discovery cost, and pause sending, but cannot approve or send email, resume sending, confirm signals, or read the dashboard token.
- Product safety controls: default approval for every email, Outbox review, autopilot opt-in, deterministic pre-send gate, do-not-contact/suppressions, opt-out handling, bounce kill switch, and per-inbox/global pause.
- No multi-user RBAC/tenant model was found; this is a single-operator local tool.

### 10. Tests/coverage/limitations

- CI: `.github/workflows/tests.yml` runs `python -m pytest -q` across Ubuntu/macOS/Windows and Python 3.11/3.12, plus packaging tests and scripted/localhost Codex CLI tests. Codex on Windows is not covered; Codex-specific modules skip there.
- Tests include 119 entries under `tests/`, covering dashboard auth, storage/state, signals, discovery, mail providers, sending mode, outbox, compliance footer, do-not-contact, prompt injection, public HTTP, prompt-injection/provider isolation, MCP, extensions, Docker config, and packaging.
- No coverage percentage or threshold was found in the repo.
- Limitations: requires a paid AI subscription plus CLI; deliverability depends on the operator's domain/mailbox and warmup; legal compliance remains the sender's responsibility (`docs/deliverability.md`); hosted managed infrastructure is private beta and not auditable here; no AI voice dialer by explicit roadmap decision.

### 11. Enterprise-only or paid-hosted boundary

- No enterprise-only code path or feature gate was found in the repository. All implementation and docs are AGPL-3.0-only.
- The hosted site describes a managed service (domains, inboxes, warmup, DNS, sending) and private beta, but no public enterprise tier, pricing, or SLA was verifiable on 2026-11-22; `/pricing` redirected to `/early-access/`.
- Optional integrations such as Instantly Growth API access, TrulyInbox Starter API access, or paid data providers are third-party paid dependencies, not Sellbird enterprise features.

### 12. LICENSE terms, attribution, redistribution

- `pyproject.toml` declares `license = "AGPL-3.0-only"`; `LICENSE` contains the GNU Affero General Public License v3 (19 November 2007).
- `NOTICE`: Sellbird (formerly Harvey) is Copyright (C) 2026 Ethan Rogers and contributors; from 0.4.0 it is AGPL-3.0-only. Harvey releases up to 0.3.x remain MIT under Copyright (c) 2026 Ethan Rogers, and that MIT notice is preserved.
- AGPL implications: if NOVARA modifies Sellbird and lets users interact with it over a network, those users must receive the corresponding source of the modified version. It cannot be relicensed as MIT/proprietary.
- Attribution/redistribution: keep `LICENSE`, `NOTICE`, the Harvey MIT notice for older code, and any third-party notices. TrulyInbox links in docs/README are affiliate links and should remain disclosed if those docs are republished.

### 13. External dependencies and costs

- Python dependencies from `pyproject.toml`/`requirements.txt`: pyyaml, python-dotenv, httpx, playwright, beautifulsoup4, dnspython, aiosmtplib, aiosqlite, keyring, pydantic, pytz, fastapi, uvicorn, mcp, plus pystray/Pillow on macOS/Windows.
- Requires Claude Pro/Max with Claude CLI, or a ChatGPT plan with Codex CLI. README claims no separate model-API bill.
- README/docs costs observed: mailbox about $7/month; default discovery source free/OpenStreetMap; 26 of 29 signals free.
- `.env.example` observed costs: DataForSEO $0.372 per 1,000 businesses and $0.006 per depth-30 organic search; Serper 2,500 free queries then a $50 prepaid pack; Scavio 50 free credits then $30/mo for 7,000 credits (estimates use $0.01 pay-as-you-go); Cloudflare Workers about $5/mo on the paid plan for local rank; Precleared 10 checks/day without a key, 25/day with a free key, paid packs beyond; verifier/data keys from Reoon, ZeroBounce, Hunter, TinyFish, and others are optional.
- These are operator-paid third-party costs. They are shown before paid discovery runs, per README/docs, but NOVARA should not present them as guarantees.

### 14. Recommendation

- Do not copy Sellbird code into NOVARA's MIT/proprietary core. AGPL-3.0 is incompatible with that unless the combined work is distributed under AGPL and network source-offer obligations are met.
- Treat Sellbird as a reference implementation or an optional, clearly separated AGPL module/service. If deployed, keep it isolated, preserve notices, provide source for modifications, and avoid merging its code into shared NOVARA components.
- Strong patterns worth studying without copying: user-confirmed signal catalog, observation-row data model, durable Outbox with human approval, pre-send gate and suppressions, extension boundaries, and read/pause-only MCP permissions.
- Hosted `sellbird.ai` is private beta; do not build a NOVARA dependency on it until pricing, terms, and availability are public.

### 15. NOVARA module implications

- Maps to the Sellbird/outreach module in `docs/VISION.md`, but conflicts with the goal of a single MIT-friendly codebase if code is imported directly.
- Identity/permissions: Sellbird's single-operator dashboard token and agent token would need to be mapped into NOVARA's one identity/permissions model; the "agent can pause but not approve/send" boundary is a useful design input.
- Data model: its local SQLite `observations`/`outbox` design would need reconciliation with NOVARA's analytics and storage abstractions. Prefer adopting the pattern, not the tables, unless the AGPL service boundary is explicit.
- Compliance: preserve approval-by-default, opt-out handling, pre-send checks, and legal/deliverability warnings as module requirements.
- If NOVARA ever ships an outreach module, document the license boundary clearly: MIT core + optional AGPL service/module, or an independently written implementation informed by these patterns.
