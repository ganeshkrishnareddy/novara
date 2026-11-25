# Notification recipient mapping (NV-030)

NOVARA deliberately has **no subscriber subsystem and no second login**. The shared
identity tables are the only recipient source.

## Resolution rule

| Novu concept | NOVARA equivalent | Location |
| --- | --- | --- |
| Subscriber | `User` | `apps/api/novara_core/models.py::User` |
| Subscriber's organisation scope | `WorkspaceMember` | `apps/api/novara_core/models.py::WorkspaceMember` |
| Subscriber id used by the inbox | `Notification.user_id` -> `User.id` | `models.py::Notification` |
| Workspace-wide broadcast | `Notification.user_id IS NULL` | `main.py::_notification_scope` |
| Subscriber profile fields | `User.email`, `User.display_name`, `User.email_verified`, `User.last_login_at` | `models.py::User` |
| Subscriber preferences | `notification_preferences` (level/target/channel) and `workspace_notification_settings` | `modules/notification_preferences.py`, `models.py` |

A recipient is therefore `(workspace_id, user_id)` and nothing else. A user who is an
active member of two workspaces is one person with two independent recipient scopes;
the same access token never crosses them because `verify_workspace` checks membership
and every query filters on `workspace_id`.

## Authentication

Recipients sign in through `/api/v1/auth/login` with the same email and password as
every other NOVARA module. There is no subscriber API key, no subscriber token and no
subscriber-only endpoint. The login response binds the session to one workspace, and
`/api/v1/auth/me` returns that workspace with the user's role.

## Visibility

`_notification_scope(workspace_id, user_id)` returns a caller's own rows plus rows with
a null `user_id` (workspace broadcasts). It is reused by the feed, counts, real-time
stream and all seen/read actions, so those surfaces cannot drift apart. Every write
re-checks the scope and returns 404 for another identity's row and 403 for a workspace
the caller does not belong to.

## Tests

- `tests/test_notifications_advanced.py::test_one_identity_is_one_recipient_with_no_second_login`
  logs in as a second member through the normal auth endpoint and verifies that the
  member sees only their own row and workspace broadcasts, with no subscribers table.
- `tests/test_notifications_advanced.py::test_single_mark_read_is_user_and_workspace_scoped`
  verifies that cross-user and cross-workspace notification writes are denied.

This mapping is a clean-room design over NOVARA's existing identity model. No Novu
source code, schema dump or proprietary data was copied.
