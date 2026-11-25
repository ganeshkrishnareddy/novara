"""Adversarial and failure-recovery tests for the NOVARA core API.

These tests probe untrusted input, cross-tenant access, token lifecycle and
audit-log integrity. They deliberately target only the stable core API: no
optional capability module is imported or assumed to be wired.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from novara_core.main import app
from novara_core.models import User, Workspace, WorkspaceMember, new_id
from novara_core.security import hash_password, verify_password

from .conftest import auth, bootstrap


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _intake(client, wid, headers, *, submission_id, email, full_name="Adversarial"):
    response = client.post(
        f"/api/v1/workspaces/{wid}/intake/website-form",
        headers=headers,
        json={
            "submission_id": submission_id,
            "email": email,
            "full_name": full_name,
            "message": "Please follow up",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _register_reader(client, wid, owner_headers, email="reader@example.com", role="read_only"):
    """Invite, register and accept as a non-owner member of ``wid``."""
    invited = client.post(
        f"/api/v1/workspaces/{wid}/invitations",
        headers=owner_headers,
        json={"email": email, "role": role},
    )
    assert invited.status_code == 200, invited.text
    raw = invited.json()["invite_token"]

    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Reader"},
    )
    assert registered.status_code == 200, registered.text

    joined = client.post(
        "/api/v1/invitations/accept",
        headers=auth(registered.json()["access_token"]),
        json={"token": raw},
    )
    assert joined.status_code == 200, joined.text
    return joined.json()


# --------------------------------------------------------------------------
# 1. Authentication failures
# --------------------------------------------------------------------------


def test_protected_routes_reject_missing_malformed_and_random_credentials(client):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    protected = [
        f"/api/v1/workspaces/{wid}/contacts",
        f"/api/v1/workspaces/{wid}/events",
        f"/api/v1/workspaces/{wid}/members",
        "/api/v1/auth/me",
    ]
    bad_headers = [
        None,
        {},
        {"Authorization": "Basic x"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
        {"Authorization": "bearer not-a-session"},
        {"Authorization": "Bearer random.token.value"},
        {"Authorization": "Bearer a b c"},  # malformed: too many parts
        {"Authorization": "Token abc"},
    ]
    for path in protected:
        for headers in bad_headers:
            response = client.get(path, headers=headers)
            assert response.status_code == 401, (path, headers, response.text)
            assert response.json()["detail"] == "invalid or expired access token"


def test_revoked_and_expired_style_tokens_are_not_accepted(client, db_session):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    headers = auth(tokens["access_token"])
    assert client.post("/api/v1/auth/logout", headers=headers).json()["revoked"] is True
    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=headers).status_code == 401


# --------------------------------------------------------------------------
# 2. Password hashing and minimum length
# --------------------------------------------------------------------------


def test_password_hashing_is_salted_and_verifiable(client, db_session):
    bootstrap(client)
    user = db_session.execute(
        select(User).where(User.email == "owner@example.com")
    ).scalar_one()

    stored = user.password_hash
    assert stored != "Password123!"
    assert "Password123!" not in stored
    assert stored.startswith("bcrypt-sha256$")
    assert verify_password("Password123!", stored) is True
    assert verify_password("WrongPassword!", stored) is False

    # The same password hashed twice yields different stored values (salting).
    assert hash_password("Password123!") != hash_password("Password123!")


def test_passwords_shorter_than_eight_characters_are_rejected(client):
    for weak in ("", "short", "1234567"):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "password": weak, "display_name": "Weak"},
        )
        assert response.status_code == 422, (weak, response.text)

    accepted = client.post(
        "/api/v1/auth/register",
        json={"email": "strong@example.com", "password": "12345678", "display_name": "Strong"},
    )
    assert accepted.status_code == 200, accepted.text


# --------------------------------------------------------------------------
# 3. Duplicate registration and bad credentials
# --------------------------------------------------------------------------


def test_duplicate_email_registration_conflicts_and_login_fails_closed(client):
    bootstrap(client)  # owner@example.com

    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": "OWNER@EXAMPLE.COM",  # normalisation must still collide
            "password": "Password123!",
            "display_name": "Impostor",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "email is already registered"

    first = client.post(
        "/api/v1/auth/register",
        json={"email": "second@example.com", "password": "Password123!", "display_name": "Second"},
    )
    assert first.status_code == 200, first.text
    again = client.post(
        "/api/v1/auth/register",
        json={"email": "second@example.com", "password": "Password123!", "display_name": "Second"},
    )
    assert again.status_code == 409

    wrong = client.post(
        "/api/v1/auth/login", json={"email": "second@example.com", "password": "definitely-wrong"}
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "invalid email or password"

    unknown = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "Password123!"}
    )
    assert unknown.status_code == 401
    assert unknown.json() == wrong.json()  # no account enumeration via login

    good = client.post(
        "/api/v1/auth/login", json={"email": "second@example.com", "password": "Password123!"}
    )
    assert good.status_code == 200, good.text


# --------------------------------------------------------------------------
# 4. Cross-workspace isolation
# --------------------------------------------------------------------------


def test_cross_workspace_access_is_denied_for_every_scoped_resource(client):
    owner = bootstrap(client)
    first_wid = owner["workspace_id"]
    first_headers = auth(owner["access_token"])

    created = client.post(
        "/api/v1/workspaces", headers=first_headers, json={"name": "Second workspace"}
    )
    assert created.status_code == 200, created.text
    second = created.json()
    second_wid = second["workspace_id"]
    second_headers = auth(second["access_token"])
    assert second_wid != first_wid
    assert second["workspace_id"] == second_wid

    mine = client.get("/api/v1/workspaces", headers=first_headers).json()
    assert {row["id"] for row in mine} == {first_wid, second_wid}
    assert all(row["role"] == "owner" for row in mine)

    suffixes = ["contacts", "leads", "tasks", "events", "members", "outreach-drafts"]
    # Both directions: a session bound to workspace A must not read workspace B.
    for target_wid, wrong_headers in ((second_wid, first_headers), (first_wid, second_headers)):
        for suffix in suffixes:
            response = client.get(
                f"/api/v1/workspaces/{target_wid}/{suffix}", headers=wrong_headers
            )
            assert response.status_code == 403, (target_wid, suffix, response.text)
            assert "cross-workspace" in response.json()["detail"]


def test_cross_workspace_write_is_denied(client):
    owner = bootstrap(client)
    first_headers = auth(owner["access_token"])
    created = client.post(
        "/api/v1/workspaces", headers=first_headers, json={"name": "Other"}
    )
    assert created.status_code == 200, created.text
    other_wid = created.json()["workspace_id"]

    blocked = client.post(
        f"/api/v1/workspaces/{other_wid}/contacts",
        headers=first_headers,
        json={"email": "cross@example.com"},
    )
    assert blocked.status_code == 403
    assert "cross-workspace" in blocked.json()["detail"]

    blocked_intake = client.post(
        f"/api/v1/workspaces/{other_wid}/intake/website-form",
        headers=first_headers,
        json={"email": "cross@example.com"},
    )
    assert blocked_intake.status_code == 403


# --------------------------------------------------------------------------
# 5. Refresh rotation and logout revocation
# --------------------------------------------------------------------------


def test_refresh_rotation_invalidates_old_access_and_refresh_tokens(client):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    old_headers = auth(tokens["access_token"])

    rotated = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert rotated.status_code == 200, rotated.text
    new = rotated.json()
    assert new["access_token"] != tokens["access_token"]
    assert new["refresh_token"] != tokens["refresh_token"]
    assert new["workspace_id"] == wid

    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=old_headers).status_code == 401
    new_headers = auth(new["access_token"])
    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=new_headers).status_code == 200

    reused = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reused.status_code == 401
    assert reused.json()["detail"] == "invalid or expired refresh token"

    # A rotation chain works, but each refresh token is single-use.
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]})
    assert again.status_code == 200, again.text
    newer = again.json()
    assert newer["access_token"] != new["access_token"]
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}
    ).status_code == 401


def test_logout_revokes_both_access_and_refresh_tokens(client):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    rotated = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert rotated.status_code == 200, rotated.text
    current = rotated.json()
    current_headers = auth(current["access_token"])

    logged_out = client.post("/api/v1/auth/logout", headers=current_headers)
    assert logged_out.status_code == 200
    assert logged_out.json()["revoked"] is True

    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=current_headers).status_code == 401
    after = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": current["refresh_token"]}
    )
    assert after.status_code == 401
    assert after.json()["detail"] == "invalid or expired refresh token"


# --------------------------------------------------------------------------
# 6. Password reset
# --------------------------------------------------------------------------


def test_password_reset_is_non_enumerating_and_single_use(client, monkeypatch):
    tokens = bootstrap(client)
    wid = tokens["workspace_id"]
    old_headers = auth(tokens["access_token"])

    unknown = client.post(
        "/api/v1/auth/password-reset/request", json={"email": "ghost@example.com"}
    )
    known = client.post(
        "/api/v1/auth/password-reset/request", json={"email": "owner@example.com"}
    )
    assert unknown.status_code == 200 and known.status_code == 200
    assert unknown.json() == known.json()  # identical body: no account existence leak
    assert "development_token" not in known.json()

    bad = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": "FreshPass123!"},
    )
    assert bad.status_code == 400
    assert bad.json()["detail"] == "invalid or expired reset token"

    # Enable dev mode only for this test. The endpoint reads os.getenv at call
    # time, so no module reload is needed (and app state stays intact).
    monkeypatch.setenv("NOVARA_DEV_MODE", "true")
    issued = client.post(
        "/api/v1/auth/password-reset/request", json={"email": "owner@example.com"}
    )
    assert issued.status_code == 200, issued.text
    raw = issued.json().get("development_token")
    assert isinstance(raw, str) and raw

    confirmed = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw, "new_password": "FreshPass123!"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json() == {"reset": True, "sessions_revoked": True}

    # Every pre-existing session (access + refresh) is dead after a reset.
    assert client.get(f"/api/v1/workspaces/{wid}/contacts", headers=old_headers).status_code == 401
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).status_code == 401

    # The reset token itself is one-time use.
    reuse = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw, "new_password": "AnotherPass123!"},
    )
    assert reuse.status_code == 400

    # Password actually changed; old password no longer authenticates.
    assert client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "Password123!"}
    ).status_code == 401
    relogin = client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "FreshPass123!"}
    )
    assert relogin.status_code == 200, relogin.text


def test_weak_new_password_is_rejected_on_reset_confirm(client, monkeypatch):
    bootstrap(client)
    monkeypatch.setenv("NOVARA_DEV_MODE", "true")
    issued = client.post(
        "/api/v1/auth/password-reset/request", json={"email": "owner@example.com"}
    )
    raw = issued.json()["development_token"]
    weak = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw, "new_password": "short"},
    )
    assert weak.status_code == 422


# --------------------------------------------------------------------------
# 7. Permission escalation
# --------------------------------------------------------------------------


def test_read_only_member_cannot_write_approve_invite_or_create_workspace(client):
    tokens = bootstrap(client)
    wid, owner_headers = tokens["workspace_id"], auth(tokens["access_token"])
    reader = _register_reader(client, wid, owner_headers)
    reader_headers = auth(reader["access_token"])

    me = client.get("/api/v1/auth/me", headers=reader_headers).json()
    assert me["role"] == "read_only"
    assert me["workspace_id"] == wid
    for denied_permission in (
        "contact:write",
        "outreach:approve",
        "member:invite",
        "workspace:manage",
    ):
        assert denied_permission not in me["permissions"]

    # Reads are allowed.
    for suffix in ("contacts", "leads", "tasks", "events", "outreach-drafts"):
        response = client.get(f"/api/v1/workspaces/{wid}/{suffix}", headers=reader_headers)
        assert response.status_code == 200, (suffix, response.text)

    # Writes and authority-granting actions are refused.
    create_contact = client.post(
        f"/api/v1/workspaces/{wid}/contacts",
        headers=reader_headers,
        json={"email": "escalate@example.com"},
    )
    assert create_contact.status_code == 403
    assert create_contact.json()["detail"] == "permission required: contact:write"

    invite = client.post(
        f"/api/v1/workspaces/{wid}/invitations",
        headers=reader_headers,
        json={"email": "friend@example.com", "role": "admin"},
    )
    assert invite.status_code == 403
    assert invite.json()["detail"] == "permission required: member:invite"

    new_workspace = client.post(
        "/api/v1/workspaces", headers=reader_headers, json={"name": "Escalated"}
    )
    assert new_workspace.status_code == 403
    assert new_workspace.json()["detail"] == "permission required: workspace:manage"

    intake = _intake(client, wid, owner_headers, submission_id="ro-1", email="ro@example.com")
    approve = client.post(
        f"/api/v1/workspaces/{wid}/outreach-drafts/{intake['draft_id']}/approve",
        headers=reader_headers,
    )
    assert approve.status_code == 403
    assert approve.json()["detail"] == "permission required: outreach:approve"


# --------------------------------------------------------------------------
# 8. IDOR / guessed identifiers
# --------------------------------------------------------------------------


def test_guessed_cross_tenant_ids_never_return_data(client):
    owner = bootstrap(client)
    victim_wid = owner["workspace_id"]
    victim_headers = auth(owner["access_token"])
    victim = _intake(
        client, victim_wid, victim_headers,
        submission_id="idor-1", email="secret-victim@example.com",
    )
    note = client.post(
        f"/api/v1/workspaces/{victim_wid}/contacts/{victim['contact_id']}/notes",
        headers=victim_headers,
        json={"contact_id": victim["contact_id"], "body": "highly secret note"},
    )
    assert note.status_code == 201, note.text

    attacker = client.post(
        "/api/v1/auth/register",
        json={"email": "attacker@example.com", "password": "Password123!", "display_name": "Attacker"},
    )
    assert attacker.status_code == 200, attacker.text
    attacker_tokens = attacker.json()
    attacker_wid, attacker_headers = attacker_tokens["workspace_id"], auth(attacker_tokens["access_token"])

    attempts = [
        ("get", f"/api/v1/workspaces/{attacker_wid}/contacts/{victim['contact_id']}", None),
        ("patch", f"/api/v1/workspaces/{attacker_wid}/leads/{victim['lead_id']}", {"status": "qualified"}),
        ("patch", f"/api/v1/workspaces/{attacker_wid}/tasks/{victim['task_id']}", {"status": "done"}),
        ("post", f"/api/v1/workspaces/{attacker_wid}/outreach-drafts/{victim['draft_id']}/approve", None),
    ]
    for method, path, payload in attempts:
        kwargs = {"headers": attacker_headers}
        if payload is not None:
            kwargs["json"] = payload
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code in (403, 404), (method, path, response.status_code, response.text)
        assert "secret-victim@example.com" not in response.text
        assert "highly secret note" not in response.text

    # Listing/searching inside the attacker's own workspace also reveals nothing.
    assert client.get(f"/api/v1/workspaces/{attacker_wid}/contacts", headers=attacker_headers).json() == []
    searched = client.get(
        f"/api/v1/workspaces/{attacker_wid}/contacts",
        headers=attacker_headers,
        params={"search": "secret-victim@example.com"},
    ).json()
    assert searched == []


# --------------------------------------------------------------------------
# 9. Input validation
# --------------------------------------------------------------------------


def test_extra_fields_are_rejected_on_write_schemas(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    cases = [
        (
            "/api/v1/auth/register",
            {"email": "extra1@example.com", "password": "Password123!", "display_name": "E", "is_admin": True},
        ),
        ("/api/v1/workspaces", {"name": "ExtraWorkspace", "role": "owner"}),
        (f"/api/v1/workspaces/{wid}/contacts", {"email": "extra2@example.com", "surprise": "field"}),
        (
            f"/api/v1/workspaces/{wid}/invitations",
            {"email": "extra3@example.com", "role": "read_only", "is_owner": True},
        ),
    ]
    for path, payload in cases:
        response = client.post(path, headers=headers, json=payload)
        assert response.status_code == 422, (path, response.text)


def test_invalid_emails_empty_workspace_names_and_bad_roles_are_rejected(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    for bad_email in ("not-an-email", "a@@b.com", "@example.com", "x@", "plain"):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": bad_email, "password": "Password123!", "display_name": "E"},
        )
        assert response.status_code == 422, (bad_email, response.text)

    for empty_name in ("", "   ", "\t\n"):
        response = client.post("/api/v1/workspaces", headers=headers, json={"name": empty_name})
        assert response.status_code == 422, (empty_name, response.text)

    for bad_role in ("owner", "superuser", "admin2", ""):
        response = client.post(
            f"/api/v1/workspaces/{wid}/invitations",
            headers=headers,
            json={"email": "invite@example.com", "role": bad_role},
        )
        assert response.status_code == 422, (bad_role, response.text)


def test_security_fix_regressions(client):
    """Regression cover for the four fixes raised by code review."""
    # 1. First-run bootstrap rejects a blank workspace name.
    blank = client.post(
        "/api/v1/setup/bootstrap",
        json={
            "workspace_name": "   ",
            "email": "bootstrap@example.com",
            "password": "Password123!",
            "display_name": "Owner",
        },
    )
    assert blank.status_code == 422, blank.text

    # 2. Embedded whitespace in an email is rejected at every entry point.
    for path, payload in (
        (
            "/api/v1/auth/register",
            {"email": "a b@example.com", "password": "Password123!", "display_name": "X"},
        ),
        (
            "/api/v1/setup/bootstrap",
            {
                "workspace_name": "Acme",
                "email": "a b@example.com",
                "password": "Password123!",
                "display_name": "X",
            },
        ),
    ):
        bad = client.post(path, json=payload)
        assert bad.status_code == 422, (path, bad.text)

    tokens = bootstrap(client, email="owner2@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    # 3. A body-supplied owner_id must be an active member of this workspace.
    fake_owner = "00000000-0000-0000-0000-000000000000"
    contact = client.post(
        f"/api/v1/workspaces/{wid}/contacts",
        headers=headers,
        json={"email": "leadowner@example.com"},
    ).json()
    cases = (
        (f"/api/v1/workspaces/{wid}/companies", {"name": "Acme", "owner_id": fake_owner}),
        (f"/api/v1/workspaces/{wid}/tasks", {"title": "Follow up", "owner_id": fake_owner}),
        (
            f"/api/v1/workspaces/{wid}/leads",
            {"contact_id": contact["id"], "owner_id": fake_owner},
        ),
    )
    for path, payload in cases:
        bad = client.post(path, headers=headers, json=payload)
        assert bad.status_code == 422, (path, bad.text)
        assert "active member" in bad.json()["detail"]

    # 4. The shared workspace guard denies a different workspace's token.
    other = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Other"}
    )
    assert other.status_code == 200, other.text
    guarded = client.get(
        f"/api/v1/workspaces/{wid}/companies",
        headers=auth(other.json()["access_token"]),
    )
    assert guarded.status_code == 403
    assert "cross-workspace" in guarded.json()["detail"]


def test_email_normalization_and_legitimate_addresses(client):
    """Emails are stored lowercase, login is case-insensitive, valid forms survive."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "MiXeD.Case+tag@Sub.Example.COM",
            "password": "Password123!",
            "display_name": "Case Test",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() is not None

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "mixed.case+TAG@sub.example.com", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text

    for good in (
        "first.last@example.com",
        "user+alias@sub.example.co.uk",
        "user-name@example-domain.com",
        "o'connor@example.com",
    ):
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": good, "password": "Password123!", "display_name": "Valid"},
        )
        assert registered.status_code == 200, (good, registered.text)


