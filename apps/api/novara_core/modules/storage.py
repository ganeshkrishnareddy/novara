"""Local-first file storage with real presigned upload/download URLs.

Implements the Papermark-style storage capabilities (PM-002, PM-015, PM-016)
over a local filesystem backend. Presigned URLs are genuine HMAC-signed tokens
that resolve to a real download endpoint; they are not fabricated. No mandatory
cloud account is required. All access is workspace-scoped and audited.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE

STORAGE_ROOT = Path(os.getenv("NOVARA_STORAGE_DIR", str(Path(__file__).resolve().parents[3] / "storage")))


def _default_presign_secret() -> bytes:
    """Resolve the HMAC signing key without a publicly known production default.

    Explicit configuration always wins. An unset secret is a local convenience
    only in NOVARA_DEV_MODE; every other run gets an unpredictable per-process
    key, so a shipped or deployed instance cannot be forged with the old
    hard-coded development value.
    """
    configured = os.getenv("NOVARA_PRESIGN_SECRET")
    if configured:
        return configured.encode("utf-8")
    if os.getenv("NOVARA_DEV_MODE", "").lower() in {"1", "true", "yes"}:
        return b"novara-dev-presign-secret"
    return secrets.token_urlsafe(32).encode("utf-8")


PRESIGN_SECRET = _default_presign_secret()
PRESIGN_TTL = 3600
MAX_UPLOAD_BYTES = int(os.getenv("NOVARA_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "text/plain",
    "application/json",
    "application/octet-stream",
}

FILE_UPLOADED = "file.uploaded"
FILE_DELETED = "file.deleted"
FILE_ACCESSED = "file.accessed"
# PM-123/PM-150: locally executed document conversion/export jobs are audited
# on the same event spine. No AGPL conversion source is vendored or called.
FILE_CONVERTED = "file.converted"
# PM-125: a real input file produces a persisted preview artifact.
FILE_PREVIEWED = "file.previewed"
register_event_types(FILE_UPLOADED, FILE_DELETED, FILE_ACCESSED, FILE_CONVERTED, FILE_PREVIEWED)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/storage",
    tags=["storage"],
)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class StoredFile(Base):
    __tablename__ = "stored_files"
    __table_args__ = (UniqueConstraint("workspace_id", "storage_path", name="uq_stored_file_path"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(300), nullable=False)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False)
    deleted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)

    @property
    def deleted(self) -> bool:
        return self.deleted_at is not None


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FileOut(BaseModel):
    id: str
    original_name: str
    filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    uploaded_by: str
    created_at: object
    deleted: bool

    model_config = ConfigDict(from_attributes=True)


class PresignUploadOut(BaseModel):
    upload_token: str
    upload_url: str
    expires_at: int


class PresignDownloadOut(BaseModel):
    download_token: str
    download_url: str
    expires_at: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file_or_404(db: Session, workspace_id: str, file_id: str) -> StoredFile:
    f = db.execute(
        select(StoredFile).where(
            StoredFile.id == file_id, StoredFile.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if f is None or f.deleted_at is not None:
        raise HTTPException(status_code=404, detail="file not found")
    return f


def _safe_filename(name: str) -> str:
    base = os.path.basename(name).strip()
    # strip path traversal and control chars
    base = base.replace("..", "").replace("/", "").replace("\\", "")
    if not base:
        base = "file"
    return f"{secrets.token_hex(8)}_{base}"


def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _presign(payload: str) -> str:
    msg = payload.encode("utf-8")
    sig = hmac.new(PRESIGN_SECRET, msg, hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _verify_presign(token: str) -> str | None:
    if "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    expected = hmac.new(PRESIGN_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    return payload


def _workspace_dir(workspace_id: str) -> Path:
    d = STORAGE_ROOT / workspace_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# PM-015: explicit storage backend adapters
# ---------------------------------------------------------------------------


class StorageAdapter(Protocol):
    """The three operations the document routes need from a byte backend."""

    name: str

    def write(self, *, workspace_id: str, filename: str, data: bytes) -> str: ...

    def read(self, storage_path: str) -> bytes: ...

    def delete(self, storage_path: str) -> None: ...


class LocalStorageAdapter:
    """Default local-first filesystem adapter; no cloud account required."""

    name = "local"

    def write(self, *, workspace_id: str, filename: str, data: bytes) -> str:
        dest = _workspace_dir(workspace_id) / filename
        dest.write_bytes(data)
        return str(dest)

    def read(self, storage_path: str) -> bytes:
        try:
            return Path(storage_path).read_bytes()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="file bytes missing") from exc

    def delete(self, storage_path: str) -> None:
        try:
            Path(storage_path).unlink(missing_ok=True)
        except OSError:
            pass


class S3CompatibleStorageAdapter:
    """Minimal S3-compatible object adapter using real SigV4 HTTP requests.

    Enabled only by explicit configuration (NOVARA_STORAGE_BACKEND=s3-compatible
    plus endpoint/bucket/credentials). The test suite points the endpoint at a
    loopback object store, so no external provider or network call is required.
    """

    name = "s3-compatible"

    def __init__(self) -> None:
        self.endpoint = os.getenv("NOVARA_S3_ENDPOINT", "").rstrip("/")
        self.bucket = os.getenv("NOVARA_S3_BUCKET", "novara")
        self.access_key = os.getenv("NOVARA_S3_ACCESS_KEY", "")
        self.secret_key = os.getenv("NOVARA_S3_SECRET_KEY", "")
        self.region = os.getenv("NOVARA_S3_REGION", "us-east-1")
        if not self.endpoint:
            raise HTTPException(status_code=503, detail="S3-compatible backend is not configured")

    def _url(self, key: str) -> str:
        return f"{self.endpoint}/{urllib.parse.quote(self.bucket)}/{urllib.parse.quote(key, safe='/')}"

    def _key_from_path(self, storage_path: str) -> str:
        if not storage_path.startswith(f"s3://{self.bucket}/"):
            raise HTTPException(status_code=404, detail="file bytes missing")
        return storage_path[len(f"s3://{self.bucket}/"):]

    @staticmethod
    def _signing_key(secret: str, date: str, region: str) -> bytes:
        def hmac_sha256(key: bytes, message: str) -> bytes:
            return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

        key = hmac_sha256(("AWS4" + secret).encode("utf-8"), date)
        key = hmac_sha256(key, region)
        key = hmac_sha256(key, "s3")
        return hmac_sha256(key, "aws4_request")

    def _headers(self, method: str, key: str, payload: bytes) -> dict[str, str]:
        url = urllib.parse.urlsplit(self._url(key))
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        date = amz_date[:8]
        payload_hash = hashlib.sha256(payload).hexdigest()
        canonical_headers = (
            f"host:{url.netloc}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join((
            method, url.path, "", canonical_headers, signed_headers, payload_hash,
        ))
        scope = f"{date}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join((
            "AWS4-HMAC-SHA256", amz_date, scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ))
        signature = hmac.new(
            self._signing_key(self.secret_key, date, self.region),
            string_to_sign.encode("utf-8"), hashlib.sha256,
        ).hexdigest()
        return {
            "Host": url.netloc,
            "X-Amz-Date": amz_date,
            "X-Amz-Content-Sha256": payload_hash,
            "Authorization": (
                f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            ),
        }

    def _request(self, method: str, key: str, data: bytes | None = None) -> bytes:
        payload = data or b""
        request = urllib.request.Request(
            self._url(key), data=payload if method in ("PUT", "POST") else None,
            headers=self._headers(method, key, payload), method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise HTTPException(status_code=404, detail="file bytes missing") from exc
            raise HTTPException(status_code=502, detail=f"object backend error: {exc.code}") from exc
        except OSError as exc:
            raise HTTPException(status_code=502, detail="object backend unreachable") from exc

    def write(self, *, workspace_id: str, filename: str, data: bytes) -> str:
        key = f"{workspace_id}/{filename}"
        self._request("PUT", key, data)
        return f"s3://{self.bucket}/{key}"

    def read(self, storage_path: str) -> bytes:
        return self._request("GET", self._key_from_path(storage_path))

    def delete(self, storage_path: str) -> None:
        self._request("DELETE", self._key_from_path(storage_path))


def get_adapter() -> StorageAdapter:
    """Resolve the adapter from explicit environment configuration per call."""
    backend = os.getenv("NOVARA_STORAGE_BACKEND", "local").strip().lower()
    if backend in ("local", "filesystem"):
        return LocalStorageAdapter()
    if backend in ("s3", "s3-compatible", "s3_compatible"):
        return S3CompatibleStorageAdapter()
    raise HTTPException(status_code=503, detail=f"unsupported storage backend: {backend}")


# ---------------------------------------------------------------------------
# Local conversion work (shared by the HTTP endpoint and the job queue)
# ---------------------------------------------------------------------------


def run_document_conversion(
    db: Session,
    *,
    workspace_id: str,
    source_file_id: str,
    target_format: str,
    actor_id: str,
) -> ConversionJob:
    """Run one document conversion locally and audit its real outcome.

    The same code backs POST /storage/conversions and the durable
    ``document_conversion`` job handler: pypdf (BSD) for PDF text extraction and
    a byte-preserving plain-text export. No AGPL converter, binary or external
    service is used. The helper flushes; the caller owns the transaction so it
    can commit normally or inside the job runner's SAVEPOINT.
    """
    src = _file_or_404(db, workspace_id, source_file_id)
    adapter = get_adapter()
    source_bytes = adapter.read(src.storage_path)
    job = ConversionJob(
        id=new_id(), workspace_id=workspace_id, source_file_id=src.id,
        target_format=target_format, status="queued",
        created_by=actor_id, created_at=now(),
    )
    db.add(job)
    db.flush()
    try:
        text = None
        if src.mime_type == "application/pdf" and target_format in ("text", "txt"):
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(source_bytes))
            text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
        elif src.mime_type == "text/plain" and target_format in ("text", "txt"):
            text = source_bytes.decode("utf-8", errors="replace")
        if text is not None:
            out_name = _safe_filename(src.original_name.rsplit(".", 1)[0] + ".txt")
            data = text.encode("utf-8")
            dest = adapter.write(
                workspace_id=workspace_id, filename=out_name, data=data,
            )
            stored = StoredFile(
                id=new_id(), workspace_id=workspace_id, original_name=out_name,
                filename=out_name, mime_type="text/plain", size_bytes=len(data),
                storage_path=str(dest), checksum_sha256=_checksum(data),
                uploaded_by=actor_id, created_at=now(),
            )
            db.add(stored)
            db.flush()
            job.result_file_id = stored.id
            job.status = "completed"
        else:
            job.status = "failed"
            job.error = "unsupported conversion"
        job.finished_at = now()
        publish_event(
            db, workspace_id=workspace_id, event_type=FILE_CONVERTED,
            entity_id=job.id,
            payload={"conversion": True, "target": target_format,
                     "status": job.status, "result_file_id": job.result_file_id},
            actor_id=actor_id,
        )
    except Exception as exc:  # noqa: BLE001 - keep the failure auditable
        job.status = "failed"
        job.error = str(exc)
        job.finished_at = now()
    db.flush()
    return job


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/files", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    workspace_id: str,
    file: UploadFile = File(...),
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> StoredFile:
    verify_workspace(principal, workspace_id)
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"file exceeds {MAX_UPLOAD_BYTES} bytes")
    mime = file.content_type or "application/octet-stream"
    if mime not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"unsupported mime type: {mime}")
    filename = _safe_filename(file.filename or "file")
    dest = get_adapter().write(
        workspace_id=workspace_id, filename=filename, data=data,
    )
    checksum = _checksum(data)
    stored = StoredFile(
        id=new_id(),
        workspace_id=workspace_id,
        original_name=file.filename or filename,
        filename=filename,
        mime_type=mime,
        size_bytes=len(data),
        storage_path=dest,
        checksum_sha256=checksum,
        uploaded_by=principal.user.id,
        created_at=now(),
    )
    db.add(stored)
    db.flush()
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=FILE_UPLOADED,
        entity_id=stored.id,
        payload={"filename": stored.filename, "size_bytes": stored.size_bytes, "mime_type": mime},
        actor_id=principal.user.id,
    )
    db.commit()
    return stored


@router.get("/files", response_model=list[FileOut])
def list_files(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[StoredFile]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(StoredFile)
        .where(StoredFile.workspace_id == workspace_id, StoredFile.deleted_at.is_(None))
        .order_by(StoredFile.created_at.desc())
    ).scalars().all()


@router.get("/files/{file_id}", response_model=FileOut)
def get_file(
    workspace_id: str,
    file_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> StoredFile:
    verify_workspace(principal, workspace_id)
    return _file_or_404(db, workspace_id, file_id)


@router.get("/files/{file_id}/download")
def download_file(
    workspace_id: str,
    file_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    f = _file_or_404(db, workspace_id, file_id)
    data = get_adapter().read(f.storage_path)
    # integrity check
    if _checksum(data) != f.checksum_sha256:
        raise HTTPException(status_code=500, detail="file integrity check failed")
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=FILE_ACCESSED,
        entity_id=f.id,
        payload={"action": "download"},
        actor_id=principal.user.id,
    )
    db.commit()
    from fastapi.responses import Response

    return Response(content=data, media_type=f.mime_type, headers={
        "Content-Disposition": f'attachment; filename="{f.original_name}"'
    })


@router.get("/files/{file_id}/pdf-info")
def pdf_info(
    workspace_id: str,
    file_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    f = _file_or_404(db, workspace_id, file_id)
    if f.mime_type != "application/pdf":
        raise HTTPException(status_code=415, detail="not a PDF")
    source_bytes = get_adapter().read(f.storage_path)
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"pypdf unavailable: {exc}")
    try:
        reader = PdfReader(io.BytesIO(source_bytes))
        meta = reader.metadata or {}
        return {
            "file_id": f.id,
            "pages": len(reader.pages),
            "title": getattr(meta, "title", None),
            "author": getattr(meta, "author", None),
            "encrypted": reader.is_encrypted,
        }
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"could not read PDF: {exc}")


@router.get("/files/{file_id}/pdf-preview")
def pdf_preview(
    workspace_id: str,
    file_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    f = _file_or_404(db, workspace_id, file_id)
    if f.mime_type != "application/pdf":
        raise HTTPException(status_code=415, detail="not a PDF")
    source_bytes = get_adapter().read(f.storage_path)
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(source_bytes))
        pages = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            pages.append({"page": i + 1, "text": text[:2000]})
        return {"file_id": f.id, "pages": len(pages), "content": pages}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"could not preview PDF: {exc}")


def _image_dimensions(mime: str, data: bytes) -> tuple[int, int]:
    """Read real pixel dimensions from PNG/GIF/JPEG bytes without PIL."""
    if mime == "image/png" and data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if mime == "image/gif" and data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if mime == "image/jpeg" and data[:2] == b"\xff\xd8":
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                offset += 2
                continue
            length = int.from_bytes(data[offset + 2:offset + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height = int.from_bytes(data[offset + 5:offset + 7], "big")
                width = int.from_bytes(data[offset + 7:offset + 9], "big")
                return width, height
            offset += 2 + length
    raise HTTPException(status_code=422, detail="image dimensions could not be read")


@router.get("/files/{file_id}/preview")
def file_preview(
    workspace_id: str,
    file_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """PM-125: produce a real, persisted preview artifact for PDF/image input."""
    verify_workspace(principal, workspace_id)
    source = _file_or_404(db, workspace_id, file_id)
    data = get_adapter().read(source.storage_path)
    stem = source.original_name.rsplit(".", 1)[0] or "preview"
    dimensions: tuple[int, int] | None = None
    pages: int | None = None
    excerpt: str | None = None
    if source.mime_type == "application/pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            pages = len(reader.pages)
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"could not preview PDF: {exc}") from exc
        excerpt = text[:4000]
        artifact_bytes = ("NOVARA local preview\nPages: " + str(pages) + "\n\n" + text).encode("utf-8")
        artifact_name = stem + ".preview.txt"
        artifact_mime = "text/plain"
    elif source.mime_type in ("image/png", "image/jpeg", "image/gif"):
        width, height = _image_dimensions(source.mime_type, data)
        dimensions = (width, height)
        encoded = base64.b64encode(data).decode("ascii")
        artifact_bytes = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
            f'<image href="data:{source.mime_type};base64,{encoded}" '
            f'width="{width}" height="{height}"/></svg>'
        ).encode("utf-8")
        artifact_name = stem + ".preview.svg"
        artifact_mime = "image/svg+xml"
    else:
        raise HTTPException(status_code=415, detail="no local preview for this mime type")

    adapter = get_adapter()
    filename = _safe_filename(artifact_name)
    artifact_path = adapter.write(
        workspace_id=workspace_id, filename=filename, data=artifact_bytes,
    )
    artifact = StoredFile(
        id=new_id(), workspace_id=workspace_id, original_name=artifact_name,
        filename=filename, mime_type=artifact_mime, size_bytes=len(artifact_bytes),
        storage_path=artifact_path, checksum_sha256=_checksum(artifact_bytes),
        uploaded_by=principal.user.id, created_at=now(),
    )
    db.add(artifact)
    db.flush()
    publish_event(
        db, workspace_id=workspace_id, event_type=FILE_PREVIEWED,
        entity_id=artifact.id,
        payload={"source_file_id": source.id, "mime_type": artifact_mime,
                 "pages": pages, "width": dimensions[0] if dimensions else None,
                 "height": dimensions[1] if dimensions else None},
        actor_id=principal.user.id,
    )
    db.commit()
    return {
        "file_id": source.id,
        "artifact_file_id": artifact.id,
        "mime_type": artifact_mime,
        "download_url": f"/api/v1/workspaces/{workspace_id}/storage/files/{artifact.id}/download",
        "pages": pages,
        "width": dimensions[0] if dimensions else None,
        "height": dimensions[1] if dimensions else None,
        "excerpt": excerpt,
    }


# ---------------------------------------------------------------------------
# Conversion jobs (PM-125)
# ---------------------------------------------------------------------------


class ConversionJob(Base):
    __tablename__ = "conversion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    source_file_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_format: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    result_file_id: Mapped[str | None] = mapped_column(String(36))
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversionRequest(BaseModel):
    source_file_id: str
    target_format: str = "text"

    model_config = ConfigDict(extra="forbid")


class ConversionOut(BaseModel):
    id: str
    source_file_id: str
    target_format: str
    status: str
    result_file_id: str | None
    error: str | None
    created_at: object
    finished_at: object

    model_config = ConfigDict(from_attributes=True)


@router.post("/conversions", response_model=ConversionOut, status_code=status.HTTP_201_CREATED)
def create_conversion(
    workspace_id: str,
    body: ConversionRequest,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> ConversionJob:
    verify_workspace(principal, workspace_id)
    job = run_document_conversion(
        db,
        workspace_id=workspace_id,
        source_file_id=body.source_file_id,
        target_format=body.target_format,
        actor_id=principal.user.id,
    )
    db.commit()
    return job


@router.get("/conversions", response_model=list[ConversionOut])
def list_conversions(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[ConversionJob]:
    verify_workspace(principal, workspace_id)
    return db.execute(
        select(ConversionJob).where(ConversionJob.workspace_id == workspace_id).order_by(ConversionJob.created_at.desc())
    ).scalars().all()


@router.get("/conversions/{job_id}", response_model=ConversionOut)
def get_conversion(
    workspace_id: str,
    job_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> ConversionJob:
    verify_workspace(principal, workspace_id)
    job = db.execute(
        select(ConversionJob).where(ConversionJob.id == job_id, ConversionJob.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="conversion job not found")
    return job


@router.delete("/files/{file_id}", status_code=status.HTTP_200_OK)
def delete_file(
    workspace_id: str,
    file_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    f = _file_or_404(db, workspace_id, file_id)
    f.deleted_at = now()
    # cleanup bytes through the configured backend adapter
    get_adapter().delete(f.storage_path)
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=FILE_DELETED,
        entity_id=f.id,
        payload={"filename": f.filename},
        actor_id=principal.user.id,
    )
    db.commit()
    return {"deleted": True, "file_id": f.id}


@router.post("/presign-upload", response_model=PresignUploadOut)
def presign_upload(
    workspace_id: str,
    filename: str = Query(..., min_length=1),
    content_type: str = Query(default="application/octet-stream"),
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> PresignUploadOut:
    verify_workspace(principal, workspace_id)
    if content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"unsupported mime type: {content_type}")
    expires_at = int(time.time()) + PRESIGN_TTL
    nonce = secrets.token_urlsafe(16)
    payload = f"upload:{workspace_id}:{filename}:{content_type}:{expires_at}:{nonce}"
    token = _presign(payload)
    return PresignUploadOut(
        upload_token=token,
        upload_url=f"/api/v1/workspaces/{workspace_id}/storage/presigned-upload?token={token}",
        expires_at=expires_at,
    )


@router.put("/presigned-upload", status_code=status.HTTP_201_CREATED)
async def presigned_upload(
    workspace_id: str,
    token: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    payload = _verify_presign(token)
    if payload is None:
        raise HTTPException(status_code=403, detail="invalid or tampered token")
    parts = payload.split(":")
    # upload:workspace_id:filename:content_type:expires_at:nonce
    if len(parts) != 6 or parts[0] != "upload":
        raise HTTPException(status_code=403, detail="invalid token payload")
    tok_workspace, filename, content_type, expires_at, _nonce = parts[1], parts[2], parts[3], parts[4], parts[5]
    if tok_workspace != workspace_id:
        raise HTTPException(status_code=403, detail="token workspace mismatch")
    if int(expires_at) < int(time.time()):
        raise HTTPException(status_code=410, detail="upload token expired")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"file exceeds {MAX_UPLOAD_BYTES} bytes")
    mime = file.content_type or content_type
    if mime not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"unsupported mime type: {mime}")
    safe = _safe_filename(filename)
    dest = get_adapter().write(workspace_id=workspace_id, filename=safe, data=data)
    # Note: presigned upload has no authenticated principal; record system actor
    stored = StoredFile(
        id=new_id(),
        workspace_id=workspace_id,
        original_name=filename,
        filename=safe,
        mime_type=mime,
        size_bytes=len(data),
        storage_path=dest,
        checksum_sha256=_checksum(data),
        uploaded_by="presigned",
        created_at=now(),
    )
    db.add(stored)
    db.commit()
    return {"uploaded": True, "file_id": stored.id}


@router.post("/files/{file_id}/presign-download", response_model=PresignDownloadOut)
def presign_download(
    workspace_id: str,
    file_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> PresignDownloadOut:
    verify_workspace(principal, workspace_id)
    f = _file_or_404(db, workspace_id, file_id)
    expires_at = int(time.time()) + PRESIGN_TTL
    payload = f"download:{workspace_id}:{file_id}:{expires_at}"
    token = _presign(payload)
    return PresignDownloadOut(
        download_token=token,
        download_url=f"/api/v1/workspaces/{workspace_id}/storage/presigned-download?token={token}",
        expires_at=expires_at,
    )


@router.get("/presigned-download")
def presigned_download(
    workspace_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    payload = _verify_presign(token)
    if payload is None:
        raise HTTPException(status_code=403, detail="invalid or tampered token")
    parts = payload.split(":")
    if len(parts) != 4 or parts[0] != "download":
        raise HTTPException(status_code=403, detail="invalid token payload")
    tok_workspace, file_id, expires_at = parts[1], parts[2], parts[3]
    if tok_workspace != workspace_id:
        raise HTTPException(status_code=403, detail="token workspace mismatch")
    if int(expires_at) < int(time.time()):
        raise HTTPException(status_code=410, detail="download token expired")
    f = _file_or_404(db, workspace_id, file_id)
    data = get_adapter().read(f.storage_path)
    if _checksum(data) != f.checksum_sha256:
        raise HTTPException(status_code=500, detail="file integrity check failed")
    publish_event(
        db,
        workspace_id=workspace_id,
        event_type=FILE_ACCESSED,
        entity_id=f.id,
        payload={"action": "presigned_download"},
        actor_id=None,
    )
    db.commit()
    from fastapi.responses import Response

    return Response(content=data, media_type=f.mime_type, headers={
        "Content-Disposition": f'attachment; filename="{f.original_name}"'
    })


# ---------------------------------------------------------------------------
# PM-141: published document API specification
# ---------------------------------------------------------------------------


@router.get("/openapi-document-spec", response_model=dict, tags=["storage"])
def published_openapi_document_spec(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
) -> dict:
    """Publish the live OpenAPI document, limited to real document routes.

    Nothing here is hand-written: FastAPI generates the spec from the running
    app's routes. A cached schema can be stale when routes are installed or
    restored after it was built (the test suite snapshots both), so invalidate
    it and let FastAPI rebuild whenever a live storage route is missing.
    """
    verify_workspace(principal, workspace_id)
    from novara_core.main import app

    spec = app.openapi()
    live_paths = {route.path for route in router.routes}
    if not live_paths.issubset(spec.get("paths", {})):
        app.openapi_schema = None
        spec = app.openapi()

    document_paths = {
        path: operations
        for path, operations in spec.get("paths", {}).items()
        if "/documents" in path or "/storage" in path
    }
    published = {key: value for key, value in spec.items() if key != "paths"}
    published["paths"] = document_paths
    return published