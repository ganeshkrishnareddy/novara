"""Document security for the Papermark P1 cluster (PM-040, PM-045, PM-117, PM-156).

Crypto construction (clean-room, Python standard library only)
--------------------------------------------------------------
* Versioned 32-byte keys are read from ``NOVARA_DOCUMENT_ENCRYPTION_KEYS`` as
  comma-separated ``id:base64key`` entries, with one entry marked ``:active``.
  Example: ``k1:<b64>,k2:<b64>:active``. With a single entry the active marker
  is optional. If the variable is unset, a deterministic local development key
  (``dev1``) is used so the app runs without secrets; deployments must set it.
* Each record gets a fresh 16-byte nonce. A keystream is built from
  ``HMAC-SHA256(enc_key, nonce || 8-byte big-endian counter)`` blocks and XORed
  with the plaintext (CTR mode). ``enc_key = HMAC-SHA256(key, "novara-enc-v1")``.
* The token is ``v1.<key_id>.<b64url(nonce)>.<b64url(ciphertext)>.<b64url(tag)>``.
  The tag is an encrypt-then-MAC ``HMAC-SHA256(mac_key, "v1" || nonce || ciphertext)``
  with ``mac_key = HMAC-SHA256(key, "novara-mac-v1")``. It is checked with
  ``hmac.compare_digest`` before any decryption is attempted.
* Rotation re-encrypts stored records under the currently active key; older key
  ids must remain in the environment until no row references them.

This is application-level at-rest protection for database records. It is NOT
full-disk encryption, NOT a KMS/HSM, and NOT a substitute for TLS in transit.
Transport hardening is the deployment's TLS termination plus the app's response
security headers in ``middleware.py``. Key material, stored ciphertext and
stored secret values are never logged or returned by metadata endpoints; the
 authorised download endpoint intentionally returns decrypted file bytes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import os
import re
import secrets
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import DOCUMENT_ADMIN, DOCUMENT_READ, DOCUMENT_WRITE
from .documents import DOCUMENT_DOWNLOADED, DOCUMENT_VIEWED, Document
from .email_campaigns import WebhookDelivery, WebhookSubscription, deliver_webhook, webhook_signature

KEY_ENV = "NOVARA_DOCUMENT_ENCRYPTION_KEYS"
DEV_KEY_ID = "dev1"
MAX_BLOB_BYTES = int(os.getenv("NOVARA_MAX_DOCUMENT_BLOB_BYTES", str(25 * 1024 * 1024)))

# Audit events on the shared, append-only bus. DOCUMENT_SHARED is also a valid
# signed webhook event name; email_campaigns.WEBHOOK_EVENT_TYPES allows it.
DOCUMENT_SECRET_STORED = "document.secret_stored"
DOCUMENT_SECRET_ROTATED = "document.secret_rotated"
DOCUMENT_ENCRYPTED_FILE_STORED = "document.encrypted_file_stored"
DOCUMENT_SHARED = "document.shared"
WATERMARK_VIEW_CREATED = "document.watermark_view_created"
DOCUMENT_WEBHOOK_SUBSCRIPTION_CREATED = "document.webhook_subscription_created"
register_event_types(
    DOCUMENT_SECRET_STORED,
    DOCUMENT_SECRET_ROTATED,
    DOCUMENT_ENCRYPTED_FILE_STORED,
    DOCUMENT_SHARED,
    DOCUMENT_VIEWED,
    DOCUMENT_DOWNLOADED,
    WATERMARK_VIEW_CREATED,
    DOCUMENT_WEBHOOK_SUBSCRIPTION_CREATED,
)

DOCUMENT_WEBHOOK_EVENT_TYPES = frozenset({DOCUMENT_SHARED, DOCUMENT_VIEWED})

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/documents/security",
    tags=["document-security"],
)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class DocumentSecret(Base):
    """PM-040: an encrypted document password/password-equivalent secret."""

    __tablename__ = "document_secrets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_document_secret_workspace_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EncryptedDocumentBlob(Base):
    """PM-156: file bytes stored only as an authenticated-encrypted token."""

    __tablename__ = "encrypted_document_blobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    plaintext_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class WatermarkView(Base):
    """PM-045: a per-view, per-viewer watermark rendered at view time."""

    __tablename__ = "watermark_views"
    __table_args__ = (UniqueConstraint("view_token", name="uq_watermark_view_token"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    viewer_email: Mapped[str] = mapped_column(String(320), nullable=False)
    viewer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    view_token: Mapped[str] = mapped_column(String(128), nullable=False)
    watermark_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# ---------------------------------------------------------------------------
# Schemas (all reject unknown fields)
# ---------------------------------------------------------------------------


class SecretCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=8192)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("secret name must not be empty")
        return stripped


class SecretOut(BaseModel):
    """Metadata only: no ciphertext, no key material, no secret value."""

    id: str
    name: str
    key_id: str

    model_config = ConfigDict(from_attributes=True)


class EncryptedBlobOut(BaseModel):
    id: str
    workspace_id: str
    document_id: str
    name: str
    mime_type: str
    size_bytes: int
    plaintext_checksum_sha256: str
    key_id: str
    created_by: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class WatermarkViewCreate(BaseModel):
    viewer_email: str = Field(min_length=3, max_length=320)
    viewer_name: str | None = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @field_validator("viewer_email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        email_addr = value.strip().lower()
        if email_addr.count("@") != 1 or any(c.isspace() for c in email_addr):
            raise ValueError("viewer_email must be a single email address")
        return email_addr

    @field_validator("viewer_name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class WatermarkViewOut(BaseModel):
    id: str
    workspace_id: str
    document_id: str
    viewer_email: str
    viewer_name: str | None
    view_token: str
    watermark_text: str
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class DocumentWebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=2000)
    secret: str = Field(min_length=16, max_length=256)
    event_types: list[str] = Field(default_factory=lambda: [DOCUMENT_SHARED])

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("subscription name must not be empty")
        return stripped

    @field_validator("url")
    @classmethod
    def http_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("webhook url must be an http(s) URL without credentials")
        return value.strip()

    @field_validator("event_types")
    @classmethod
    def document_events_only(cls, value: list[str]) -> list[str]:
        if not value or len(set(value)) != len(value) or any(
            event not in DOCUMENT_WEBHOOK_EVENT_TYPES for event in value
        ):
            raise ValueError("only document.shared and document.viewed are supported")
        return value


class DocumentWebhookOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    url: str
    event_types: list[str]
    enabled: bool
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class SignedShareRequest(BaseModel):
    subscription_id: str = Field(min_length=1, max_length=36)
    recipient_email: str | None = Field(default=None, max_length=320)

    model_config = ConfigDict(extra="forbid")

    @field_validator("subscription_id", "recipient_email")
    @classmethod
    def clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


# ---------------------------------------------------------------------------
# Versioned, authenticated encryption (stdlib only)
# ---------------------------------------------------------------------------


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def load_encryption_keys(raw: str | None = None) -> tuple[dict[str, bytes], str]:
    """Return (key_id -> 32-byte key, active_key_id) from config or the dev default.

    ``raw`` exists for tests and for explicit in-process rotation helpers; the
    default reads ``NOVARA_DOCUMENT_ENCRYPTION_KEYS`` on every call so key
    rotation does not require a process restart.
    """
    configured = os.getenv(KEY_ENV) if raw is None else raw
    if configured is None or not configured.strip():
        dev_key = hashlib.sha256(b"novara-local-dev-document-encryption-key-v1").digest()
        return {DEV_KEY_ID: dev_key}, DEV_KEY_ID

    keys: dict[str, bytes] = {}
    active: str | None = None
    for part in configured.split(","):
        part = part.strip()
        if not part:
            continue
        fields = part.split(":")
        if len(fields) == 2:
            key_id, encoded, marked_active = fields[0], fields[1], False
        elif len(fields) == 3 and fields[2] == "active":
            key_id, encoded, marked_active = fields[0], fields[1], True
        else:
            raise ValueError("malformed document encryption key entry")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", key_id):
            raise ValueError("malformed document encryption key id")
        try:
            key = base64.b64decode(encoded, validate=True)
        except ValueError as exc:  # binascii.Error is a ValueError subclass
            raise ValueError("malformed document encryption key bytes") from exc
        if len(key) != 32:
            raise ValueError("document encryption keys must be 32 bytes")
        if key_id in keys:
            raise ValueError("duplicate document encryption key id")
        keys[key_id] = key
        if marked_active:
            if active is not None:
                raise ValueError("more than one active document encryption key")
            active = key_id
    if not keys:
        raise ValueError("no document encryption keys configured")
    if active is None:
        if len(keys) != 1:
            raise ValueError("an active document encryption key is required")
        active = next(iter(keys))
    return keys, active


def active_key_id() -> str:
    """The key id new records are encrypted under."""
    return load_encryption_keys()[1]


def _derived_key(key: bytes, label: bytes) -> bytes:
    return hmac.new(key, label, hashlib.sha256).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    blocks = []
    counter = 0
    produced = 0
    while produced < length:
        blocks.append(hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest())
        produced += 32
        counter += 1
    return b"".join(blocks)[:length]


def _encrypt_bytes(plaintext: bytes, key_id: str | None = None) -> str:
    keys, active = load_encryption_keys()
    selected = key_id or active
    if selected not in keys:
        raise ValueError("unknown document encryption key id")
    key = keys[selected]
    nonce = secrets.token_bytes(16)
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, _keystream(_derived_key(key, b"novara-enc-v1"), nonce, len(plaintext))))
    tag = hmac.new(
        _derived_key(key, b"novara-mac-v1"),
        b"v1" + nonce + ciphertext,
        hashlib.sha256,
    ).digest()
    return ".".join(("v1", selected, _b64encode(nonce), _b64encode(ciphertext), _b64encode(tag)))


def _decrypt_bytes(token: str) -> bytes:
    parts = token.split(".")
    if len(parts) != 5 or parts[0] != "v1":
        raise ValueError("invalid encrypted token")
    key_id, nonce_text, cipher_text, tag_text = parts[1], parts[2], parts[3], parts[4]
    keys, _active = load_encryption_keys()
    if key_id not in keys:
        raise ValueError("encrypted token uses an unavailable key")
    try:
        nonce = _b64decode(nonce_text)
        ciphertext = _b64decode(cipher_text)
        supplied_tag = _b64decode(tag_text)
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError("invalid encrypted token encoding") from exc
    if len(nonce) != 16 or len(supplied_tag) != 32:
        raise ValueError("invalid encrypted token")
    key = keys[key_id]
    expected_tag = hmac.new(
        _derived_key(key, b"novara-mac-v1"),
        b"v1" + nonce + ciphertext,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(expected_tag, supplied_tag):
        raise ValueError("encrypted token authentication failed")
    return bytes(
        a ^ b for a, b in zip(ciphertext, _keystream(_derived_key(key, b"novara-enc-v1"), nonce, len(ciphertext)))
    )


def encrypt_secret(plaintext: str, key_id: str | None = None) -> str:
    """Encrypt a UTF-8 secret into a versioned, authenticated token."""
    return _encrypt_bytes(plaintext.encode("utf-8"), key_id)


def decrypt_secret(token: str) -> str:
    """Authenticate and decrypt a token produced by :func:`encrypt_secret`."""
    try:
        return _decrypt_bytes(token).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("encrypted token is not UTF-8 text") from exc


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _document_or_404(db: Session, workspace_id: str, document_id: str) -> Document:
    document = db.execute(
        select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


def _secret_or_404(db: Session, workspace_id: str, secret_id: str) -> DocumentSecret:
    row = db.execute(
        select(DocumentSecret).where(
            DocumentSecret.id == secret_id, DocumentSecret.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="secret not found")
    return row


def _blob_or_404(db: Session, workspace_id: str, blob_id: str) -> EncryptedDocumentBlob:
    row = db.execute(
        select(EncryptedDocumentBlob).where(
            EncryptedDocumentBlob.id == blob_id, EncryptedDocumentBlob.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="encrypted file not found")
    return row


def _view_by_token_or_404(db: Session, workspace_id: str, view_token: str) -> WatermarkView:
    row = db.execute(
        select(WatermarkView).where(
            WatermarkView.view_token == view_token, WatermarkView.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="watermark view not found")
    return row


def _document_webhook_or_404(
    db: Session, workspace_id: str, subscription_id: str
) -> WebhookSubscription:
    row = db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == subscription_id,
            WebhookSubscription.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="document webhook subscription not found")
    return row


def _safe_filename(name: str) -> str:
    base = os.path.basename(name.strip()).replace("..", "").replace("/", "").replace("\\", "")
    base = "".join(c for c in base if c.isprintable() and c not in {'"', "'", "\r", "\n"})
    return base[:200] or "document.bin"


def _safe_mime(value: str) -> str:
    candidate = value.strip()[:120]
    if not re.fullmatch(r"[A-Za-z0-9.+/-]+", candidate):
        return "application/octet-stream"
    return candidate


def _svg_overlay(text: str) -> str:
    """One reusable overlay with four tiled marks; the viewer applies it to each page."""
    escaped = html.escape(text, quote=True)
    marks = "\n".join(
        f'  <text x="24" y="{y}" font-family="sans-serif" font-size="18" '
        f'fill="#b91c1c" fill-opacity="0.35">{escaped}</text>'
        for y in (70, 230, 390, 550)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="840" height="600" '
        'viewBox="0 0 840 600" role="img" aria-label="Confidential document watermark">\n'
        f"{marks}\n</svg>"
    )


# ---------------------------------------------------------------------------
# PM-040 — secret vault
# ---------------------------------------------------------------------------


@router.post("/secrets", response_model=SecretOut, status_code=status.HTTP_201_CREATED)
def store_secret(
    workspace_id: str,
    body: SecretCreate,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> DocumentSecret:
    verify_workspace(principal, workspace_id)
    if db.execute(
        select(DocumentSecret.id).where(
            DocumentSecret.workspace_id == workspace_id, DocumentSecret.name == body.name
        )
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="a secret with this name already exists")
    key_id = active_key_id()
    token = encrypt_secret(body.value, key_id=key_id)
    secret = DocumentSecret(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name,
        ciphertext=token,
        key_id=key_id,
        created_by=principal.user.id,
        created_at=now(),
        rotated_at=None,
    )
    db.add(secret)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_SECRET_STORED,
        entity_id=secret.id,
        payload={"name": secret.name, "key_id": secret.key_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return secret


@router.get("/secrets", response_model=list[SecretOut])
def list_secrets(
    workspace_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> list[DocumentSecret]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(DocumentSecret)
        .where(DocumentSecret.workspace_id == workspace_id)
        .order_by(DocumentSecret.created_at)
    ).scalars().all()


@router.post("/secrets/rotate")
def rotate_secrets(
    workspace_id: str,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """Re-encrypt every secret in this workspace under the active key."""
    verify_workspace(principal, workspace_id)
    key_id = active_key_id()
    rows = db.execute(
        select(DocumentSecret).where(DocumentSecret.workspace_id == workspace_id)
    ).scalars().all()
    try:
        for row in rows:
            plaintext = decrypt_secret(row.ciphertext)
            row.ciphertext = encrypt_secret(plaintext, key_id=key_id)
            row.key_id = key_id
            row.rotated_at = now()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="a stored secret uses an unavailable key") from exc
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_SECRET_ROTATED,
        payload={"rotated": len(rows), "key_id": key_id},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"rotated": len(rows), "key_id": key_id}


# ---------------------------------------------------------------------------
# PM-156 — encrypted file at rest
# ---------------------------------------------------------------------------


@router.post("/encrypted-files", response_model=EncryptedBlobOut, status_code=status.HTTP_201_CREATED)
async def store_encrypted_file(
    workspace_id: str,
    document_id: str = Form(...),
    file: UploadFile = File(...),
    name: str = Form(default=""),
    mime_type: str = Form(default=""),
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> EncryptedDocumentBlob:
    verify_workspace(principal, workspace_id)
    _document_or_404(db, workspace_id, document_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="file must not be empty")
    if len(data) > MAX_BLOB_BYTES:
        raise HTTPException(status_code=413, detail="file exceeds the configured limit")
    key_id = active_key_id()
    token = _encrypt_bytes(data, key_id=key_id)
    safe_name = _safe_filename(name or file.filename or "document.bin")
    blob = EncryptedDocumentBlob(
        id=new_id(),
        workspace_id=workspace_id,
        document_id=document_id,
        name=safe_name,
        mime_type=_safe_mime(mime_type or file.content_type or "application/octet-stream"),
        ciphertext=token,
        size_bytes=len(data),
        plaintext_checksum_sha256=hashlib.sha256(data).hexdigest(),
        key_id=key_id,
        created_by=principal.user.id,
        created_at=now(),
    )
    db.add(blob)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_ENCRYPTED_FILE_STORED,
        entity_id=blob.id,
        payload={
            "document_id": document_id,
            "name": blob.name,
            "size_bytes": blob.size_bytes,
            "key_id": blob.key_id,
        },
        actor_id=principal.user.id,
    )
    db.commit()
    return blob


@router.get("/encrypted-files/{blob_id}/download")
def download_encrypted_file(
    workspace_id: str,
    blob_id: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> Response:
    verify_workspace(principal, workspace_id)
    blob = _blob_or_404(db, workspace_id, blob_id)
    try:
        plaintext = _decrypt_bytes(blob.ciphertext)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="stored file failed authentication") from exc
    if not hmac.compare_digest(hashlib.sha256(plaintext).hexdigest(), blob.plaintext_checksum_sha256):
        raise HTTPException(status_code=500, detail="stored file failed integrity check")
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_DOWNLOADED,
        entity_id=blob.document_id,
        payload={"encrypted_blob_id": blob.id, "name": blob.name, "action": "download"},
        actor_id=principal.user.id,
    )
    db.commit()
    return Response(
        content=plaintext,
        media_type=blob.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{_safe_filename(blob.name)}"',
            "Cache-Control": "no-store",
        },
    )


# ---------------------------------------------------------------------------
# PM-045 — dynamic, per-view watermarking
# ---------------------------------------------------------------------------


@router.post(
    "/documents/{document_id}/watermark-views",
    response_model=WatermarkViewOut,
    status_code=status.HTTP_201_CREATED,
)
def create_watermark_view(
    workspace_id: str,
    document_id: str,
    body: WatermarkViewCreate,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> WatermarkView:
    verify_workspace(principal, workspace_id)
    _document_or_404(db, workspace_id, document_id)
    view_id = new_id()
    identity = (
        f"{body.viewer_name} <{body.viewer_email}>"
        if body.viewer_name
        else body.viewer_email
    )
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S UTC")
    watermark_text = f"NOVARA CONFIDENTIAL | {identity} | view {view_id} | {timestamp}"
    view = WatermarkView(
        id=view_id,
        workspace_id=workspace_id,
        document_id=document_id,
        viewer_email=body.viewer_email,
        viewer_name=body.viewer_name,
        view_token=secrets.token_urlsafe(24),
        watermark_text=watermark_text,
        created_at=now(),
    )
    db.add(view)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=WATERMARK_VIEW_CREATED,
        entity_id=view.id,
        payload={"document_id": document_id, "viewer_email": view.viewer_email},
        actor_id=principal.user.id,
    )
    db.commit()
    return view


@router.get("/watermark-views/{view_token}/overlay")
def watermark_overlay(
    workspace_id: str,
    view_token: str,
    principal: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
) -> Response:
    verify_workspace(principal, workspace_id)
    view = _view_by_token_or_404(db, workspace_id, view_token)
    return Response(
        content=_svg_overlay(view.watermark_text),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# PM-117 — signed outgoing document webhooks (reuses the shared deliverer)
# ---------------------------------------------------------------------------


@router.post(
    "/webhook-subscriptions",
    response_model=DocumentWebhookOut,
    status_code=status.HTTP_201_CREATED,
)
def create_document_webhook_subscription(
    workspace_id: str,
    body: DocumentWebhookCreate,
    principal: Principal = Depends(require(DOCUMENT_ADMIN)),
    db: Session = Depends(get_db),
) -> WebhookSubscription:
    verify_workspace(principal, workspace_id)
    if db.execute(
        select(WebhookSubscription.id).where(
            WebhookSubscription.workspace_id == workspace_id, WebhookSubscription.name == body.name
        )
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="a subscription with this name already exists")
    subscription = WebhookSubscription(
        id=new_id(),
        workspace_id=workspace_id,
        name=body.name,
        url=body.url,
        secret=body.secret,
        event_types=list(body.event_types),
        enabled=True,
        created_by=principal.user.id,
        created_at=now(),
    )
    db.add(subscription)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_WEBHOOK_SUBSCRIPTION_CREATED,
        entity_id=subscription.id,
        payload={"name": subscription.name, "event_types": subscription.event_types},
        actor_id=principal.user.id,
    )
    db.commit()
    return subscription


@router.post("/documents/{document_id}/signed-share-delivery")
def signed_share_delivery(
    workspace_id: str,
    document_id: str,
    body: SignedShareRequest,
    principal: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    document = _document_or_404(db, workspace_id, document_id)
    subscription = _document_webhook_or_404(db, workspace_id, body.subscription_id)
    if not subscription.enabled or DOCUMENT_SHARED not in subscription.event_types:
        raise HTTPException(status_code=422, detail="subscription does not accept document.shared")
    result = deliver_webhook(
        db,
        workspace_id=workspace_id,
        subscription_id=subscription.id,
        event_type=DOCUMENT_SHARED,
        payload={
            "document_id": document.id,
            "title": document.title,
            "recipient_email": body.recipient_email,
            "shared_by": principal.user.id,
        },
    )
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=DOCUMENT_SHARED,
        entity_id=document.id,
        payload={
            "subscription_id": subscription.id,
            "delivery_id": result["delivery_id"],
            "status": result["status"],
            "recipient_email": body.recipient_email,
        },
        idempotency_key=f"document-shared:{result['delivery_id']}",
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "delivery_id": result["delivery_id"],
        "event": DOCUMENT_SHARED,
        "status": result["status"],
        "attempts": result["attempts"],
        "status_code": result["status_code"],
        "subscription_id": subscription.id,
    }


# Kept importable for tests and for receivers that want the exact helper used
# by the deliverer; no second signature implementation is introduced here.
__all__ = [
    "DOCUMENT_SECRET_STORED",
    "DOCUMENT_SECRET_ROTATED",
    "DOCUMENT_ENCRYPTED_FILE_STORED",
    "DOCUMENT_SHARED",
    "WATERMARK_VIEW_CREATED",
    "DOCUMENT_WEBHOOK_SUBSCRIPTION_CREATED",
    "DOCUMENT_WEBHOOK_EVENT_TYPES",
    "DocumentSecret",
    "EncryptedDocumentBlob",
    "WatermarkView",
    "encrypt_secret",
    "decrypt_secret",
    "load_encryption_keys",
    "active_key_id",
    "webhook_signature",
    "WebhookDelivery",
    "router",
]
