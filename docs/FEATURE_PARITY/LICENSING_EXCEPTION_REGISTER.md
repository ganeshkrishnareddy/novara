# Licensing exception register

Every capability that cannot be copied into NOVARA because it is Enterprise, proprietary, commercial, paid-hosted or AGPL/GPL-incompatible is registered here with its lawful clean-room alternative. Counts are derived from `MASTER_FEATURE_MATRIX.csv`.

**0 `LICENSING_RESTRICTED` features** across 0 sources. No source code from an incompatible licence was copied; no enterprise credential, hosted service or paid tier is a NOVARA dependency.

## Source licence decisions (from `docs/research/LICENSE_COMPLIANCE.md`)

| Source | Community licence | Enterprise/proprietary split | NOVARA reuse approach |
| --- | --- | --- | --- |
| Formbricks | AGPL-3.0 community + Formbricks EE; MIT SDKs | apps/web/modules/ee — Formbricks EE (commercial) | clean-room survey runtime; MIT SDK only at an explicit boundary |
| Meilisearch | MIT + OpenLDAP core; BUSL-1.1 EE | enterprise_editions — BUSL-1.1 | clean-room SQL search; MIT client at an explicit boundary |
| GrowthBook | MIT community; GrowthBook Enterprise License | packages/*/enterprise — Enterprise License | clean-room flag/experiment core; MIT SDK at an explicit boundary |
| Papermark | AGPL-3.0 community; commercial EE | ee/ and app/(ee)/ — commercial EE | clean-room document metadata + view events; no file I/O |
| Plane | AGPL-3.0-only (entire repo) | none; whole repo AGPL-3.0-only | clean-room projects/tasks; public API only for user interoperability |
| Mautic | GPL-3.0 community; Mautic trademark unlicensed | none; GPL-3.0 (trademark unlicensed) | clean-room campaign/metrics; optional MIT API library at a boundary |
| Chatwoot | MIT community; Chatwoot Enterprise License | enterprise/ — Chatwoot Enterprise License | clean-room ticket/conversation core; MIT core API if added |
| Novu | MIT community; proprietary enterprise packages | enterprise/packages — proprietary licence | clean-room job queue + adapters; local mock never claims delivery |
| Marketing Skills | MIT (attribution required) | none; single MIT licence | content reuse with attribution, version pinning, provenance |
| Sellbird | AGPL-3.0-only v0.4.0+; MIT ≤0.3.x | version split: v0.4.0+ AGPL, ≤0.3.x MIT | clean-room approval-gate/Outbox patterns; no AGPL code |

## Restricted features by source

| Source | Restricted rows | Examples (ID: feature) |
| --- | --- | --- |
| Formbricks | 0 | none |
| Meilisearch | 0 | none |
| GrowthBook | 0 | none |
| Papermark | 0 | none |
| Plane | 0 | none |
| Mautic | 0 | none |
| Chatwoot | 0 | none |
| Novu | 0 | none |
| Marketing Skills | 0 | none |
| Sellbird | 0 | none |

## Full exception register

Each row: ID, feature, the licensing constraint recorded in the inventory, and the lawful alternative/remaining work. The lawful alternative is the clean-room action we take instead of copying the restricted source.

| ID | Source | Feature | Licensing constraint | Lawful alternative / remaining work |
| --- | --- | --- | --- | --- |

## Governance

- Attribution, notices and SBOM obligations are preserved in `THIRD_PARTY_NOTICES.md` and `docs/research/LICENSE_COMPLIANCE.md`. MIT content (Marketing Skills) keeps frontmatter, copyright and partner disclosures.
- AGPL/GPL network-copyleft paths are never vendored into NOVARA. Where a clean-room equivalent exists it is marked `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION` with the boundary named in the source inventory — it is not a claim of upstream feature parity.
- Enterprise/proprietary features stay `LICENSING_RESTRICTED` until a lawful clean-room implementation passes its own acceptance criteria; then a new status is recorded, never a silent relabel.