def test_owner_assignment_requires_active_same_workspace_member(client, db_session):
    """Foreign, inactive and nonexistent owners are rejected on every owner-bearing write."""
    tokens = bootstrap(client, email="owner3@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner = db_session.execute(
        select(User).where(User.email == "owner3@example.com")
    ).scalar_one()
    contact = client.post(
        f"/api/v1/workspaces/{wid}/contacts",
        headers=headers,
        json={"email": "owner-target@example.com"},
    ).json()

    foreign_ws = Workspace(id=new_id(), name="Foreign")
    foreign_user = User(
        id=new_id(),
        email="foreign@example.com",
        display_name="Foreign",
        password_hash=hash_password("Password123!"),
    )
    db_session.add_all([foreign_ws, foreign_user])
    db_session.flush()
    db_session.add(
        WorkspaceMember(
            id=new_id(),
            workspace_id=foreign_ws.id,
            user_id=foreign_user.id,
            role="owner",
            status="active",
        )
    )
    inactive = User(
        id=new_id(),
        email="inactive@example.com",
        display_name="Inactive",
        password_hash=hash_password("Password123!"),
    )
    db_session.add(inactive)
    db_session.flush()
    db_session.add(
        WorkspaceMember(
            id=new_id(),
            workspace_id=wid,
            user_id=inactive.id,
            role="sales_rep",
            status="suspended",
        )
    )
    db_session.commit()

    bad_owners = (foreign_user.id, inactive.id, "00000000-0000-0000-0000-000000000000")
    cases = (
        (
            f"/api/v1/workspaces/{wid}/companies",
            {"name": "Acme"},
            "post",
        ),
        (
            f"/api/v1/workspaces/{wid}/tasks",
            {"title": "Follow up"},
            "post",
        ),
        (
            f"/api/v1/workspaces/{wid}/leads",
            {"contact_id": contact["id"]},
            "post",
        ),
        (
            f"/api/v1/workspaces/{wid}/contacts/{contact['id']}",
            {},
            "patch",
        ),
    )
    for bad_owner in bad_owners:
        for path, payload, method in cases:
            response = getattr(client, method)(
                path, headers=headers, json={**payload, "owner_id": bad_owner}
            )
            assert response.status_code in (400, 403, 422), (path, bad_owner, response.text)
            assert "active member" in response.json()["detail"]

    # A valid active member of this workspace still works.
    good = client.post(
        f"/api/v1/workspaces/{wid}/tasks",
        headers=headers,
        json={"title": "Owned task", "owner_id": owner.id},
    )
    assert good.status_code == 201, good.text
    assert good.json()["owner_id"] == owner.id


