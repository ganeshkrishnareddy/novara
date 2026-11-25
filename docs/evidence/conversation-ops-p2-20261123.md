# Evidence — clean-room conversation operations P2 cluster (T-098)

Date: 2026-11-23 (Asia/Calcutta). All work is local and uncommitted at Git HEAD `73e9f76`.

## Scope

Fifteen named acceptance tests were added in
`apps/api/tests/test_conversation_ops_p2.py` (thirteen feature rows plus one
extra snooze-expiry case and one workspace-isolation case) and one static UI
wiring guard in `apps/api/tests/test_ui_wiring.py`. Every test drives the real
FastAPI app against real persisted, workspace-scoped rows, including real
invited second workspace members. No app code is mocked.

The clean-room module `apps/api/novara_core/modules/conversation_ops.py` owns
twelve additive workspace-scoped tables created by Alembic revision
`c8d0e1f2a3b4` (down revision `b7c9d0e1f2a3`): `agent_presence`,
`conversation_snoozes`, `note_mentions`, `typing_indicators`,
`message_receipts`, `conversation_mutes`, `conversation_folders`,
`inbox_hours`, `hours_slots`, `hours_overrides`, `inbox_holidays`,
`reply_dedup`. It extends NOVARA's existing support tickets/messages and
labels without altering their tables.

## Delivery boundary (important)

Chatwoot is FOSSA-licensed; nothing was copied. There is no ActionCable or
WebSocket transport (collision checks are polling-only), no outbound
notification delivery (mentions publish through the local event spine), no
real-time push service and no external holiday API. Business hours use the
standard-library `zoneinfo` database when the host supplies one; on Windows
builds without `tzdata`, a documented fixed-offset table (UTC, Asia/Kolkata,
Tokyo, London, Berlin, New York, and explicit `UTC±HH:MM` strings) is used,
so DST is not applied in that fallback. The API contract reports
`external_calls: false`, `external_delivery: false`, and
`timezone_source` explicitly. Replies are recorded as local `TicketMessage`
rows with idempotency keys; no email is sent.

## Row-by-row evidence

| Row | Named test | Verified behaviour |
| --- | --- | --- |
| CW-006 | `test_cw006_agent_presence_states_drive_visibility` | Per-member online/away/offline presence persists, is listable per workspace, rejects invalid states and is visible to teammates. |
| CW-010 | `test_cw010_snoozed_conversations_leave_and_reenter_the_queue`, `test_cw010_due_snoozes_return_to_the_active_queue` | Snoozes leave the active queue, reject past times, are idempotent and re-enter on unsnooze or the due-sweep. A directly seeded past-due row is deactivated by `expire-due`. |
| CW-020 | `test_cw020_mentions_notify_active_teammates_in_private_notes` | Mentions in internal notes notify active members only, deduplicate repeated ids and appear in the mentioned member's list through local events. |
| CW-021 | `test_cw021_collision_detection_and_duplicate_reply_prevention` | Live typing indicators raise collision warnings, replies fail closed with 409 unless explicitly forced, and duplicate `client_msg_id` retries are refused. |
| CW-022 | `test_cw022_delivery_and_read_receipts_are_per_message_and_user` | Delivery/read receipts are stored per message and per user, and reads are listed independently. |
| CW-025 | `test_cw025_bulk_actions_apply_status_assignee_and_labels` | Bulk actions update status, assignee and an existing label on up to 100 conversations; missing labels/assignees/tickets fail closed. |
| CW-029 | `test_cw029_saved_filter_folders_show_live_counts` | Named filter folders compute live counts from current tickets, reject unsupported filters and duplicates, and can be deleted. |
| CW-032 | `test_cw032_mute_suppresses_notifications_for_one_conversation` | Mutes are per user per conversation, listed only for their owner, reversible and fail closed on unknown tickets. |
| CW-052 | `test_cw052_business_hours_are_timezone_aware_and_per_inbox` | Weekly schedules evaluate in the configured timezone, show per-inbox availability and reject duplicate inboxes or unknown timezones. |
| CW-053 | `test_cw053_date_overrides_reduce_or_close_hours` | Date overrides supersede weekly schedules for full closure or reduced windows. |
| CW-054 | `test_cw054_regional_holidays_close_dates_in_one_click` | Operator-supplied holiday/region lists close dates in one click without any external lookup, deduplicate and reject malformed dates. |
| CW-055 | `test_cw055_split_shifts_allow_multiple_windows_per_day` | Multiple windows per weekday create split shifts with a lunch gap, and invalid windows are rejected. |
| CW-056 | `test_cw056_away_message_is_shown_outside_business_hours` | Outside hours return the configured away message (or a safe default) with no external calls. |
| Isolation | `test_conversation_ops_workspace_isolation` | A second workspace sees no presence/folders, cannot mute, list or delete this workspace's rows and cannot evaluate its inbox hours. |
| UI | `test_conversation_ops_route_controls_are_rendered_and_dispatched` | The `conversation-ops` Operations route renders presence, snoozes, mentions, collision/receipts, bulk/folders/mutes and inbox hours; every control has one dispatcher and one form handler. |

## Commands and results

- `pytest apps/api/tests/test_conversation_ops_p2.py` -> **15 passed, 1 warning**.
- `pytest apps/api/tests/test_conversation_ops_p2.py apps/api/tests/test_ui_wiring.py`
  -> **49 passed, 1 warning**.
- `node --check apps/web/app.js` -> exit 0.
- `alembic heads` -> single head `c8d0e1f2a3b4`.
- `scripts/migration_roundtrip_check.py b7c9d0e1f2a3` -> **ROUND TRIP PASS:
  upgrade -> downgrade -> upgrade, existing data preserved**.
- Full-suite result is recorded in `docs/TEST_RESULTS.md`.

## Not claimed

No Chatwoot-hosted API, widget SDK, CLI, realtime WebSocket transport,
external MFA, dashboard apps, help centre, outbound email/push, hosted
holiday service or IANA DST rules in the fixed-offset fallback are claimed.
Other Chatwoot rows remain in their existing matrix states.