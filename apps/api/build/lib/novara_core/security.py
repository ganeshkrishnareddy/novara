"""Password hashing, server-side sessions and one-time tokens.

Tokens are random, stored only as SHA-256 hashes, and revocable. No password or
raw token is ever written to the database or to logs.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

import bcrypt
from sqlalchemy import select

from .models import (
    EmailVerificationToken,
    PasswordResetToken,
    Session,
    in_hours,
    new_id,
    now,
)

PASSWORD_PREFIX = "bcrypt-sha256$"
ACCESS_HOURS = 1
REFRESH_HOURS = 24 * 14
RESET_HOURS = 1
VERIFY_HOURS = 24
INVITE_HOURS = 24 * 7


def _prehash(password: str) -> bytes:
    # bcrypt truncates at 72 bytes; pre-hashing avoids silent truncation.
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")


def hash_password(password: str) -> str:
    return PASSWORD_PREFIX + bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, stored: str) -> bool:
    if not stored.startswith(PASSWORD_PREFIX):
        return False
    try:
        expected = stored[len(PASSWORD_PREFIX) :].encode("ascii")
        return bcrypt.checkpw(_prehash(password), expected)
    except (ValueError, TypeError):
        return False


def new_raw_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _expired(value: datetime) -> bool:
    return _naive(value) <= _naive(now())


def create_session(db, *, user_id: str, workspace_id: str) -> tuple[Session, str, str]:
    access = new_raw_token()
    refresh = new_raw_token()
    session = Session(
        id=new_id(),
        user_id=user_id,
        workspace_id=workspace_id,
        access_token_hash=hash_token(access),
        refresh_token_hash=hash_token(refresh),
        access_expires_at=in_hours(ACCESS_HOURS),
        refresh_expires_at=in_hours(REFRESH_HOURS),
        revoked_at=None,
        created_at=now(),
    )
    db.add(session)
    db.flush()
    return session, access, refresh


def session_by_access(db, raw_token: str | None) -> Session | None:
    if not raw_token:
        return None
    session = db.execute(
        select(Session).where(Session.access_token_hash == hash_token(raw_token))
    ).scalar_one_or_none()
    if session is None or session.revoked_at is not None or _expired(session.access_expires_at):
        return None
    return session


def rotate_session(db, raw_refresh: str) -> tuple[Session, str, str] | None:
    session = db.execute(
        select(Session).where(Session.refresh_token_hash == hash_token(raw_refresh))
    ).scalar_one_or_none()
    if session is None or session.revoked_at is not None or _expired(session.refresh_expires_at):
        return None
    access = new_raw_token()
    refresh = new_raw_token()
    session.access_token_hash = hash_token(access)
    session.refresh_token_hash = hash_token(refresh)
    session.access_expires_at = in_hours(ACCESS_HOURS)
    session.refresh_expires_at = in_hours(REFRESH_HOURS)
    db.flush()
    return session, access, refresh


def revoke_session(db, raw_access: str | None) -> bool:
    session = session_by_access(db, raw_access)
    if session is None:
        return False
    session.revoked_at = now()
    db.flush()
    return True


def issue_one_time_token(db, kind: str, user_id: str) -> str:
    raw = new_raw_token()
    record = PasswordResetToken if kind == "reset" else EmailVerificationToken
    expires = RESET_HOURS if kind == "reset" else VERIFY_HOURS
    db.add(
        record(
            id=new_id(),
            user_id=user_id,
            token_hash=hash_token(raw),
            expires_at=in_hours(expires),
            used_at=None,
            created_at=now(),
        )
    )
    db.flush()
    return raw


def consume_one_time_token(db, kind: str, raw: str) -> object | None:
    record = PasswordResetToken if kind == "reset" else EmailVerificationToken
    item = db.execute(select(record).where(record.token_hash == hash_token(raw))).scalar_one_or_none()
    if item is None or item.used_at is not None or _expired(item.expires_at):
        return None
    item.used_at = now()
    db.flush()
    return item
