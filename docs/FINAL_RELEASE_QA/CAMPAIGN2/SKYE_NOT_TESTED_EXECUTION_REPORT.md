# Skye — NOT_TESTED Execution Report (Campaign 2)

**Bot:** Skye (ProgVision Games)
**Scope:** The 675 features assigned to Skye in `NOT_TESTED_EXECUTION_QUEUE.csv`
**Generated:** 2026-11-25, 12:32 IST
**Repository:** `D:\NOVARA` (Git HEAD `f1dcfefe162faac644e974f075a411eb0975f4cb`, branch `main`)
**Read-only:** No application code, tests, README, site, final registry or shared report was modified. No commit, push, tag, deploy or provider contact. Only the two owned deliverables were created: this report and `docs/FINAL_RELEASE_QA/CAMPAIGN2/evidence/skye_feature_test_results.csv`. Batch stdout was saved under `docs/FINAL_RELEASE_QA/CAMPAIGN2/evidence/skye_test_batch_01.txt` … `skye_test_batch_09.txt`.

## 1. Method

1. Read `NOT_TESTED_EXECUTION_QUEUE.csv` and selected rows where `Assigned agent == Skye` (675 features).
2. Read `evidence/not_tested_test_map.json` and took the exact pytest node IDs from `directly_named` for each feature ID.
3. Deduplicated node IDs across features (684 unique nodes; one node is parametrized and collected as 2 variants, giving 685 test cases).
4. Split the 684 unique nodes into 9 small batches (80, 80, 80, 80, 80, 80, 80, 80, 44) and ran each batch with the project venv, saving full stdout/stderr and a JUnit XML per batch.
5. Marked a feature `PASS` only when **all** of its directly named node IDs passed. No route-only or broad-sweep observation was promoted.
6. Wrote one row per feature ID to `skye_feature_test_results.csv` with the mapped nodes, per-node outcome, evidence batch file(s) and an observed note.

Fixtures: `apps/api/tests/conftest.py` provides an in-memory SQLite engine per test (`sqlite://` with `StaticPool`), so runs used fresh synthetic databases only. No real credentials or providers were used.

## 2. Counts

| Metric | Count |
|---|---:|
| Features assigned to Skye | 675 |
| Features marked PASS | 675 |
| Features marked FAIL | 0 |
| Features left NOT_TESTED | 0 |
| Unique pytest nodes run | 684 |
| Test cases collected (incl. parametrized variants) | 685 |
| Test cases passed | 685 |
| Test cases failed / errored | 0 |
| Batches run | 9 |
| Batches with non-zero exit code | 0 |

## 3. Exact commands

All batches were run from `D:\NOVARA` with the project venv. The node list for each batch is in `C:\Users\ganes\AppData\Local\Temp\opencode\campaign2\batch_##.txt` (one node ID per line, prefixed with `apps/api/tests/`). The command template for every batch was:

```powershell
Set-Location D:\NOVARA
$nodes = Get-Content "C:\Users\ganes\AppData\Local\Temp\opencode\campaign2\batch_0N.txt"
.\.venv\Scripts\python.exe -m pytest $nodes -v --tb=short --junitxml="C:\Users\ganes\AppData\Local\Temp\opencode\campaign2\batch_0N.xml" 2>&1 |
  Out-File -FilePath "docs\FINAL_RELEASE_QA\CAMPAIGN2\evidence\skye_test_batch_0N.txt" -Encoding utf8
```

The nine runs, with node counts and results:

| Batch | Nodes | Exit code | Result line | Batch file |
|---:|---:|---:|---|---|
| 01 | 80 | 0 | `80 passed, 1 warning in 54.66s` | `skye_test_batch_01.txt` |
| 02 | 80 | 0 | `80 passed, 1 warning in 57.36s` | `skye_test_batch_02.txt` |
| 03 | 80 | 0 | `80 passed, 1 warning in 56.31s` | `skye_test_batch_03.txt` |
| 04 | 80 | 0 | `80 passed, 1 warning in 64.25s` | `skye_test_batch_04.txt` |
| 05 | 80 | 0 | `80 passed, 1 warning in 63.02s` | `skye_test_batch_05.txt` |
| 06 | 80 | 0 | `80 passed, 1 warning in 62.88s` | `skye_test_batch_06.txt` |
| 07 | 80 | 0 | `80 passed, 1 warning in 68.04s` | `skye_test_batch_07.txt` |
| 08 | 80 | 0 | `80 passed, 1 warning in 58.89s` | `skye_test_batch_08.txt` |
| 09 | 44 | 0 | `45 passed, 1 warning in 32.41s` (one parametrized node collected 2 variants) | `skye_test_batch_09.txt` |

The only parametrized node was `test_sellbird_safety_p1.py::test_sb079_blank_footer_is_rejected`, which collected two variants (`[]` and `[   ]`); both passed.

## 4. Failures by feature ID

None. All 675 assigned features passed all of their directly named pytest nodes.

## 5. Repair recommendations

None required. No failing or errored node was observed, so no test or application change is recommended from this pass. If a later change touches the modules covered by these nodes, re-run the same node IDs (listed in `skye_feature_test_results.csv`) as the regression gate.

## 6. Limitations

- In-memory SQLite only; no production PostgreSQL, Docker or hosted deployment was exercised.
- Synthetic data only; no real credentials, providers or external transactions.
- Only the directly named pytest nodes were run. A feature can have behaviour beyond what its named nodes cover; passing nodes are per-feature evidence, not full acceptance of every source capability.
- No dark theme, mobile installer or non-Chromium browser was tested.
- Node IDs were deduplicated across features, so a node shared by several features was executed once and its result applied to all of them.
- Results reflect the repository state at Git HEAD `f1dcfefe162faac644e974f075a411eb0975f4cb` (2026-11-25). Later changes require re-running.

## 7. Deliverable

`docs/FINAL_RELEASE_QA/CAMPAIGN2/evidence/skye_feature_test_results.csv` — 675 rows, one per Master feature ID, with columns: `Master feature ID`, `Source project`, `Exact source feature name`, `NOVARA module`, `Mapped pytest nodes`, `Per-node outcome`, `Evidence batch file`, `Campaign 2 result`, `Observed note`. All 675 rows have `Campaign 2 result = PASS`.
