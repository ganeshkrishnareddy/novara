# PL-088 guest project intake — named evidence (2026-11-23)

Clean-room NOVARA implementation. No email, external form host, public URL or
provider is contacted. Requests are real persisted rows and acceptance uses the
project module's own work-item creation path.

| Master ID | Named test | Proved locally |
|---|---|---|
| PL-088 | `test_project_intake_p1.py::test_pl088_guest_submission_and_acceptance_creates_real_work_item` | An admin issues a revocable link (token shown once, stored only as SHA-256); a guest submits without an account; the request is queued; acceptance creates a real project work item with the requester context; link/submit/accept events are audited; listing never returns the token. |
| PL-088 | `test_project_intake_p1.py::test_pl088_decline_snooze_revoke_and_tenant_isolation` | Decline and snooze are persisted with decided actor/time; re-deciding is rejected with 409; past snooze dates are rejected with 422; revocation and expiry both reject submissions with 401; a different workspace gets 403 on queue and decision endpoints. |

## Commands and results

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_project_intake_p1.py -q --disable-warnings
# 2 passed, 1 warning in 2.13s

.venv\Scripts\python.exe scripts/migration_roundtrip_check.py e2f4a6b8c0d3
# ROUND TRIP PASS: upgrade -> downgrade -> upgrade, existing data preserved
```

## Implementation surface

- `apps/api/novara_core/modules/project_intake.py` — `ProjectIntakeLink` and
  `ProjectIntakeRequest` tables, admin link/queue/decision endpoints under
  `/api/v1/workspaces/{workspace_id}/projects/{project_id}/intake`, and a public
  submit endpoint under `/api/v1/public/project-intake/{token}/requests`.
- `apps/api/migrations/versions/e2f4a6b8c0d3_project_intake_p1.py` — idempotent
  table creation on top of the API-key migration head.
- Link management requires `WORKSPACE_MANAGE`; queue reads require `TASK_READ`;
  decisions require `TASK_WRITE`. All admin routes verify workspace membership.

## Honest limitations

- This is a local guest-intake endpoint, not a hosted public form builder or a
  spam/CAPTCHA-protected internet-facing service. Deployments must put their own
  edge protection in front of the public route.
- No notification is sent to administrators on submission; the queue is the
  source of truth and can be polled through the API.
- The token is a high-entropy random secret hashed with SHA-256; it is not a
  password KDF, which is appropriate for a generated bearer-style token.
