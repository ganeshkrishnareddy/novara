# Sellbird P1 evidence — 2026-11-23

## Scope and method

- Acceptance suite: `apps/api/tests/test_sellbird_safety_p1.py` — **9 named tests / 10 passed** (`python -m pytest apps/api/tests/test_sellbird_safety_p1.py -q --disable-warnings`; the extra case is the blank-footer parametrization).
- Every test drives the real FastAPI app against the shared test database, uses real workspace rows and bearer sessions, and asserts over persisted state and audit events.
- `socket.socket.connect` is patched to fail in the network-sensitive tests: any accidental outbound connection fails the test loudly. No test or implementation presents a local mock as a delivered message.
- The deliberate product decision is that this build has **no send route and no sender role**. These rows close against their documented acceptance criteria (review-only drafts, gates, opt-outs, audited agents, compliance footer, proof that nothing can send), not by adding autonomous delivery.

## Implementation touched

- `apps/api/novara_core/modules/outreach_safety.py`: workspace policy/footer, opt-outs, suppressions (reason, scope, expiry, revocation), and the deterministic pre-send gate; all changes emit audit events.
- `apps/api/novara_core/workflow.py`, `apps/api/novara_core/models.py`, `apps/api/novara_core/main.py`: workspace-scoped personalised draft creation, approval, review-only outbox listing and footer injection.
- `apps/api/novara_core/modules/agents.py`: local-only agent configs/runs with step limits, human approval and audit events; no `sender` role and no fabricated model output.
- `apps/api/novara_core/modules/adapters.py`: local mock invocations always report `delivered: false`.

## Test-to-feature evidence

| Feature | Named test | Verified behaviour |
| --- | --- | --- |
| SB-018 | `test_sb018_personalised_draft_uses_workspace_rows_rejects_unresolved_and_stays_draft` | Subject/body variables resolve from workspace contact and company rows; unknown or unresolved variables return 422 without a draft row; every draft stays `draft` with no approver. |
| SB-021 | `test_sb021_outbox_listing_is_workspace_scoped_filtered_ordered_and_review_only` | Listing is workspace-scoped, status-filtered and ordered against persisted rows; foreign workspace gets 403; repeated listing creates no adapter calls or events and no network traffic. |
| SB-024 | `test_sb024_presend_gate_blocks_failed_conditions_and_passing_never_sends` | Unapproved, blank-subject, missing-footer and suppressed drafts fail the gate and cannot be approved; a passing draft reports `blocked_no_delivery_adapter`; no adapter call or delivery occurs. |
| SB-030 | `test_sb030_opt_out_blocks_approval_and_is_audited` | Opt-out sets `do_not_contact`, creates an active suppression with reason `opt_out`, emits `outreach.optout_recorded`, blocks the gate and approval, and is listable; no `outreach.approved` event. |
| SB-031 | `test_sb031_suppression_list_reason_scope_expiry_blocks_with_recorded_reason` | Suppression records reason/scope/expiry, blocks approval with the recorded reason in `outreach.gate_rejected`; an expired entry no longer blocks; revocation is audited and removes the block. |
| SB-038 | `test_sb038_agent_configs_runs_are_audited_limited_and_human_approved` | Local agent config has no fabricated output, rejects a `sender` role and over-limit steps, waits for approval, denies a sales_rep approver, and records create/run/status/approve events with the real actor. |
| SB-042 | `test_sb042_no_role_or_route_can_send_in_this_build` | OpenAPI and route tables contain no send/sender/outbox path, no explicit permission contains `send`, no agent role can send, and a configured provider invoked with `send` still reports `delivered: false`; approving a draft never sends. |
| SB-079 | `test_sb079_drafts_carry_configured_compliance_footer_and_cannot_be_sent` (+ parametrized blank-footer rejection) | Default footer is appended on intake; an owner-updated footer replaces it on new drafts and emits `outreach.footer_updated`; blank footers are rejected with 422; no adapter call or delivered event is produced. |

## Decision record

- These rows are closed as verified **local, review-only** behaviour. No real email, SMS, WhatsApp or other outbound delivery is implemented or claimed.
- If a delivery adapter is ever added, it needs its own authorised feature rows, per-message human approval and separate security review; these rows do not grant that capability.
