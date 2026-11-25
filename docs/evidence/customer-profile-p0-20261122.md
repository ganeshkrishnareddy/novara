# T-055 evidence — P0 Customer Profile cluster (2026-11-22)

## Scope

| ID | Source feature | Acceptance evidence |
| --- | --- | --- |
| CW-014 | Contact profiles | `test_customer_profile_p0.py::test_ticket_belongs_to_exactly_one_existing_workspace_contact`, `::test_contact_profile_surfaces_only_its_linked_conversations` |
| CW-129 | Accounts and account memberships | `::test_one_user_can_belong_to_multiple_workspaces`, `::test_suspension_revokes_support_access_immediately_and_can_be_reversed`, `::test_membership_changes_validate_roles_status_and_last_owner` |

Clean-room implementation only; no Chatwoot code, bundle or schema was copied.

## What was built

- `modules/support.py`: `GET /tickets?contact_id=` filters to one validated
  workspace contact; a foreign or guessed id returns 422.
- `apps/web/app.js`: the contact profile now loads its linked conversations and
  renders them as a Support conversations section with links to the inbox
  detail. No second support identity store is introduced.
- `main.py`: `PATCH /workspaces/{workspace_id}/members/{user_id}` changes one
  membership's role or lifecycle status. It validates role/status, protects
  the last active owner, and publishes a `member.updated` audit event.
- `events.py`, `schemas.py`: new event name and validated request schema.
- `dependencies.py` (existing behaviour, now asserted): every request resolves
  an active membership, so suspension revokes access immediately even for an
  existing bearer token.
- `apps/web/app.js`: Team access shows member status, suspend/reactivate
  controls and a role select; self and owner rows cannot be changed from the UI.
- `scripts/runtime_smoke.py`: section [9] verifies the contact-linked ticket
  journey and the last-owner guard over HTTP.

No database migration was needed: `WorkspaceMember.status` and
`Ticket.contact_id` already exist in the schema.

## Commands and results

From `D:\NOVARA\apps\api` (Python at `D:\NOVARA\.venv\Scripts\python.exe`):

```
python -m pytest tests/test_customer_profile_p0.py -q -rs
  6 passed, 1 warning in 2.68s

python -m pytest tests/test_ui_wiring.py tests/test_customer_profile_p0.py -q -rs
  14 passed, 1 warning in 2.69s

python -m pytest -q -rs
  219 passed, 1 warning in 73.73s
```

From `D:\NOVARA`:

```
node --check apps\web\app.js                 -> no syntax errors
python -m compileall -q apps\api\novara_core -> no errors
python scripts\runtime_smoke.py              -> RUNTIME SMOKE: PASS
```

The only warning is the known Starlette/httpx TestClient deprecation notice.
No response bodies, bearer tokens or credentials were printed.

## Behaviour proved

- A ticket cannot be linked to a missing contact (422) or a contact in another
  workspace.
- A contact profile lists only its own conversations; pre-chat identification
  reuses the same contact row and reports `created: false`.
- One user holds active memberships in two workspaces; support rows in each
  require the matching scoped token.
- Suspending a member returns 403 on tickets and contacts with their existing
  token; reactivating restores access.
- Invalid status (`snoozed`), owner self-assignment, empty updates, non-member
  patching and non-manager patching are rejected; the last active owner cannot
  be suspended or demoted.

## Matrix accounting

Only CW-014 and CW-129 were changed in `MASTER_FEATURE_MATRIX.csv`; all seven
FEATURE_PARITY deliverables were regenerated:

- 1,488 permanent IDs, zero omissions
- VERIFIED_COMPLETE 65 (was 63)
- complete-like 150 / 1,488 = 10.08% (was 148 / 9.95%)
- PARTIALLY_IMPLEMENTED 147 (was 149)
- P0: 111 rows — 58 verified, 12 partial, 32 replacement, 9 restricted

## Not claimed

- No Docker, signed installer, physical-device build or external send.
- No commit, push, tag, deployment or public publishing. Git HEAD is unchanged
  at `73e9f76`.

## Next

T-056: select the next grouped cluster from the 12 remaining P0 partial rows
(Formbricks 1, Plane 4, Mautic 6, Novu 1).
