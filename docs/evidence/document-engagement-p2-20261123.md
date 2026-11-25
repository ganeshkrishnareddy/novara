# Evidence — clean-room document engagement P2 cluster (T-095)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Thirteen named acceptance tests were added in
`apps/api/tests/test_document_engagement_p2.py` (twelve feature rows plus one
workspace-isolation test) and one static UI wiring guard in
`apps/api/tests/test_ui_wiring.py`. Every test drives the real FastAPI app
against real persisted, workspace-scoped rows. No app code is mocked.

The clean-room module `apps/api/novara_core/modules/document_engagement.py`
owns six additive workspace-scoped tables created by Alembic revision
`f5a7b8c9d0e1` (down revision `e4f5a7b8c9d0`). It extends NOVARA's existing
documents module with metadata/folder moves, version promotion and link
repoint, name search, reactions, feedback, annotations, engagement events,
internal-visit exclusion, a click route and aggregated analytics.

## Delivery boundary (important)

These Papermark rows are AGPL community patterns and were implemented
clean-room: no Papermark server source was copied. No hosted viewer, outbound
email, geolocation service or external analytics provider is contacted.
Country/city and device/OS/platform fields are caller-supplied metadata, never
resolved through an external lookup (`external_geolocation: false`). This
verifies NOVARA's own local adapter, not source-equivalence with Papermark.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| PM-007 | `test_pm007_document_metadata_rename_and_folder_move` | A document can be renamed and moved into a workspace folder; a missing folder is a 404, an empty change a 422, and the folder can be cleared. |
| PM-010 | `test_pm010_version_promotion_and_link_repoint` | Promoting a version makes it the single primary and can repoint an external URL; a missing version is a 404. |
| PM-018 | `test_pm018_document_name_search_is_case_insensitive` | Name search matches a case-insensitive substring within the workspace; an empty query is a 422. |
| PM-024 | `test_pm024_reactions_are_deduplicated_and_removable` | Page reactions persist, deduplicate per user/page/key, reject unknown keys and can be removed. |
| PM-025 | `test_pm025_feedback_records_rating_and_author` | Feedback stores a validated 1–5 rating and author; an out-of-range rating is a 422. |
| PM-027 | `test_pm027_annotations_attach_to_pages_and_versions` | Annotations persist with kind/page/position and an optional version; invalid kinds and missing versions are rejected. |
| PM-076 | `test_pm076_scroll_depth_and_completion_are_aggregated` | Analytics compute average scroll depth and completion rate; an out-of-range depth is a 422. |
| PM-077 | `test_pm077_video_view_analytics_are_recorded` | Video engagement events contribute view counts and average position. |
| PM-083 | `test_pm083_visitor_location_is_caller_supplied_metadata` | Country/city analytics aggregate caller-supplied location with `external_geolocation: false`. |
| PM-084 | `test_pm084_device_os_and_platform_analytics` | Client information per view is aggregated by device and platform. |
| PM-085 | `test_pm085_internal_visits_are_excluded_from_analytics` | Registering internal visitors flags and excludes their events; duplicates and invalid match types are rejected; removal works. |
| PM-091 | `test_pm091_click_route_records_target_and_counts` | The dedicated click route records a target and feeds click analytics; an empty target is a 422. |
| Isolation | `test_document_engagement_workspace_isolation` | A second workspace cannot read this workspace's analytics/reactions or address their document, reaction or internal-visitor IDs. |
| UI | `test_document_engagement_route_controls_are_rendered_and_dispatched` | The `document-engagement` Operations route renders documents, internal visitors and collaboration forms; every control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_document_engagement_p2.py` -> **13 passed, 1 warning**.
- `pytest apps/api/tests/test_document_engagement_p2.py apps/api/tests/test_ui_wiring.py`
  -> **44 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `f5a7b8c9d0e1`.
- `scripts/migration_roundtrip_check.py e4f5a7b8c9d0` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md`.

## Not claimed

No Papermark-hosted feature, outbound digest email, hosted viewer, external
geolocation, paid unlimited capacity, e-signature legality, OAuth/passkey
providers, MCP server or published SDK is claimed. Rows outside this cluster
remain in their existing matrix states.