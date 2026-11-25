# Plane platform P1 — named acceptance evidence (2026-11-23)

All tests run against the real FastAPI app with an isolated SQLite database via
`apps/api/tests/conftest.py`. No external service, credential or mock success
response is used. Command:

```
D:\NOVARA\.venv\Scripts\python.exe -m pytest apps/api/tests/test_plane_platform_p1.py -q --disable-warnings
# 8 passed, 1 warning in 5.79s
```

| Master ID | Named test | What is proved |
|---|---|---|
| PL-041 | `test_pl041_admin_can_change_workspace_settings_and_every_change_is_audited` | Authorised admin edits workspace settings via the real PATCH route; values persist; exactly one `workspace.settings_updated` event carries the verified actor and changed field names; secret-looking keys are rejected; a foreign workspace id is denied. |
| PL-044 | `test_pl044_api_prefix_is_versioned_documented_and_permission_checked` | The generated OpenAPI inventory is versioned under `/api/v1/`; unauthenticated and forged-token reads get 401; a real token gets 200; the concrete permission-checked route is documented as `/api/v1/workspaces/{workspace_id}/admin/settings`. |
| PL-049 | `test_pl049_rate_limit_headers_and_429_through_real_app` | Three auth attempts yield 401, 401, 429 with `X-RateLimit-*`, `Retry-After` and hardening headers on the real app. |
| PL-055 | `test_pl055_password_lifecycle_rejects_replayed_reset_tokens` | A reset token changes the password, revokes the old session and cannot be replayed; login with the new password succeeds. |
| PL-057 | `test_pl057_bearer_sessions_replace_csrf_tokens_without_a_cookie_surface` | Auth responses set no cookie, untrusted cross-origin credentialed requests are refused, unauthenticated writes get 401, a rotated access token is rejected and the current bearer token succeeds. The recorded criterion's CSRF-token mechanism is replaced by bearer sessions; the row is dispositioned as a compatible replacement, not a literal CSRF implementation. |
| PL-033, PL-077 | `test_pl033_and_pl077_intake_creates_one_real_notification_and_event` | One website-form intake creates exactly one in-app notification with its `workspace_id`, one `notification.created` event linked to that notification id, and the SPA serves a real `/notifications` route. |
| PL-105 | `test_pl105_invite_acceptance_creates_membership_and_audited_event` | Invite acceptance by a registered second user creates workspace membership with the invited role, emits exactly one `member.joined` event, and replaying the invite is rejected. |

Security note: PL-057's original criterion names a CSRF token. NOVARA has no
ambient-cookie session, so CSRF has no attack surface here; the test proves the
documented bearer-token equivalent rather than adding a token that protects
nothing.
