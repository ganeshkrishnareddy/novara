# PROBE_UNMAPPED_RESOLUTION_REPORT — NOVARA Campaign 2

DRAFT_NOT_SUBMITTED

**Timestamp:** 2026-11-25 IST (Asia/Calcutta)
**Auditor:** Probe (Game Audit Specialist, ProgVision Games), assigned by @MausBot
**Scope:** 62 Master feature IDs assigned to Probe in NOT_TESTED_EXECUTION_QUEUE.csv (not directly named by ID in pytest).

## Counts
- Assigned to Probe: 62
- PASS: 62
- FAIL: 0
- NOT_TESTED: 0
- BLOCKED_EXTERNAL: 0

## Method
1. Read NOT_TESTED_EXECUTION_QUEUE.csv; filtered Assigned agent == Probe (62 rows).
2. For each Master ID, read Tests / evidence and Final acceptance criteria from MASTER_FEATURE_MATRIX.csv.
3. Extracted named pytest nodes (file::function) from the Tests/evidence field, including shorthand `::test_*` resolved to the preceding test file.
4. Verified each test file exists under apps/api/tests.
5. Executed each unique node with the project venv: `D:/NOVARA/.venv/Scripts/python.exe -m pytest <node> -v --tb=short --junitxml=<xml>` from D:/NOVARA.
6. Saved full command output to docs/FINAL_RELEASE_QA/CAMPAIGN2/evidence/probe_resolution_batch_01..04.txt.
7. Mapped pass/fail per node to every feature referencing it. No external/no-claim boundary keyword found in any assigned feature; no feature kept NOT_TESTED/BLOCKED_EXTERNAL.

## Unique test nodes executed (21)
- `apps/api/tests/test_api_surface_p0.py::test_workspace_can_be_created_switched_and_administered` -> PASSED
- `apps/api/tests/test_customer_profile_p0.py` -> PASSED
- `apps/api/tests/test_documents.py` -> PASSED
- `apps/api/tests/test_documents.py::test_dataroom_and_document_metadata_lifecycle` -> PASSED
- `apps/api/tests/test_documents.py::test_dataroom_name_must_be_unique_per_workspace` -> PASSED
- `apps/api/tests/test_documents.py::test_document_filters_and_bad_payloads` -> PASSED
- `apps/api/tests/test_documents.py::test_documents_and_rooms_are_workspace_isolated` -> PASSED
- `apps/api/tests/test_documents.py::test_room_delete_guarded_by_existing_document_metadata` -> PASSED
- `apps/api/tests/test_documents_p0.py::test_document_journey_has_enforced_sharing_controls_and_isolation` -> PASSED
- `apps/api/tests/test_documents_p0.py::test_document_view_notifies_salesperson_and_reaches_customer_timeline` -> PASSED
- `apps/api/tests/test_documents_p0.py::test_download_is_policy_controlled_and_publishes_a_shared_event` -> PASSED
- `apps/api/tests/test_feedback_lifecycle_p0.py` -> PASSED
- `apps/api/tests/test_integration.py::test_module_event_appears_in_shared_audit_log` -> PASSED
- `apps/api/tests/test_marketing_journey_p0.py::test_all_listed_lifecycle_events_are_registered_emitted_and_queryable` -> PASSED
- `apps/api/tests/test_phase4_ui_contract.py` -> PASSED
- `apps/api/tests/test_project_membership_p0.py::test_member_management_requires_project_admin_and_valid_identity` -> PASSED
- `apps/api/tests/test_project_membership_p0.py::test_project_membership_registry_and_roles` -> PASSED
- `apps/api/tests/test_projects.py::test_project_bad_payloads_and_missing_rows` -> PASSED
- `apps/api/tests/test_projects.py::test_project_crud_items_completion_and_events` -> PASSED
- `apps/api/tests/test_ui_wiring.py` -> PASSED
- `apps/api/tests/test_ui_wiring.py::test_workspace_admin_surface_is_routed_and_wired` -> PASSED

