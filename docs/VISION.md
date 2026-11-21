# Founder vision — NOVARA

Stated by the owner on 2026-11-22. Source of truth for intent, alongside the master development prompt.

## One product, not ten

The goal is not another CRM, marketing tool, project app or AI chatbot. It is **one complete, unified, free and open-source business operating system** that removes subscription sprawl, multiple logins, scattered data, duplicate customer records and vendor dependency.

A beginner downloads NOVARA, installs it, opens one dashboard, creates a workspace and runs their whole business from there. A developer can extend, integrate and customise it.

## Why the ten repositories were chosen

Each solves a different business problem; the useful capability is brought into one coherent product:

| Project | Capability brought into NOVARA |
|---|---|
| Formbricks | Surveys, NPS, CSAT, customer feedback |
| Meilisearch | Fast, typo-tolerant, filterable universal search |
| GrowthBook | Feature flags, experiments, A/B testing, product analytics |
| Papermark | Secure document sharing, viewer tracking, permissions, data rooms |
| Plane | Projects, tasks, issues, kanban, cycles, milestones |
| Mautic | Segmentation, email marketing, campaigns, landing pages, journeys |
| Chatwoot | Support, live chat, shared inbox, omnichannel conversations |
| Novu | Notification workflows: email, push, SMS, in-app |
| Marketing Skills | SEO, copywriting, growth strategy, CRO, competitor research, content |
| Sellbird | Lead research, prospecting, enrichment, outreach, AI sales |

**Do not** copy and paste code blindly, embed the original apps behind a new shell, or bolt ten navigation links together and call it integration. Preserve applicable licences and build the unified product around the capabilities.

## Everything must work together

The defining feature is the connection between modules. Reference flows:

- Website form submission → CRM contact/upsert → duplicate check → authorised enrichment → lead assignment → categorisation → marketing segment → personalised campaign → outreach draft → **human approval** → send via authorised provider → detect reply → update timeline → notify owner → follow-up task → track conversion → one dashboard.
- Website chat → identify customer → show CRM profile and prior conversations → agent replies → internal task if needed → notifications → interaction recorded.
- Proposal document viewed → authorised view event recorded against the customer → assigned salesperson notified.

No manual transfer of information between ten applications.

## Controlled autonomy

An agent ecosystem: research, lead, enrichment, sales, reply-classification, marketing, SEO, content, analytics, support and QA agents, with sub-agent delegation and a master orchestrator. Autonomy is bounded by permissions, execution limits, audit logs, approval gates and task boundaries. External emails, public posts and destructive actions require authorisation.

## Genuinely free and open source

Source downloadable, local and self-hosted operation, essential modules without paywalls, own workspaces and data, export, backup, extension and contribution. No mandatory cloud subscription, activation key or hosted account. Optional external services disclose their costs. Prefer local AI models where practical.

## One installation, every platform

Windows, macOS, Linux, Android and iOS, plus Docker/CLI for developers. Beginners must not have to install PostgreSQL and Redis by hand or decode environment variables. Desktop manages local services; mobile connects securely to a local or remote instance. Clear diagnostics on failure.

## One professional experience

Original logo, one design system, one navigation, one authentication and workspace experience, consistent typography and components, professional dashboards and charts, responsive and accessible. Premium, clean, modern, **light theme only — no dark mode**. Every module must look like the same product.

## Self-marketing

Internal agents identify developer communities, directories, publications, launch opportunities, contributors and partners; prepare SEO, announcements, docs, tutorials and social content; and monitor traffic, stars, downloads, contributions and referrals. Platform rules and authorisation govern all external publication.

## Explicitly rejected

Landing page only; static dashboard with fake data; empty module pages; dead buttons; mock integrations claimed as real; duplicate CRM systems; separate identities per module; isolated automation; ignored licensing; compromised security; claimed tests without evidence; multiple disconnected repositories; stopping at architecture docs or a prototype; unresolved release blockers; needless complexity; expensive infrastructure for basic local use.

## Priority order

1. Product correctness
2. Security and privacy
3. Reliable cross-module integration
4. Functional completeness
5. Ease of installation
6. User experience
7. Performance
8. Documentation
9. Cross-platform distribution
10. Marketing and adoption

## Engineering stance

Treat this as a serious long-term open-source product. Think like a founder, principal architect, security engineer, senior full-stack developer, UX designer, DevOps engineer, QA director, maintainer and growth strategist. Challenge bad decisions, find missing features and better approaches, make reasonable engineering calls autonomously and document them. Do not implement something merely because it is in the initial list if research shows a safer or better approach.
