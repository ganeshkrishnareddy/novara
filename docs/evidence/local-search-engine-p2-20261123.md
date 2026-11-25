# Evidence — Clean-room local search engine (2026-11-23)

## Scope

Closed 32 Meilisearch P2 rows with a new clean-room module
`apps/api/novara_core/modules/search_engine.py`. Two additive workspace-scoped
tables (`search_indexes`, `search_documents`) are registered in Alembic revision
`b3c4d5e6f7a9`. The engine tokenizes and scores documents in Python against
persisted workspace data: no Meilisearch server, embedding provider, external
SDK or upstream source is used. Every mutation is audited through the shared
event bus.

## Rows closed and named test

All tests are in `apps/api/tests/test_search_engine_p2.py`.

| ID | Capability | Test |
| --- | --- | --- |
| MS-041 | Index creation and management | `test_ms041_index_creation_management_and_fields` |
| MS-043 | Index fields listing | same |
| MS-044 | Add or replace documents | `test_ms044_047_batch_add_and_replace_documents` |
| MS-047 | Batch import and large datasets | same |
| MS-045 | Partial document update | `test_ms045_046_partial_update_and_delete` |
| MS-046 | Document deletion | same |
| MS-004 | Typo tolerance (bounded Levenshtein) | `test_ms004_typo_tolerance` |
| MS-016 | Synonyms (single and multi-word) | `test_ms016_synonyms` |
| MS-017 | Stop words | `test_ms017_stop_words` |
| MS-018 | Separator tokens | `test_ms018_019_separators_and_non_separators` |
| MS-019 | Non-separator tokens | same |
| MS-020 | Dictionary | `test_ms020_dictionary` |
| MS-021 | Language support and tokenization | `test_ms021_locale_and_tokenization` |
| MS-025 | Highlighting | `test_ms025_026_027_highlight_crop_and_positions` |
| MS-026 | Cropping and snippets | same |
| MS-027 | Match positions | same |
| MS-029 | Phrase search and term exclusion | `test_ms029_phrase_search_and_term_exclusion` |
| MS-030 | Matching strategy (last/all/any) | `test_ms030_matching_strategy` |
| MS-031 | Placeholder search | `test_ms031_placeholder_search` |
| MS-012 | Custom ranking rules | `test_ms012_013_ranking_rules_and_score_details` |
| MS-013 | Ranking score and score details | same |
| MS-007 | Faceted search and distributions | `test_ms007_008_facets_and_facet_search` |
| MS-008 | Facet value type-ahead | same |
| MS-023 | Geosearch | `test_ms023_024_geo_search_and_distance_sort` |
| MS-024 | Geo distance sorting | same |
| MS-032 | Distinct attribute | `test_ms032_distinct_attribute` |
| MS-033 | Proximity precision | `test_ms033_proximity_precision` |
| MS-034 | Search cutoff | `test_ms034_search_cutoff` |
| MS-035 | Per-query searchable attributes | `test_ms035_per_query_searchable_attributes` |
| MS-040 | Settings API | `test_ms040_settings_api` |
| MS-057 | Version endpoint | `test_ms057_061_version_and_feature_flags` |
| MS-061 | Experimental feature toggles | same |

## UI

`apps/web/app.js` gained a dedicated `search-indexes` Operations route with a
navigation item, index list, create/delete actions and a local query panel that
renders ranked hits, highlights and score. `apps/api/tests/test_ui_wiring.py`
statically guards the route, every control and every dispatcher.

## Security and isolation

`test_search_engine_workspace_isolation` proves another workspace sees no
indexes, cannot read settings by name and cannot query an index it does not own.
Every create/update/delete requires `verify_workspace` plus
`require(CONTACT_READ)` / `require(NOTE_WRITE)` and publishes an audited event.

## Verification actually run (from `D:\\NOVARA`)

- Targeted suite: **23 passed**.
- UI wiring + targeted: **43 passed** (21 UI guards after adding the new guard).
- Full API suite: **528 passed, 2 warnings in 264.17s** (baseline 504).
- `node --check apps/web/app.js`: exit 0.
- Migration: single Alembic head `b3c4d5e6f7a9`; round trip from
  `a2b3c4d5e6f8` upgrade → downgrade → upgrade PASS with data preserved.

## Honest limits

This is an original local implementation, not Meilisearch. There is no vector
or hybrid search, no LMDB storage, no task queue/webhooks, no remote export,
no Prometheus endpoint, no client SDKs/MCP server, no TLS/HTTP2 termination and
no LLM integration. Typo tolerance is bounded edit distance, ranking is a
weighted scoring pipeline over local documents, and geosearch uses haversine
distance over stored `_geo` coordinates. These out-of-scope rows remain honestly
unclaimed in the matrix.