# --------------------------------------------------------------------------
# 10. Event integrity
# --------------------------------------------------------------------------


def test_events_are_append_only_idempotent_and_correlated(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    first = client.post(
        f"/api/v1/workspaces/{wid}/intake/website-form",
        headers=headers,
        json={"submission_id": "idem-42", "email": "idem@example.com", "full_name": "Idem"},
    )
    assert first.status_code == 201, first.text
    replay = client.post(
        f"/api/v1/workspaces/{wid}/intake/website-form",
        headers=headers,
        json={"submission_id": "idem-42", "email": "idem@example.com", "full_name": "Idem"},
    )
    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()  # deduplicated result, identical ids

    events = client.get(f"/api/v1/workspaces/{wid}/events", headers=headers).json()
    assert len(events) == 5, events  # replay produced no extra events
    assert len({event["id"] for event in events}) == 5
    correlation_id = first.json()["correlation_id"]
    assert {event["correlation_id"] for event in events} == {correlation_id}

    contacts = client.get(f"/api/v1/workspaces/{wid}/contacts", headers=headers).json()
    assert len(contacts) == 1
    tasks = client.get(f"/api/v1/workspaces/{wid}/tasks", headers=headers).json()
    assert len(tasks) == 1

    # A different submission is a different workflow with its own correlation id.
    second = client.post(
        f"/api/v1/workspaces/{wid}/intake/website-form",
        headers=headers,
        json={"submission_id": "idem-43", "email": "other@example.com"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["correlation_id"] != correlation_id
    events = client.get(f"/api/v1/workspaces/{wid}/events", headers=headers).json()
    assert len(events) == 10, events
    assert {event["correlation_id"] for event in events} == {
        correlation_id, second.json()["correlation_id"]
    }

    # Append-only: no route can mutate or delete an audit event.
    mutating_event_routes = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = set(getattr(route, "methods", None) or [])
        if "events" in path and methods & {"PATCH", "PUT", "DELETE"}:
            mutating_event_routes.append((path, sorted(methods)))
    assert mutating_event_routes == []

    patch_response = client.patch(
        f"/api/v1/workspaces/{wid}/events", headers=headers, json={}
    )
    assert patch_response.status_code in (404, 405), patch_response.status_code
    delete_response = client.delete(f"/api/v1/workspaces/{wid}/events", headers=headers)
    assert delete_response.status_code in (404, 405), delete_response.status_code


# --------------------------------------------------------------------------
# 11. Delete safeguards
# --------------------------------------------------------------------------


def test_contact_delete_requires_archive_and_no_dependents(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    created = client.post(
        f"/api/v1/workspaces/{wid}/contacts",
        headers=headers,
        json={"email": "delete-me@example.com", "full_name": "Delete Me"},
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    not_archived = client.delete(f"/api/v1/workspaces/{wid}/contacts/{cid}", headers=headers)
    assert not_archived.status_code == 409
    assert "archive" in not_archived.json()["detail"]

    note = client.post(
        f"/api/v1/workspaces/{wid}/contacts/{cid}/notes",
        headers=headers,
        json={"contact_id": cid, "body": "blocks deletion"},
    )
    assert note.status_code == 201, note.text

    archived = client.post(f"/api/v1/workspaces/{wid}/contacts/{cid}/archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["archived"] is True

    with_dependents = client.delete(f"/api/v1/workspaces/{wid}/contacts/{cid}", headers=headers)
    assert with_dependents.status_code == 409
    detail = with_dependents.json()["detail"]
    assert "dependent_records" in detail
    assert detail["dependent_records"].get("notes") == 1

    # An archived contact with no dependent rows can be hard-deleted and is audited.
    clean = client.post(
        f"/api/v1/workspaces/{wid}/contacts", headers=headers, json={"email": "clean@example.com"}
    )
    assert clean.status_code == 201, clean.text
    clean_id = clean.json()["id"]
    assert client.post(
        f"/api/v1/workspaces/{wid}/contacts/{clean_id}/archive", headers=headers
    ).status_code == 200
    deleted = client.delete(f"/api/v1/workspaces/{wid}/contacts/{clean_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted": True, "contact_id": clean_id}
    assert client.get(f"/api/v1/workspaces/{wid}/contacts/{clean_id}", headers=headers).status_code == 404

    event_types = [
        event["event_type"]
        for event in client.get(f"/api/v1/workspaces/{wid}/events", headers=headers).json()
    ]
    assert "contact.deleted" in event_types


# --------------------------------------------------------------------------
# 12. No outbound send surface
# --------------------------------------------------------------------------


def test_no_route_can_send_or_publish_external_messages(client):
    paths = " ".join(getattr(route, "path", "") for route in app.routes).lower()
    assert "send" not in paths
    assert "publish" not in paths
    assert "email/send" not in paths

    # Approval is the terminal action: it records an event but never sends.
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    intake = _intake(client, wid, headers, submission_id="send-1", email="draft@example.com")
    approved = client.post(
        f"/api/v1/workspaces/{wid}/outreach-drafts/{intake['draft_id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert "sent" not in approved.json()["status"]
    drafts = client.get(f"/api/v1/workspaces/{wid}/outreach-drafts", headers=headers).json()
    assert [draft["status"] for draft in drafts] == ["approved"]
