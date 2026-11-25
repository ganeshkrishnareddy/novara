# Evidence — clean-room advanced search P2 cluster (T-094)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Fifteen named acceptance tests were added in
`apps/api/tests/test_search_advanced_p2.py` (fourteen feature rows plus one
workspace-isolation test) and one static UI wiring guard in
`apps/api/tests/test_ui_wiring.py`. Every test drives the real FastAPI app
against real persisted, workspace-scoped rows. No app code is mocked.

The clean-room module `apps/api/novara_core/modules/search_advanced.py` owns
nine additive workspace-scoped tables created by Alembic revision
`e4f5a7b8c9d0` (down revision `d3e4f5a7b8c9`). It extends NOVARA's existing
local search engine (`search_engine.py`) with hybrid/vector ranking, localized
attributes, suggestions, weighted federation, index swap, edit-by-function,
compaction records, templates and saved previews.

## Delivery boundary (important)

These Meilisearch rows are MIT-core features and were implemented clean-room:
no Meilisearch server source was copied and no BUSL/enterprise file is used.
All embeddings are deterministic local token-hash vectors computed inside
NOVARA's own database; similarity is exposed as a 0..1 score. No Meilisearch
server, embedding model, external SDK, hosted demo, LMDB/OpenLDAP connector or
vector database is contacted. This verifies NOVARA's own local adapter, not
source-equivalence with Meilisearch.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| MS-001 | `test_ms001_hybrid_search_combines_local_semantic_and_lexical_scores` | Hybrid search blends an explicit semantic weight with lexical overlap; every score is 0..1 with semantic/lexical components. |
| MS-022 | `test_ms022_localized_attributes_and_query_locales_are_recorded` | Locale-specific attribute patterns and query-locale overrides persist on an index. |
| MS-036 | `test_ms036_suggestions_return_prefix_matches_from_indexed_attributes` | Suggestion connectors return prefix matches from a configured attribute; duplicate keys are rejected. |
| MS-038 | `test_ms038_federated_weights_merge_results_from_multiple_indexes` | Federated search applies per-index weights to merged scores; empty member lists are rejected. |
| MS-042 | `test_ms042_index_swap_moves_documents_and_settings_atomically` | Index swap exchanges documents and settings; self-swap is rejected and the moved document is searchable in its new index. |
| MS-048 | `test_ms048_edit_documents_by_function_transforms_selected_fields` | A deterministic edit function transforms selected document attributes and persists the JSON change; unsupported ops are rejected. |
| MS-053 | `test_ms053_index_and_task_queue_compactions_are_recorded` | Index and task-queue compactions are recorded locally with counted documents; invalid kinds are rejected. |
| MS-074 | `test_ms074_similar_documents_are_ranked_by_local_vector_similarity` | Similar documents are ranked from deterministic local embeddings with a 0..1 similarity; a missing reference is a 404. |
| MS-075 | `test_ms075_embedders_store_local_vector_settings_without_external_models` | Embedder settings are local; external kinds and hosted sources are rejected with 422. |
| MS-076 | `test_ms076_user_provided_embeddings_accept_custom_vectors_only` | User-provided embedders accept custom vectors with strict dimension checks; other kinds reject vector upload. |
| MS-077 | `test_ms077_composite_and_multiple_embedders_coexist_on_one_index` | Multiple and composite embedders coexist on one index and are usable in hybrid search. |
| MS-078 | `test_ms078_binary_quantization_uses_one_bit_per_dimension` | Binary quantization stores one bit per dimension and is used in hybrid ranking. |
| MS-095 | `test_ms095_local_search_preview_runs_without_a_hosted_demo` | A saved local preview reruns its query against the index with `local_only: true`. |
| MS-103 | `test_ms103_render_templates_substitute_document_and_query_values` | Embedder/chat/fragment templates render locally, substituting document and query values; invalid kinds are rejected. |
| Isolation | `test_search_advanced_workspace_isolation` | A second workspace cannot read this workspace's embedders/federations or address their index, embedder or federation IDs. |
| UI | `test_search_advanced_route_controls_are_rendered_and_dispatched` | The `search-advanced` Operations route renders federations and search/config forms; every control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_search_advanced_p2.py` -> **15 passed, 1 warning**.
- `pytest apps/api/tests/test_search_advanced_p2.py apps/api/tests/test_ui_wiring.py`
  -> **45 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `e4f5a7b8c9d0`.
- `scripts/migration_roundtrip_check.py d3e4f5a7b8c9` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md`.

## Not claimed

No Meilisearch-hosted feature, external embedding model, vector database,
official client SDK, framework connector, MCP server, agent tooling, Prometheus
exporter, remote export or task webhook delivery is claimed. Rows outside this
cluster remain in their existing matrix states.