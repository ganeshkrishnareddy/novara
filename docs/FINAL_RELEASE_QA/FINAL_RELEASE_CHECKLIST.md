# Final release checklist — Campaign 2

Original timestamp: 2026-11-25 12:37 IST. Updated 2026-11-25 (IST) after marketing-site live deployment. Verdict: **LOCAL RELEASE ACCEPTED: NO; MARKETING SITE LIVE.**

| Checkpoint | Status | Evidence |
|---|---|---|
| 0 Baseline / safety | DONE | `CAMPAIGN2/CHECKPOINT_0_BASELINE.md`; HEAD `f1dcfef`; uncommitted work preserved; no reset/clean/push/tag |
| 1 Feature inventory | DONE | 1,488 rows, 0 omissions, 0 duplicates in `FEATURE_BY_FEATURE_ACCEPTANCE.csv` and `FINAL_FEATURE_ACCEPTANCE_REGISTRY.csv` |
| 2 Full feature testing | EVIDENCE CLOSED, STATUS UNCHANGED | 737/737 formerly `NOT_TESTED` rows have individual named evidence; `NOT_TESTED_FEATURE_CLOSURE_REPORT.md` |
| 3 Ten source platforms | DONE (inventory + closure) | `TEN_SOURCE_PROJECT_ACCEPTANCE_REPORT.md`; 1,418 verified + 70 replacements in matrix |
| 4 Cross-module workflows | DONE (local) | `END_TO_END_WORKFLOW_REPORT.md` — 10/10 fresh representative tests; prior W1–W8 0 FAIL |
| 5 Integrations | LOCAL ONLY | `INTEGRATION_ACCEPTANCE_REPORT.md` — 27/27 fresh local contract checks; live 0/21 |
| 6 Security and reliability | DONE (local) | `SECURITY_AND_REGRESSION_REPORT.md` — 17/17 fresh checks; not an audit |
| 7 UI/UX/accessibility | DONE (Chromium) | 20/20 browser checks at root and subpath; 0 console problems |
| 8 Database / deployment | DB PASS; marketing site live; backend deploy unverified | single Alembic head `e0f1a2b3c4d5`; Pages rerun succeeded, backend/hosted deployment 0% |
| 9 GitHub community feature | DONE, advisory gap | `README_AND_COMMUNITY_AUDIT.md`; no banned engagement practice; README lacks explicit Star/Fork/PR URLs |
| 10 Professional README | DONE, hash unchanged | `README_FINAL_AUDIT.md` 40 PASS / 0 FAIL; SHA-256 `e3b1838…76b64c` |
| 11 Marketing website | DONE, validated locally | validator 35 passed / 0 failed; browser 20/20 root and subpath |
| 12 Marketing website launch | LIVE | `MARKETING_SITE_DEPLOYMENT_REPORT.md`; `https://ganeshkrishnareddy.github.io/novara/` and checked assets HTTP 200 |
| 13 Final regression | BASELINE DONE | 1,641 passed, 4 warnings, exit 0; no code change in Campaign 2, so no rerun required |
| 18 Final registry | DONE | `FINAL_FEATURE_ACCEPTANCE_REGISTRY.csv`; 0 PARTIAL; statuses unchanged; 1,577 evidence paths resolve |
| 20 Independent audits | DONE | `AUDIT_RECONCILIATION.md`, `LICENSING_CLAIMS_AUDIT.md`, `REGISTRY_INTEGRITY_AUDIT.md`, Shield/Probe/Skye Campaign 2 reports |
| 21 External blocker grouping | DONE | `EXTERNAL_BLOCKER_RESOLUTION_REPORT.md`; 221 rows grouped; live NOT VERIFIED |
| 22 Repair/retest log | DONE | `REPAIR_AND_RETEST_LOG.md`; no new application/test repair in Campaign 2 |
| 23 Release gate | **NOT MET** | `FINAL_RELEASE_BLOCKERS.md` |

## Metric separation

- Final feature acceptance: PASS 28 / 1,488 = 1.88%; accepted-like 98 / 1,488 = 6.59%.
- Campaign 2 evidence closure: 737 / 737 formerly `NOT_TESTED` rows = 100%.
- Fresh local test executions: 811 / 811 passed.
- Integration local contract checks: 27 / 27 passed; live provider verification 0 / 21 = 0%.
- Marketing-site deployment-platform verification: 100% (Pages enabled, workflow succeeded, live URL/assets HTTP 200).
- Backend/hosted deployment-platform verification: 0% (no backend deployment performed).

## Remaining owner actions

1. Marketing-site launch is complete; no further owner action is needed for the public page.
2. Choose NOVARA's licence; no fully open-source claim until then.
3. Decide whether to explicitly promote conservative final statuses; Campaign 2 does not do so automatically.
4. Resolve Docker, live PostgreSQL, hosted deployment and signed-installer verification.
5. Provide explicit authorization and isolated credentials before any live provider verification.
6. Complete name/trademark/domain availability review.

No Git commit, push, tag, force-push, reset, clean or deployment was performed during Campaign 2. After Campaign 2, the marketing site was launched by enabling Pages and rerunning the existing workflow; no new Git commit, push or backend deployment was performed. The publication commit remains `f1dcfefe162faac644e974f075a411eb0975f4cb`.
