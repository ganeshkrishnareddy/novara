# End-to-end workflow report — Campaign 2

Timestamp: 2026-11-25 12:23 IST. Repository `D:\NOVARA`, HEAD `f1dcfefe162faac644e974f075a411eb0975f4cb`. Scope: the ten cross-source workflow outcomes in `docs/FEATURE_PARITY/UNIFIED_WORKFLOW_CATALOG.md` and the eight recorded harness workflows in `docs/QA/END_TO_END_WORKFLOW_RESULTS.md`.

## Verdict

Local workflow verification is **PASS for the tested local scopes**, with explicit no-send/no-hosted-provider boundaries. This does not establish external provider delivery, a hosted deployment or full product release.

## Fresh Campaign 2 verification

A fresh isolated-database pytest run executed one representative, directly relevant test for each catalog workflow:

```powershell
cd D:\NOVARA
.\.venv\Scripts\python.exe -m pytest `
  "apps/api/tests/test_search.py::test_search_across_all_shared_types" `
  "apps/api/tests/test_support_inbox.py::test_shared_inbox_is_workspace_scoped_audited_and_local_only" `
  "apps/api/tests/test_marketing.py::test_campaign_metrics_rollups_summary_and_events" `
  "apps/api/tests/test_sales.py::test_deal_lifecycle_filters_summary_activities_and_events" `
  "apps/api/tests/test_feedback_lifecycle_p0.py::test_survey_lifecycle_controls_responses_and_is_audited" `
  "apps/api/tests/test_documents.py::test_dataroom_and_document_metadata_lifecycle" `
  "apps/api/tests/test_analytics.py::test_experiment_crud_results_and_events" `
  "apps/api/tests/test_projects.py::test_project_crud_items_completion_and_events" `
  "apps/api/tests/test_jobs.py::test_enqueue_is_idempotent_and_audited" `
  "apps/api/tests/test_marketing_skills_p1.py::test_mk001_ab_testing_skill_is_pinned_verified_and_isolated" `
  -v --tb=short --junitxml=docs\FINAL_RELEASE_QA\CAMPAIGN2\evidence\workflow_verification_20261125.xml
```

Observed: **10 passed, 1 warning, exit 0 in 14.04s**. The warning is the known Starlette/httpx TestClient deprecation notice. Evidence: `CAMPAIGN2/evidence/workflow_verification_20261125.txt` and `...xml`. Each test used the shared `conftest.py` fixture that creates a fresh in-memory SQLite database and restores global app state.

## Workflow A–J coverage

| ID | Catalog workflow | Fresh representative test | Result | Honest boundary |
|---|---|---|---|---|
| A | Universal search across the workspace | `test_search.py::test_search_across_all_shared_types` | PASS | Local workspace-scoped search; not a hosted search cluster |
| B | Customer inbox / shared conversation | `test_support_inbox.py::test_shared_inbox_is_workspace_scoped_audited_and_local_only` | PASS | Local/no-send; no live chat channel or browser SDK |
| C | Campaign lifecycle and measurement | `test_marketing.py::test_campaign_metrics_rollups_summary_and_events` | PASS | Delivery remains `NOT_EXECUTED`; no outbound message |
| D | Sales pipeline from lead to close | `test_sales.py::test_deal_lifecycle_filters_summary_activities_and_events` | PASS | Outreach remains a local draft with approval gate |
| E | Feedback and satisfaction loop | `test_feedback_lifecycle_p0.py::test_survey_lifecycle_controls_responses_and_is_audited` | PASS | Local surveys/responses; no hosted widget or survey email |
| F | Document room with tracked views | `test_documents.py::test_dataroom_and_document_metadata_lifecycle` | PASS | Metadata/room lifecycle only; no file I/O and no document-room UI |
| G | Experiment and metric evaluation | `test_analytics.py::test_experiment_crud_results_and_events` | PASS | Local clean-room analysis; no hosted experimentation SDK/control plane |
| H | Work management and cycles | `test_projects.py::test_project_crud_items_completion_and_events` | PASS | Core project/work-item APIs; full Plane UX is not claimed |
| I | Notification workflow and adapters | `test_jobs.py::test_enqueue_is_idempotent_and_audited` | PASS | Local queue/adapters only; no outbound provider call |
| J | Guided marketing content and growth plays | `test_marketing_skills_p1.py::test_mk001_ab_testing_skill_is_pinned_verified_and_isolated` | PASS | Content/manifest verification; no runtime skill module, external traffic or engagement automation |

## Recorded eight-workflow harness

`docs/QA/END_TO_END_WORKFLOW_RESULTS.md` and `artifacts/final_qa_2026-11-24/evidence/qa_e2e_log.jsonl` record 61 synthetic local records: 52 PASS, 9 informational, 0 FAIL across W1–W8. Boundaries recorded there remain in force:

- W2 campaign delivery: `NOT_EXECUTED`.
- W4 document link notifications: local records only.
- W5 experimentation: local analysis only.
- W7 automation: in-app only.
- W8 AI-assisted operation: simulated local agent, no hosted model.

## Evidence resolution

- `CAMPAIGN2/evidence/workflow_verification_20261125.txt`
- `CAMPAIGN2/evidence/workflow_verification_20261125.xml`
- `docs/QA/END_TO_END_WORKFLOW_RESULTS.md`
- `artifacts/final_qa_2026-11-24/evidence/qa_e2e_log.jsonl`
- `artifacts/final_qa_2026-11-24/test-results/e2e-console.txt`
- `docs/FEATURE_PARITY/UNIFIED_WORKFLOW_CATALOG.md`

## Limitations

No real email, SMS, WhatsApp, push, payment, hosted AI, hosted search, hosted experimentation SDK or external campaign delivery was attempted. Non-Chromium browsers and hosted deployment were not verified. Workflow PASS results are local behavior evidence, not release acceptance for the full 1,488-feature inventory.