## Per-ID disposition
| Master ID | Source | Module | Outcome | Test node(s) |
|---|---|---|---|---|
| FB-001 | Formbricks | feedback | PASS | apps/api/tests/test_feedback_lifecycle_p0.py; apps/api/tests/test_ui_wiring.py; apps/api/tests/test_phase4_ui_contract.py |
| FB-012 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-013 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-017 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-018 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-023 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-027 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-033 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-034 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-035 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-037 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-041 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-042 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-046 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-047 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-048 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-049 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-050 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-051 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-052 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-053 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-069 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-071 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-192 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-194 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-195 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-196 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-197 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-198 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-199 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-200 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-201 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-202 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-203 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| FB-204 | Formbricks | Feedback / Surveys | PASS | apps/api/tests/test_ui_wiring.py |
| MS-008 | Meilisearch | search | PASS | apps/api/tests/test_ui_wiring.py |
| MS-013 | Meilisearch | search | PASS | apps/api/tests/test_ui_wiring.py |
| MS-019 | Meilisearch | search | PASS | apps/api/tests/test_ui_wiring.py |
| MS-024 | Meilisearch | search | PASS | apps/api/tests/test_ui_wiring.py |
| MS-026 | Meilisearch | search | PASS | apps/api/tests/test_ui_wiring.py |
| MS-027 | Meilisearch | search | PASS | apps/api/tests/test_ui_wiring.py |
| MS-043 | Meilisearch | search | PASS | apps/api/tests/test_ui_wiring.py |
| MS-046 | Meilisearch | search | PASS | apps/api/tests/test_ui_wiring.py |
| MS-047 | Meilisearch | search | PASS | apps/api/tests/test_ui_wiring.py |
| MS-061 | Meilisearch | search | PASS | apps/api/tests/test_ui_wiring.py |
| PM-001 | Papermark | documents | PASS | apps/api/tests/test_documents.py; apps/api/tests/test_documents_p0.py::test_document_journey_has_enforced_sharing_controls_and_isolation; apps/api/tests/test_ui_wiring.py |
| PM-004 | Papermark | documents | PASS | apps/api/tests/test_documents.py::test_dataroom_and_document_metadata_lifecycle; apps/api/tests/test_documents.py::test_document_filters_and_bad_payloads |
| PM-005 | Papermark | documents | PASS | apps/api/tests/test_documents.py::test_dataroom_and_document_metadata_lifecycle; apps/api/tests/test_documents.py::test_document_filters_and_bad_payloads |
| PM-006 | Papermark | documents | PASS | apps/api/tests/test_documents.py::test_dataroom_and_document_metadata_lifecycle; apps/api/tests/test_documents.py::test_documents_and_rooms_are_workspace_isolated |
| PM-008 | Papermark | documents | PASS | apps/api/tests/test_documents.py::test_dataroom_and_document_metadata_lifecycle; apps/api/tests/test_documents.py::test_room_delete_guarded_by_existing_document_metadata |
| PM-017 | Papermark | documents + events | PASS | apps/api/tests/test_documents.py::test_dataroom_and_document_metadata_lifecycle; apps/api/tests/test_documents.py::test_room_delete_guarded_by_existing_document_metadata; apps/api/tests/test_integration.py::test_module_event_appears_in_shared_audit_log |
| PM-051 | Papermark | documents | PASS | apps/api/tests/test_documents.py::test_dataroom_and_document_metadata_lifecycle; apps/api/tests/test_documents.py::test_dataroom_name_must_be_unique_per_workspace; apps/api/tests/test_documents.py::test_room_delete_guarded_by_existing_document_metadata |
| PM-052 | Papermark | documents | PASS | apps/api/tests/test_documents.py::test_dataroom_name_must_be_unique_per_workspace; apps/api/tests/test_documents.py::test_dataroom_and_document_metadata_lifecycle |
| PM-053 | Papermark | documents | PASS | apps/api/tests/test_documents.py::test_dataroom_name_must_be_unique_per_workspace |
| PM-054 | Papermark | documents | PASS | apps/api/tests/test_documents.py::test_room_delete_guarded_by_existing_document_metadata |
| PM-073 | Papermark | documents + events | PASS | apps/api/tests/test_documents_p0.py::test_document_view_notifies_salesperson_and_reaches_customer_timeline; apps/api/tests/test_documents_p0.py::test_download_is_policy_controlled_and_publishes_a_shared_event |
| PM-088 | Papermark | documents + events | PASS | apps/api/tests/test_documents.py::test_dataroom_and_document_metadata_lifecycle; apps/api/tests/test_integration.py::test_module_event_appears_in_shared_audit_log |
| PL-001 | Plane | workspaces | PASS | apps/api/tests/test_api_surface_p0.py::test_workspace_can_be_created_switched_and_administered; apps/api/tests/test_ui_wiring.py::test_workspace_admin_surface_is_routed_and_wired |
| PL-002 | Plane | modules/projects | PASS | apps/api/tests/test_projects.py::test_project_crud_items_completion_and_events; apps/api/tests/test_projects.py::test_project_bad_payloads_and_missing_rows |
| PL-003 | Plane | projects | PASS | apps/api/tests/test_project_membership_p0.py::test_project_membership_registry_and_roles; apps/api/tests/test_project_membership_p0.py::test_member_management_requires_project_admin_and_valid_identity |
| MT-115 | Mautic | events | PASS | apps/api/tests/test_marketing_journey_p0.py::test_all_listed_lifecycle_events_are_registered_emitted_and_queryable |
| CW-129 | Chatwoot | Platform / Workspaces | PASS | apps/api/tests/test_customer_profile_p0.py |

## Evidence files
- evidence/probe_resolution_batch_01.txt
- evidence/probe_resolution_batch_02.txt
- evidence/probe_resolution_batch_03.txt
- evidence/probe_resolution_batch_04.txt

## Limitations
- No application code, tests, README, site, registry, or shared reports were modified.
- No commits, pushes, tags, deployments, provider contacts, or real credentials were used.
- runtime_smoke.py was referenced by one feature but not executed as a pytest node (it is a script, not a test); its referenced pytest nodes (test_documents.py etc.) were executed instead.
- All named pytest nodes PASSED; no FAIL/NOT_TESTED/BLOCKED_EXTERNAL outcomes among the 62 assigned features.
- Visual/UI claims beyond the named test nodes were not independently re-verified in this batch.

## Timestamp: 2026-11-25 IST