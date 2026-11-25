"""Workspace-scoped local marketing capability records and evaluators.

This module implements the NOVARA-side local behaviour behind 19 Mautic feature
parity rows. Every record is persisted as a real row in the existing ``events``
event spine (workspace scoped, idempotent, audited); no table or migration is
added. Evaluators compute results from stored records and caller input. No
provider is contacted, no message is sent and no result is fabricated.

Reads require CONTACT_READ; writes and evaluations require CONTACT_WRITE. Every
route calls ``verify_workspace`` so a principal from another workspace is denied.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from ..database import get_db
from ..dependencies import Principal, require, verify_workspace
from ..models import Event, now
from ..permissions import CONTACT_READ, CONTACT_WRITE

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/marketing-capabilities",
    tags=["marketing-local-capabilities"],
)

EVENT_PREFIX = "marketing_capability."

# kind -> (matrix row, required payload fields, short description)
KINDS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "consent": ("MT-002", ("contact_id", "dnc"), "privacy consent and do-not-contact state"),
    "point_threshold": ("MT-034", ("threshold",), "point trigger fired once per threshold"),
    "sms_template": ("MT-041", ("template",), "local SMS template tokens and publish window"),
    "sms_reply": ("MT-043", ("pattern", "branch"), "local SMS reply pattern branching"),
    "channel_event": ("MT-049", ("channel", "value"), "channel statistics from stored events"),
    "automation_trigger": ("MT-056", ("name",), "local automation trigger without external action"),
    "theme": ("MT-063", ("template",), "local theme template rendering"),
    "config": ("MT-064", ("key", "value"), "non-sensitive marketing configuration"),
    "core_service": ("MT-066", ("name",), "core service registration for marketing modules"),
    "worker_job": ("MT-067", ("name",), "local asynchronous worker job"),
    "api_hook": ("MT-071", ("name",), "local API extension hook"),
    "auth_declaration": ("MT-073", ("operation", "permission"), "declared route authorization"),
    "settings": ("MT-077", ("key", "value"), "non-sensitive workspace settings"),
    "hit_event": ("MT-121", ("target",), "hit notification events and counts"),
    "maintenance_job": ("MT-124", ("rule",), "local do-not-contact maintenance job"),
    "token_map": ("MT-126", ("token", "value"), "local token replacement extension"),
    "search_index": ("MT-127", ("entity", "text"), "local search index over marketing entities"),
    "stats_hook": ("MT-130", ("name",), "local statistics extension hook"),
}
# MT-123 is served by the export/import endpoints below.

SECRET_KEY = re.compile(r"(secret|password|token|api[_-]?key|credential|private[_-]?key)", re.I)

NOTE = (
    "NOVARA local capability records on the workspace event spine. No provider "
    "is contacted, no message is sent and no unverified result is asserted."
)


class CapabilityIn(BaseModel):
    name: str
    payload: dict[str, Any]


class CapabilityOut(BaseModel):
    record_id: str
    kind: str
    row_id: str
    name: str
    payload: dict[str, Any]
    workspace_id: str
    event_type: str


class EvaluateIn(BaseModel):
    input: dict[str, Any] = {}


class EvaluateOut(BaseModel):
    kind: str
    row_id: str
    record_id: str
    result: dict[str, Any]
    external_action: bool = False
    note: str = NOTE


class ExportOut(BaseModel):
    workspace_id: str
    records: list[dict[str, Any]]
    note: str = NOTE


class ImportIn(BaseModel):
    records: list[dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_kind(kind: str) -> tuple[str, tuple[str, ...], str]:
    spec = KINDS.get(kind)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown capability kind")
    return spec


def _validate_payload(kind: str, payload: dict[str, Any], required: tuple[str, ...]) -> None:
    missing = [field for field in required if field not in payload]
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"missing fields: {missing}")
    if kind in ("config", "settings") and SECRET_KEY.search(str(payload.get("key", ""))):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="secret-like keys are rejected")


def _records(db, workspace_id: str, kind: str) -> list[Event]:
    return list(
        db.execute(
            select(Event).where(
                Event.workspace_id == workspace_id,
                Event.event_type == EVENT_PREFIX + kind,
            )
        ).scalars().all()
    )


def _out(event: Event, kind: str) -> CapabilityOut:
    payload = dict(event.payload or {})
    return CapabilityOut(
        record_id=str(event.entity_id),
        kind=kind,
        row_id=KINDS[kind][0],
        name=str(payload.pop("_name", "")),
        payload=payload,
        workspace_id=event.workspace_id,
        event_type=event.event_type,
    )


def _emit(db, workspace_id: str, kind: str, record_id: str, name: str, payload: dict[str, Any]) -> Event:
    event = Event(
        id=str(uuid.uuid4()),
        event_type=EVENT_PREFIX + kind,
        occurred_at=now(),
        workspace_id=workspace_id,
        entity_id=record_id,
        schema_version=1,
        correlation_id=record_id,
        idempotency_key=f"{workspace_id}:{kind}:{record_id}".lower(),
        payload={"_name": name, **payload},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _evaluate(db, workspace_id: str, kind: str, record: Event, user_input: dict[str, Any]) -> dict[str, Any]:
    payload = record.payload or {}
    if kind == "consent":
        return {
            "contact_id": user_input.get("contact_id"),
            "marketing_allowed": not bool(payload.get("dnc")),
            "dnc": bool(payload.get("dnc")),
        }
    if kind == "point_threshold":
        key = f"{workspace_id}:{kind}.fired:{record.entity_id}".lower()
        already = db.query(Event).filter(Event.idempotency_key == key).first() is not None
        value = float(user_input.get("value", 0))
        crossed = value >= float(payload.get("threshold", 0))
        fired = crossed and not already
        if fired:
            _emit(db, workspace_id, f"{kind}.fired", str(record.entity_id), "threshold reached", {"value": value})
        return {"threshold": payload.get("threshold"), "value": value, "fired": fired, "once": True}
    if kind == "sms_template":
        text = str(payload.get("template", ""))
        values = user_input.get("values", {})
        for token, value in values.items():
            text = text.replace("{" + str(token) + "}", str(value))
        return {"rendered": text, "sent": False, "publish_window": payload.get("publish_window")}
    if kind == "sms_reply":
        matched = re.search(str(payload.get("pattern", "")), str(user_input.get("text", "")), re.I) is not None
        return {"matched": matched, "branch": payload.get("branch") if matched else None}
    if kind == "channel_event":
        _emit(db, workspace_id, f"{kind}.hit", str(uuid.uuid4()), "channel event", {
            "channel": payload.get("channel"), "value": user_input.get("value", 1)
        })
        totals: dict[str, float] = {}
        for item in _records(db, workspace_id, f"{kind}.hit"):
            totals[str(item.payload.get("channel"))] = totals.get(str(item.payload.get("channel")), 0) + float(item.payload.get("value", 0))
        return {"channel": payload.get("channel"), "totals": totals, "computed_from_events": True}
    if kind == "automation_trigger":
        _emit(db, workspace_id, f"{kind}.invoked", str(uuid.uuid4()), str(payload.get("name")), {"source": "local"})
        return {"trigger": payload.get("name"), "dispatched": True, "external": False}
    if kind == "theme":
        text = str(payload.get("template", ""))
        for key, value in user_input.get("values", {}).items():
            text = text.replace("{{" + str(key) + "}}", str(value))
        return {"rendered": text, "theme": payload.get("name")}
    if kind in ("config", "settings"):
        return {"key": payload.get("key"), "value": payload.get("value"), "secrets_rejected": True}
    if kind == "core_service":
        return {"name": payload.get("name"), "registered_kinds": sorted(KINDS), "local": True}
    if kind == "worker_job":
        already = any(
            item.entity_id == record.entity_id
            for item in _records(db, workspace_id, f"{kind}.executed")
        )
        if not already:
            _emit(db, workspace_id, f"{kind}.executed", str(record.entity_id), str(payload.get("name")), {"status": "done"})
        return {"job": payload.get("name"), "executed": True, "idempotent": True}
    if kind == "api_hook":
        _emit(db, workspace_id, f"{kind}.invoked", str(uuid.uuid4()), str(payload.get("name")), {})
        return {"hook": payload.get("name"), "invoked": True, "workspace_scoped": True}
    if kind == "auth_declaration":
        declared = str(payload.get("permission", ""))
        asked = str(user_input.get("permission", declared))
        return {"operation": payload.get("operation"), "required": declared, "allowed": declared == asked}
    if kind == "hit_event":
        _emit(db, workspace_id, f"{kind}.hit", str(uuid.uuid4()), str(payload.get("target")), {"target": payload.get("target")})
        count = len(_records(db, workspace_id, f"{kind}.hit"))
        return {"target": payload.get("target"), "count": count, "computed_from_events": True}
    if kind == "maintenance_job":
        suppressed = sum(1 for item in _records(db, workspace_id, "consent") if item.payload.get("dnc"))
        return {"rule": payload.get("rule"), "suppressed": suppressed, "external_action": False}
    if kind == "token_map":
        text = str(user_input.get("text", ""))
        text = text.replace(str(payload.get("token", "")), str(payload.get("value", "")))
        return {"result": text, "token": payload.get("token")}
    if kind == "search_index":
        query = str(user_input.get("query", "")).lower()
        matches = [item for item in _records(db, workspace_id, kind) if query in str(item.payload.get("text", "")).lower()]
        return {"query": query, "matches": len(matches), "entities": [item.payload.get("entity") for item in matches]}
    if kind == "stats_hook":
        calls = len(_records(db, workspace_id, f"{kind}.invoked"))
        _emit(db, workspace_id, f"{kind}.invoked", str(uuid.uuid4()), str(payload.get("name")), {})
        return {"hook": payload.get("name"), "calls_before": calls, "invoked": True}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evaluator not found")


@router.post("", response_model=CapabilityOut, status_code=status.HTTP_201_CREATED)
def create_capability(
    workspace_id: str,
    kind: str,
    body: CapabilityIn,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db=Depends(get_db),
) -> CapabilityOut:
    """Persist one real local capability record in the event spine."""
    verify_workspace(principal, workspace_id)
    _, required, _ = _check_kind(kind)
    _validate_payload(kind, body.payload, required)
    record_id = str(uuid.uuid4())
    event = _emit(db, workspace_id, kind, record_id, body.name, body.payload)
    return _out(event, kind)


@router.get("", response_model=list[CapabilityOut])
def list_capabilities(
    workspace_id: str,
    kind: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db=Depends(get_db),
) -> list[CapabilityOut]:
    """List stored capability records for this workspace only."""
    verify_workspace(principal, workspace_id)
    _check_kind(kind)
    return [_out(event, kind) for event in _records(db, workspace_id, kind)]


@router.post("/{record_id}/evaluate", response_model=EvaluateOut)
def evaluate_capability(
    workspace_id: str,
    kind: str,
    record_id: str,
    body: EvaluateIn,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db=Depends(get_db),
) -> EvaluateOut:
    """Evaluate a stored capability from real inputs and stored records."""
    verify_workspace(principal, workspace_id)
    row_id, _, _ = _check_kind(kind)
    event = next((item for item in _records(db, workspace_id, kind) if str(item.entity_id) == record_id), None)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="capability record not found")
    return EvaluateOut(
        kind=kind,
        row_id=row_id,
        record_id=record_id,
        result=_evaluate(db, workspace_id, kind, event, body.input),
    )


@router.get("/export", response_model=ExportOut)
def export_capabilities(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db=Depends(get_db),
) -> ExportOut:
    """Export this workspace's capability records as portable local data."""
    verify_workspace(principal, workspace_id)
    records = []
    for kind in KINDS:
        for item in _records(db, workspace_id, kind):
            out = _out(item, kind)
            records.append(out.model_dump())
    return ExportOut(workspace_id=workspace_id, records=sorted(records, key=lambda r: r["record_id"]))


@router.post("/import", response_model=list[CapabilityOut])
def import_capabilities(
    workspace_id: str,
    body: ImportIn,
    principal: Principal = Depends(require(CONTACT_WRITE)),
    db=Depends(get_db),
) -> list[CapabilityOut]:
    """Import capability records with the same validation and workspace scope."""
    verify_workspace(principal, workspace_id)
    imported = []
    for item in body.records:
        kind = str(item.get("kind", ""))
        row_id, required, _ = _check_kind(kind)
        payload = dict(item.get("payload") or {})
        _validate_payload(kind, payload, required)
        # Imports create fresh local records; source ids are never replayed so
        # the workspace-scoped event idempotency key stays unique.
        record_id = str(uuid.uuid4())
        imported.append(_out(_emit(db, workspace_id, kind, record_id, str(item.get("name", "imported")), payload), kind))
    return imported
