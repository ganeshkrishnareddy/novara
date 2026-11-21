# Repository audit — initial pass

Source: GitHub REST API, verified 2026-11-22 00:52 IST. This is metadata only. Deep source audit (features, schemas, APIs, deployment, tests) is in progress and will be recorded in `docs/research/repos/`.

| # | Repository | Language | Default branch | Stars | License (GitHub classification) | Last push |
|---|---|---|---|---|---|---|
| 1 | formbricks/formbricks | TypeScript | main | 13,288 | NOASSERTION / Other | 2026-11-20 |
| 2 | meilisearch/meilisearch | Rust | main | 59,951 | NOASSERTION / Other | 2026-11-20 |
| 3 | growthbook/growthbook | TypeScript | main | 8,639 | NOASSERTION / Other | 2026-11-21 |
| 4 | papermark/papermark | TypeScript | main | 9,441 | NOASSERTION / Other | 2026-08-28 |
| 5 | makeplane/plane | TypeScript | preview | 62,906 | AGPL-3.0 | 2026-11-20 |
| 6 | mautic/mautic | PHP | 7.x | 11,067 | NOASSERTION / Other | 2026-11-20 |
| 7 | chatwoot/chatwoot | Ruby | develop | 40,298 | NOASSERTION / Other | 2026-11-20 |
| 8 | novuhq/novu | TypeScript | next | 40,399 | NOASSERTION / Other | 2026-11-21 |
| 9 | coreyhaines31/marketingskills | JavaScript | main | 61,851 | MIT | 2026-11-20 |
| 10 | ethanplusai/sellbird | Python | main | 6,879 | AGPL-3.0 | 2026-11-18 |

## What this means

- `NOASSERTION / Other` means GitHub could not classify the license file. It usually indicates a custom or modified license (community licence plus extra clauses), so the actual text must be read before any code is reused or redistributed. It must **not** be treated as permissive.
- `makeplane/plane` and `ethanplusai/sellbird` are **AGPL-3.0** — network copyleft. Combining these with other code, or offering the result over a network, carries obligations that need explicit review.
- `coreyhaines31/marketingskills` is MIT and is a skills/prompt library rather than a runtime system. The marketing intelligence module should be independently implemented using it as inspiration, not copied as a runtime dependency.
- All ten repositories are active, not archived. Papermark's last push is older (2026-08-28) and needs freshness checks.

## Per-repository deep audit

Assigned outputs land in `docs/research/repos/`:

- `01-formbricks-meilisearch-growthbook.md`
- `02-papermark-chatwoot-novu.md`
- `03-plane-mautic.md`
- `04-marketingskills-sellbird.md`
