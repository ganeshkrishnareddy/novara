# Ten source project acceptance report — Campaign 2

Timestamp: 2026-11-25 12:35 IST. HEAD `f1dcfefe162faac644e974f075a411eb0975f4cb`. Source: `MASTER_FEATURE_MATRIX.csv` (1,488 rows), `FINAL_FEATURE_ACCEPTANCE_REGISTRY.csv` (1,488 rows), `TEN_SOURCE_PROJECT_COMPLETION_REPORT.md`.

## Verdict

All ten source-project inventories are accounted for row by row and every formerly `NOT_TESTED` row now has individual Campaign 2 evidence. The conservative final acceptance statuses are unchanged: **28 PASS, 70 REPLACEMENT_VERIFIED, 221 BLOCKED_EXTERNAL, 737 NOT_TESTED, 432 NOT_APPLICABLE**. Source completeness and local evidence closure are not release acceptance.

## Source-by-source accounting

| # | Source | Matrix rows | Verified complete | Compatible replacement | Final PASS | Final REPLACEMENT_VERIFIED | Final NOT_TESTED | Final BLOCKED_EXTERNAL | Final NOT_APPLICABLE | C2 evidence closed | C2 live blocked |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Formbricks | 234 | 227 | 7 | 0 | 7 | 154 | 0 | 73 | 154 | 0 |
| 2 | Meilisearch | 103 | 94 | 9 | 0 | 9 | 55 | 0 | 39 | 55 | 0 |
| 3 | GrowthBook | 284 | 283 | 1 | 1 | 1 | 53 | 80 | 149 | 53 | 80 |
| 4 | Papermark | 156 | 144 | 12 | 1 | 12 | 133 | 3 | 7 | 133 | 3 |
| 5 | Plane | 158 | 151 | 7 | 7 | 7 | 105 | 7 | 32 | 105 | 7 |
| 6 | Mautic | 133 | 124 | 9 | 7 | 9 | 43 | 54 | 20 | 43 | 54 |
| 7 | Chatwoot | 168 | 156 | 12 | 6 | 12 | 102 | 3 | 45 | 102 | 3 |
| 8 | Novu | 119 | 112 | 7 | 0 | 7 | 58 | 18 | 36 | 58 | 18 |
| 9 | Marketing Skills | 53 | 53 | 0 | 0 | 0 | 0 | 53 | 0 | 0 | 53 |
| 10 | Sellbird | 80 | 74 | 6 | 6 | 6 | 34 | 3 | 31 | 34 | 3 |
| | **Total** | **1,488** | **1,418** | **70** | **28** | **70** | **737** | **221** | **432** | **737** | **221** |

Matrix `VERIFIED_COMPLETE + compatible replacement = 1,488/1,488`. No matrix row is `NOT_IMPLEMENTED`, `PARTIALLY_IMPLEMENTED`, `LICENSING_RESTRICTED` or `EXTERNAL_DEPENDENCY_BLOCKED` as a status label. The `BLOCKED_EXTERNAL` column above is the conservative final acceptance disposition, not the matrix status label.

## Per-source Campaign 2 notes

- **Formbricks (234):** 154 `NOT_TESTED` rows closed with named per-feature evidence; 73 `NOT_APPLICABLE`; 7 replacements; hosted survey widget/email/SDK boundaries remain no-claim.
- **Meilisearch (103):** 55 rows closed with named local-search evidence; 9 replacements; hosted search cluster and external embedding model remain NOT VERIFIED.
- **GrowthBook (284):** 53 rows closed with named local flag/experiment evidence; 80 rows remain `BLOCKED_EXTERNAL` for hosted experimentation; 149 `NOT_APPLICABLE`.
- **Papermark (156):** 133 rows closed with named document-room evidence; 3 external-dependency rows remain blocked; document room stays metadata/room lifecycle only.
- **Plane (158):** 105 rows closed; 7 external rows remain blocked; full Plane UX is not claimed.
- **Mautic (133):** 43 rows closed; 54 campaign-delivery rows remain blocked; no outbound message was sent.
- **Chatwoot (168):** 102 rows closed; 3 external rows remain blocked; live chat/webhook/browser SDK remain no-claim.
- **Novu (119):** 58 rows closed; 18 notification-delivery rows remain blocked; local queue/adapters only.
- **Marketing Skills (53):** no runtime module and no `NOT_TESTED` rows; 53 rows remain `BLOCKED_EXTERNAL` because content guidance cannot prove provider delivery or external engagement. Content is documented with attribution.
- **Sellbird (80):** 34 rows closed; 3 external rows remain blocked; outreach remains local drafts with human approval.

## Evidence and method

1. Recomputed matrix and final-registry counts directly from CSV fields; no hand-set counts.
2. Verified `FINAL_FEATURE_ACCEPTANCE_REGISTRY.csv` has 1,488 rows, identical ID order and identical `Final acceptance status` values to the pre-campaign registry.
3. Verified 737 `NOT_TESTED` rows each have a Campaign 2 test result, named nodes and an evidence reference; 221 `BLOCKED_EXTERNAL` rows each have a dependency-class evidence reference.
4. Verified 1,577 Campaign 2 evidence-reference paths resolve from the repository root; 0 missing.
5. Cross-checked source roll-up against `TEN_SOURCE_PROJECT_COMPLETION_REPORT.md` and `COMPLETION_DASHBOARD.md`.

Named evidence:

- `docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv`
- `docs/FEATURE_PARITY/COMPLETION_DASHBOARD.md`
- `docs/FEATURE_PARITY/SOURCES/01-formbricks.md` … `10-sellbird.md`
- `docs/FEATURE_PARITY/UNIFIED_WORKFLOW_CATALOG.md`
- `docs/FINAL_RELEASE_QA/CAMPAIGN2/evidence/skye_feature_test_results.csv` (675 rows)
- `docs/FINAL_RELEASE_QA/CAMPAIGN2/probe_unmapped_feature_results.csv` (62 rows)
- `docs/FINAL_RELEASE_QA/CAMPAIGN2/evidence/skye_test_batch_01.txt` … `09.txt`
- `docs/FINAL_RELEASE_QA/CAMPAIGN2/evidence/probe_resolution_batch_01.txt` … `04.txt`
- `docs/FINAL_RELEASE_QA/FINAL_FEATURE_ACCEPTANCE_REGISTRY.csv`

## Limits

Named node passes cover the acceptance behavior encoded by those nodes, not every possible behavior of the upstream source. No live provider, hosted deployment, mobile installer, non-Chromium browser or full product release was verified. Source acceptance remains evidence-gated; final release status is unchanged.
