# Meilisearch-compatible local search P1 — named acceptance evidence (2026-11-23)

NOVARA's default build uses its own workspace-scoped SQL search: no search-engine
server, master key or external call is involved. Command:

```
D:\NOVARA\.venv\Scripts\python.exe -m pytest apps/api/tests/test_search_meilisearch_p1.py -q --disable-warnings
# 5 passed (also re-run with the Plane and notification suites: 22 passed)
```

| Master ID | Named test | What is proved |
|---|---|---|
| MS-006 | `test_ms006_search_filters_narrow_results_and_workspace_isolation_holds` | Query filters narrow real contacts, a second workspace's rows cannot be read with the first workspace's token (403), and an empty query is rejected (422). |
| MS-028 | `test_ms028_search_limit_is_validated_and_result_count_is_exact` | Limits 0 and 101 are rejected; a limit of 1 returns exactly one row and an exact `total`; a large valid limit returns a result count equal to `total`. |
| MS-062 | `test_ms062_no_master_key_is_required_by_novara_search` | A normal workspace bearer token is sufficient for search; no engine master key is returned or required. |
| MS-063 | `test_ms063_secret_like_config_is_rejected_and_no_engine_key_is_stored` | A secret-like `apiKey` integration config is rejected with 422 and stores no row; a URL-only config is accepted and the stored row contains no secret. |
| MS-065 | `test_ms065_search_result_fields_are_escaped_in_the_renderer` | The SPA result renderer uses escaped text and attribute helpers; no raw-HTML result path is present. |

No filter DSL, paging, engine keys or federation parameters are claimed: those
remain honest compatible-replacement limitations in the matrix.
