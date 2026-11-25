# Chatwoot-compatible support P1 — named acceptance evidence (2026-11-23)

Tests drive the real FastAPI app with isolated databases; no external channel,
provider credential or mock delivery is used.

```
D:\NOVARA\.venv\Scripts\python.exe -m pytest apps/api/tests/test_chatwoot_support_p1.py -q --disable-warnings
# 19 passed, 1 warning in 17.03s
```

| Master ID | Named test | Proved locally |
|---|---|---|
| CW-005 | `test_cw005_team_creation_membership_and_assignment` | Team creation, membership, team assignment, team filtering and workspace isolation. |
| CW-008 | `test_cw008_routing_rule_trace_and_manual_assignment_wins` | Stored routing rule acts on a new unassigned ticket with a traceable event; manual assignment still wins. |
| CW-012 | `test_cw012_labels_create_apply_filter_and_report_per_workspace` | Labels created, applied, filtered and reported per workspace. |
| CW-013 | `test_cw013_typed_attributes_on_contact_and_ticket_filter_and_export` | Typed attributes on contacts/tickets, filtering and export. |
| CW-016 | `test_cw016_contact_note_is_internal_only_audited_and_never_delivered` | Support-owned contact note uses the path contact id, is contact-only, never becomes a message, is audited with the verified actor, and denies foreign/read-only writes. |
| CW-017 | `test_cw017_contact_timeline_correlates_tickets_and_messages_in_order` | Timeline derives correlation ids only from real `ticket.contact_linked` links, returns ordered events, rejects cross-tenant rows. |
| CW-023 | `test_cw023_saved_reply_expand_into_draft_without_sending` | Saved reply creation and local expansion (unresolved variables preserved); no external delivery. UI "insert into reply box" action is not yet wired, so this row stays partial. |
| CW-024 | `test_cw024_macro_applies_ordered_local_changes_atomically_with_audit` | Macro action allow-list now applies to both list and JSON bodies; external/unknown/empty actions get 422; apply is atomic and audited. |
| CW-028 | `test_cw028_every_supported_filter_narrows_and_invalid_filters_return_422` | Every supported filter narrows safely; invalid filters get 422; no arbitrary SQL path. |
| CW-051 | `test_cw051_conversation_rule_reacts_locally_and_leaves_run_trace` | Local rule reacts to a real ticket event and leaves a run trace; external actions unavailable. |
| CW-075 | `test_cw075_segment_returns_exact_stored_rule_matches_and_is_reusable` | Persisted segment returns exactly matching contacts and can be reused through the API; UI reuse is not yet exercised by the test, so this row stays partial. |
| CW-086 | `test_cw086_published_public_article_readable_and_draft_hidden` | Published article readable by intended audience, draft hidden. |
| CW-093 | `test_cw093_dashboard_counts_equal_workspace_scoped_sql_counts` | Dashboard counts equal workspace-scoped SQL counts. |
| CW-095 | `test_cw095_conversation_metrics_come_from_rows_and_honour_date_filters` | Volume/response metrics from real rows with date filters. |
| CW-100 | `test_cw100_csat_average_and_response_rate_use_stored_responses_and_filters` | CSAT average and response rate from stored responses with date/inbox filters. |
| CW-102 | `test_cw102_resolution_creates_one_local_survey_and_no_message` | Resolution creates one local survey row and no external message. |
| CW-118 | `test_cw118_token_scope_rotation_and_revocation_take_effect_immediately` | Token scope enforced server-side; rotation and revocation take effect immediately. |
| CW-158 | `test_cw158_fresh_schema_creates_every_support_table_and_workspace_fk` | Fresh schema creates every support table and workspace foreign key. |
| CW-166 | `test_cw166_unsigned_or_replayed_webhook_rejected_and_valid_event_creates_one_ticket` | Real HMAC-SHA256 inbound webhook at `.../tickets/webhooks/inbound`: 300s timestamp tolerance, forged/tampered/stale signature rejection, durable replay rejection (409), exactly one local ticket and one event per external id, workspace isolation. Signature secret is a documented local default overridable by `NOVARA_SUPPORT_WEBHOOK_SECRET`; no provider-specific standard is claimed. |

The CRM `.../contacts/{id}/notes` route in `main.py` still requires `contact_id`
in its body; CW-016 uses the support-owned path-id route instead. This is a
documented route difference, not a weakened acceptance test.
