# Evidence — clean-room project wiki collaboration (T-100)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Eleven named acceptance tests were added in
`apps/api/tests/test_wiki_pages_p2.py` (one per PL row plus a contract guard,
workspace isolation and permission checks) and one static UI wiring guard in
`apps/api/tests/test_ui_wiring.py`. Every test drives the real FastAPI app with
real persisted, workspace-scoped rows; no app code is mocked.

The clean-room module `apps/api/novara_core/modules/wiki_pages.py` owns twelve
additive workspace-scoped tables created by Alembic revision `e0f2a3b4c5d6`
(down revision `d9e1f2a3b4c5`), all extending NOVARA's existing `project_pages`
table by foreign key only. No existing table is altered.

## Delivery boundary (important)

This is a clean-room implementation written from each feature's documented
behaviour, not from Plane's Django/Channels or React editor source. There is no
Django model, Channels/WebSocket transport, React editor package, tiptap/block
editor dependency, hosted service or outbound HTTP. Notable honest limits:

- **Version history** stores full title/body snapshots with monotonic versions
  and appends a new version on restore; nothing is destructively overwritten.
- **Analytics** count only locally recorded views (`WikiPageView`) and report
  `external_calls: false`; no analytics vendor is contacted.
- **Publication** exposes a *local* URL (`/local/p/<slug>`), not a public hosted
  page. No domain, CDN or distribution is involved.
- **Exports** are deterministic local Markdown/HTML/text renders with a sha256
  content hash; no PDF/DOCX renderer or file download is claimed.
- **Co-editing** uses expiring local edit leases read by polling; presence is
  explicitly `polling-only`. No realtime socket or CRDT engine is claimed.

The API contract reports `version: 1`, `legacy_versions: []`,
`external_calls: false`, `external_delivery: false` and
`realtime_transport: polling-only (no Channels/WebSocket)`.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| PL-096 | `test_pl096_page_version_history_records_and_restores` | Monotonic versions, immutable history, restore appends a new version without losing earlier rows. |
| PL-097 | `test_pl097_page_analytics_count_local_views_only` | Locally recorded views aggregate by visitor/source; no external calls. |
| PL-098 | `test_pl098_page_publication_and_local_exports` | Publish toggles a local URL with unique per-workspace slugs; md/html/txt exports are deterministic local renders with content hashes. |
| PL-099 | `test_pl099_page_labels_are_workspace_scoped_and_attachable` | Labels created once, attached, listed, removed; missing labels fail 422. |
| PL-100 | `test_pl100_nested_pages_form_a_cycle_safe_tree` | Parent/child relations, ordered children, cycle and self-parent rejection. |
| PL-101 | `test_pl101_page_collections_group_pages` | Named collections group pages in explicit positions; duplicates conflict. |
| PL-102 | `test_pl102_editor_blocks_replace_and_list_in_order` | Typed blocks validated against a local block-type catalog, ordered, replaceable; unsupported types fail 422. |
| PL-103 | `test_pl103_polling_presence_and_inline_comments` | Expiring local edit leases, polling presence excluding the owner, block-scoped inline comments that resolve; bad block ids fail 404. |
| Robustness | `test_wiki_contract_reports_no_external_transport` | Contract advertises one API version, no external transport and local-only delivery. |
| Isolation | `test_wiki_pages_are_workspace_isolated` | A second workspace sees no trees/collections and cannot read or mutate another workspace's page entities. |
| Permission | `test_wiki_mutations_require_write_permission` | Reads use TASK_READ; unauthenticated writes are refused and cross-workspace lookups fail closed. |
| UI | `test_wiki_pages_route_controls_are_rendered_and_dispatched` | The `wiki-pages` Operations route renders all eight feature panels; every control has exactly one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_wiki_pages_p2.py` -> **11 passed, 1 warning**.
- `pytest apps/api/tests/test_wiki_pages_p2.py apps/api/tests/test_ui_wiring.py`
  -> **47 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `e0f2a3b4c5d6`.
- `scripts/migration_roundtrip_check.py d9e1f2a3b4c5` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md`.

## Not claimed

No Plane source, Django/Channels transport, React editor package, hosted
service, public page delivery, realtime collaboration engine or outbound HTTP
is claimed. Other Plane rows remain in their existing matrix states.
