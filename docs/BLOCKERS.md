# Blockers and decisions

| ID | Blocker | Impact | Owner | Status |
|---|---|---|---|---|
| B-01 | Docker not installed on this machine | Blocks Docker Compose distribution, local PostgreSQL/Redis containers, installation testing and all container build targets | Owner / environment | Open |
| B-02 | Seven repositories report unclassifiable licenses; two are AGPL-3.0 | Blocks any decision to copy, combine or redistribute source code | Research + licensing review | Open |
| B-03 | NOVARA's own license not chosen | Blocks creating `LICENSE` and any public release | Owner decision | Open |
| B-04 | Name / trademark / domain availability not checked | Blocks final public branding | Research | Open |
| B-05 | ~~No GitHub repository created~~ | — | Owner | Resolved 2026-11-22: `https://github.com/ganeshkrishnareddy/novara` (public, default branch `main`, initially empty) |
| B-06 | Platform signing, notarisation and store credentials absent | Blocks signed Windows/macOS installers and App Store / Play publication | Owner | Open |
| B-07 | External integration credentials (Gmail, Microsoft 365, WhatsApp, SMS, AI providers) absent | Blocks live integration tests and provider-backed features | Owner | Open |
| B-08 | Code signing certificates and release infrastructure absent | Blocks verified public binaries | Owner | Open |

Nothing in this file is an instruction to act — it is a record of what is missing.
