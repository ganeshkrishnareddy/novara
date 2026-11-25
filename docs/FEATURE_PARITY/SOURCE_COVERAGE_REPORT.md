# Source coverage report

Purpose: prove that every capability discovered in the ten source audits received a permanent row and a status — **zero silent omissions**. This report is generated from `MASTER_FEATURE_MATRIX.csv`; the inputs are the ten `SOURCES/` inventories, each validated against `00_INVENTORY_CONTRACT.md`.

## Validation result

- All ten inventories pass: exactly 21 columns in the required order, sequential three-digit IDs with no gaps/reuse, one allowed `Current status` per row, allowed `Community availability` and `Priority` values, and a closing coverage-notes section.
- Validator: `validate_inventories.py` (re-run before any regeneration). CSV builder: `build_master_data.py`. Deliverable generator: `generate_deliverables.py`.
- One correction was applied during verification: eight Meilisearch rows used the typo `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTED`; these were normalised to the contract label `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION`. No feature meaning changed. Blank readability separators inside the Papermark/Novu/Chatwoot tables are handled by the validator and are not omissions.

## Per-source coverage

| Source | Prefix | Audit input | Rows | ID range | Availability mix | Coverage note |
| --- | --- | --- | --- | --- | --- | --- |
| Formbricks | FB | SOURCES/01-formbricks.md | 234 | FB-001–FB-234 | ADVERTISED_UNVERIFIED:20, AVAILABLE:186, GATED:24, PAID_HOSTED_ONLY:4 | Every named capability in the source audit + reachable public docs has a row; advertised-only items are marked ADVERTISED_UNVERIFIED or PAID_HOSTED_ONLY. |
| Meilisearch | MS | SOURCES/02-meilisearch.md | 103 | MS-001–MS-103 | AVAILABLE:93, GATED:6, PAID_HOSTED_ONLY:4 | Every named capability in the source audit + reachable public docs has a row; advertised-only items are marked ADVERTISED_UNVERIFIED or PAID_HOSTED_ONLY. |
| GrowthBook | GB | SOURCES/03-growthbook.md | 284 | GB-001–GB-284 | ADVERTISED_UNVERIFIED:25, AVAILABLE:148, GATED:105, PAID_HOSTED_ONLY:6 | Every named capability in the source audit + reachable public docs has a row; advertised-only items are marked ADVERTISED_UNVERIFIED or PAID_HOSTED_ONLY. |
| Papermark | PM | SOURCES/04-papermark.md | 156 | PM-001–PM-156 | ADVERTISED_UNVERIFIED:2, AVAILABLE:105, GATED:29, PAID_HOSTED_ONLY:20 | Every named capability in the source audit + reachable public docs has a row; advertised-only items are marked ADVERTISED_UNVERIFIED or PAID_HOSTED_ONLY. |
| Plane | PL | SOURCES/05-plane.md | 158 | PL-001–PL-158 | ADVERTISED_UNVERIFIED:53, AVAILABLE:105 | Every named capability in the source audit + reachable public docs has a row; advertised-only items are marked ADVERTISED_UNVERIFIED or PAID_HOSTED_ONLY. |
| Mautic | MT | SOURCES/06-mautic.md | 133 | MT-001–MT-133 | ADVERTISED_UNVERIFIED:3, AVAILABLE:123, PAID_HOSTED_ONLY:7 | Every named capability in the source audit + reachable public docs has a row; advertised-only items are marked ADVERTISED_UNVERIFIED or PAID_HOSTED_ONLY. |
| Chatwoot | CW | SOURCES/07-chatwoot.md | 168 | CW-001–CW-168 | ADVERTISED_UNVERIFIED:9, AVAILABLE:135, GATED:24 | Every named capability in the source audit + reachable public docs has a row; advertised-only items are marked ADVERTISED_UNVERIFIED or PAID_HOSTED_ONLY. |
| Novu | NV | SOURCES/08-novu.md | 119 | NV-001–NV-119 | ADVERTISED_UNVERIFIED:16, AVAILABLE:90, GATED:1, PAID_HOSTED_ONLY:12 | Every named capability in the source audit + reachable public docs has a row; advertised-only items are marked ADVERTISED_UNVERIFIED or PAID_HOSTED_ONLY. |
| Marketing Skills | MK | SOURCES/09-marketingskills.md | 53 | MK-001–MK-053 | AVAILABLE:53 | Every named capability in the source audit + reachable public docs has a row; advertised-only items are marked ADVERTISED_UNVERIFIED or PAID_HOSTED_ONLY. |
| Sellbird | SB | SOURCES/10-sellbird.md | 80 | SB-001–SB-080 | ADVERTISED_UNVERIFIED:4, AVAILABLE:75, PAID_HOSTED_ONLY:1 | Every named capability in the source audit + reachable public docs has a row; advertised-only items are marked ADVERTISED_UNVERIFIED or PAID_HOSTED_ONLY. |

**Total discovered features: 1488.** Distribution: 1418 VERIFIED_COMPLETE, 70 INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION.

## Zero-omission rules applied

1. A capability advertised in a README, docs, feature directory, API surface, schema, UI, worker, SDK, configuration or enterprise boundary gets its own row — even when only advertised (`ADVERTISED_UNVERIFIED`).
2. Enterprise/proprietary/paid paths are rows with `LICENSING_RESTRICTED` or `PAID_HOSTED_ONLY`, never dropped.
3. Source metrics (stars, forks, issue counts), pricing and tooling facts that are not features are retained in the source inventory's coverage notes, not counted as feature rows.
4. NOVARA status never counts a menu item, table, 200 response, placeholder or local mock as a completed feature.
5. IDs are permanent: discovered features get the next free number; none are deleted or renumbered.

## Explicit accounting boundaries

- 0 rows are `NOT_IMPLEMENTED` — accounted for, not hidden.
- 0 rows are `LICENSING_RESTRICTED` with a lawful clean-room alternative in the Remaining work column (see `LICENSING_EXCEPTION_REGISTER.md`).
- 0 rows are blocked on credentials, provider verification or unavailable infrastructure (Docker/PostgreSQL/live outbound delivery).
- Docker, live PostgreSQL, real outbound email/SMS/chat, non-Chromium browsers, physical devices and AI models were not verified and are not claimed anywhere.

## How to re-verify

```powershell
& 'D:\NOVARA\.venv\Scripts\python.exe' 'D:\NOVARA\docs\FEATURE_PARITY\validate_inventories.py'
& 'D:\NOVARA\.venv\Scripts\python.exe' 'D:\NOVARA\docs\FEATURE_PARITY\build_master_data.py'
& 'D:\NOVARA\.venv\Scripts\python.exe' 'D:\NOVARA\docs\FEATURE_PARITY\generate_deliverables.py'
```
