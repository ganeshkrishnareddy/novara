# GrowthBook-compatible clean-room API P1 evidence (2026-11-23)

NOVARA exposes its own versioned, workspace-scoped REST API and local
email/password account lifecycle. No GrowthBook source, MongoDB server or
external call is involved.

```
D:\NOVARA\.venv\Scripts\python.exe -m pytest apps/api/tests/test_growthbook_api_p1.py -q --disable-warnings
# 4 passed, 1 warning in 5.23s
```

| Master ID | Named test | Proved locally |
|---|---|---|
| GB-059 | `test_gb059_versioned_rest_api_is_validated_permission_checked_and_wired` | The public OpenAPI inventory is versioned under `/api/v1/`; a real route requires a valid bearer token, rejects secret-like settings (422), persists valid settings, and the SPA calls the same versioned API. |
| GB-063 | `test_gb063_organisations_are_workspaces_with_members_and_isolation` | Workspaces (the organisation equivalent) are listed, created and switched with a fresh session; a foreign workspace's admin/member routes are denied; the SPA has a real workspaces page. |
| GB-064 | `test_gb064_local_email_and_password_accounts_validate_and_scope_sessions` | Local accounts validate email/password, reject bad credentials, scope sessions to a workspace, revoke other sessions on password change and reject the old password; the SPA has a change-password form. |
| GB-117 | `test_gb117_configured_flag_provider_does_not_claim_delivery` | A GrowthBook integration can be configured locally, secret-like config is rejected, the capability report marks it configured, and the adapter view makes no delivery claim. |

GB-060 (a separate REST v2 surface) and GB-087 (MongoDB primary store) are not
claimed: NOVARA has one versioned API and a local SQL store by design, with no
MongoDB dependency.
