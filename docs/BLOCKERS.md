# Blockers and decisions

| ID | Blocker | Impact | Owner | Status |
|---|---|---|---|---|
| B-01 | Container tooling not yet available in the development environment | Blocks Docker Compose distribution, local PostgreSQL/Redis containers, installation testing and all container build targets | Owner / environment | Open |
| B-02 | ~~Repository licenses unclassified~~ | — | Research + licensing review | Resolved 2026-11-22: decisions recorded in `docs/research/LICENSE_COMPLIANCE.md`; no source copied |
| B-03 | NOVARA's own license not chosen | Blocks creating `LICENSE` and any public release | Owner decision | Open |
| B-04 | Name / trademark / domain availability not checked | Blocks final public branding | Research | Open |
| B-05 | ~~No GitHub repository created~~ | — | Owner | Resolved 2026-11-22: `https://github.com/ganeshkrishnareddy/novara` (public, default branch `main`, initially empty) |
| B-06 | Platform signing, notarisation and store credentials absent | Blocks signed Windows/macOS installers and App Store / Play publication | Owner | Open |
| B-07 | External integration credentials (Gmail, Microsoft 365, WhatsApp, SMS, AI providers) absent | Blocks live integration tests and provider-backed features | Owner | Open |
| B-08 | Code signing certificates and release infrastructure absent | Blocks verified public binaries | Owner | Open |
| B-09 | ~~AI agent center and integrations have no frontend screens~~ | — | Development | Resolved 2026-11-22: both screens implemented and live browser tested; see `docs/QA_ROUNDS_2026-11-22.md` |
| B-10 | ~~Three QA rounds with evidence logs not complete~~ | — | QA / Development | Resolved 2026-11-22: developer, independent (Panko, 14/14) and adversarial/recovery rounds complete in `docs/QA_ROUNDS_2026-11-22.md` |
| B-11 | Live tablet/mobile viewport emulation unavailable in the mounted browser | Responsive layouts inspected in CSS only, not at device widths | Environment | Open |
| B-12 | PostgreSQL and container behaviour unverified (Docker unavailable); Alembic revision tested on SQLite only | Blocks deployment and migration parity claims | Environment / Owner | Open |

Nothing in this file is an instruction to act — it is a record of what is missing.

| B-13 | 236 catalogue rows are LICENSING_RESTRICTED and 135 are EXTERNAL_DEPENDENCY_BLOCKED | These 371 rows cannot become VERIFIED_COMPLETE in a clean-room local build without lawful clean-room replacements or owner-supplied credentials and infrastructure. They remain honestly dispositioned in the matrix and licensing register rather than being silently dropped or marked complete | Owner / legal / environment | Open |
