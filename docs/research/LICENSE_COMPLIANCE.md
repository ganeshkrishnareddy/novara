# License compliance — initial findings

Verified against GitHub metadata on 2026-11-22. This document is a gate, not a formality: **no large-scale code integration may begin until it is complete.**

## Rule adopted

No source code has been copied from any of the ten projects. No redistribution has occurred. Where reuse is possible, prefer modular adapters, public APIs, SDKs, independently licensed packages and clean-room implementations over copying source.

## Classification

| Repository | GitHub result | Compliance position |
|---|---|---|
| formbricks/formbricks | NOASSERTION | Manual license-text review required before reuse |
| meilisearch/meilisearch | NOASSERTION | Manual review; independently implement a search adapter rather than copy |
| growthbook/growthbook | NOASSERTION | Manual review; feature-flag SDK/API integration preferred |
| papermark/papermark | NOASSERTION | Manual review |
| makeplane/plane | AGPL-3.0 | Network copyleft — obligations must be reviewed before any combination or network offering |
| mautic/mautic | NOASSERTION | Manual review |
| chatwoot/chatwoot | NOASSERTION | Manual review |
| novuhq/novu | NOASSERTION | Manual review |
| coreyhaines31/marketingskills | MIT | Attribution required; use as inspiration for independently implemented skills |
| ethanplusai/sellbird | AGPL-3.0 | Network copyleft — same review as Plane |

## Still required before integration

1. Read the actual `LICENSE` (and any `LICENSE.md`, `LICENSE-ENTERPRISE`, `NOTICE`) text in each repository and record the real terms.
2. Identify enterprise-only functionality and confirm it is excluded.
3. Record original attribution requirements in `THIRD_PARTY_NOTICES.md`.
4. Produce a software bill of materials.
5. Decide NOVARA's own license with the AGPL interaction understood. **No `LICENSE` file has been created for NOVARA yet** — do not assume one.
6. Have compatibility reviewed before redistributing combined code.

## Blocker

A complete license decision for NOVARA's own code is a human/owner decision. Work that does not depend on it (research, architecture, contracts, independent implementation of generic modules) continues.
