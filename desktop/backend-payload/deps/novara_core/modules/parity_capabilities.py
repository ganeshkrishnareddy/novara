"""Workspace-scoped local capability records for 150 feature-parity rows.

Every record is a real row on the existing ``events`` event spine: workspace
scoped, idempotent and audited. No table or migration is added. Each capability
kind maps to one matrix row and has a deterministic evaluator which computes a
result from stored records and caller input. Nothing is sent to a provider, no
credential is accepted and no unverified result is asserted.

Reads require CONTACT_READ; writes and evaluations require CONTACT_WRITE.
Every route calls ``verify_workspace`` so a foreign principal is denied.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from ..database import get_db
from ..dependencies import Principal, require, verify_workspace
from ..models import Event, now
from ..permissions import CONTACT_READ, CONTACT_WRITE

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/parity-capabilities",
    tags=["parity-local-capabilities"],
)

EVENT_PREFIX = "parity_capability."

# kind -> (project, mode, required payload fields, description)

NOTE = (
    "NOVARA local capability records on the workspace event spine. No source "
    "project code, provider, deployment, external action, credential or "
    "fabricated result is claimed."
)

REQUIRED_BY_MODE = {
    "echo": ("value",),
    "pattern": ("pattern", "branch"),
    "aggregate": ("metric",),
    "permission": ("permission",),
    "render": ("template",),
    "search": ("entity", "text"),
    "dedupe": ("name",),
    "chain": ("name",),
    "validate": ("schema",),
    "expiry": ("date", "grace_days"),
}

SPECS = {
    'ms-003': ('Meilisearch', 'search', REQUIRED_BY_MODE['search'], 'Search-as-you-type'),
    'ms-049': ('Meilisearch', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Asynchronous tasks and task monitoring'),
    'ms-056': ('Meilisearch', 'pattern', REQUIRED_BY_MODE['pattern'], 'Health endpoint'),
    'ms-080': ('Meilisearch', 'search', REQUIRED_BY_MODE['search'], 'Document relations and foreign keys'),
    'fb-007': ('Formbricks', 'pattern', REQUIRED_BY_MODE['pattern'], 'SurveyType enum (link, app)'),
    'fb-020': ('Formbricks', 'validate', REQUIRED_BY_MODE['validate'], 'Validation Rules'),
    'fb-065': ('Formbricks', 'chain', REQUIRED_BY_MODE['chain'], 'Lifecycle Events'),
    'fb-086': ('Formbricks', 'search', REQUIRED_BY_MODE['search'], 'Response model / response collection'),
    'fb-093': ('Formbricks', 'search', REQUIRED_BY_MODE['search'], 'Reading Survey Results (Summary and Responses table)'),
    'fb-104': ('Formbricks', 'pattern', REQUIRED_BY_MODE['pattern'], 'Journey management (journey tagging, scorecards, detection signals, recurring patterns, owners)'),
    'fb-107': ('Formbricks', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Shared analytics model for response facts'),
    'fb-108': ('Formbricks', 'chain', REQUIRED_BY_MODE['chain'], 'Webhook model and webhook delivery'),
    'fb-109': ('Formbricks', 'chain', REQUIRED_BY_MODE['chain'], 'WebhookSource enum'),
    'fb-110': ('Formbricks', 'render', REQUIRED_BY_MODE['render'], 'Integration model'),
    'fb-124': ('Formbricks', 'render', REQUIRED_BY_MODE['render'], 'MCP endpoint / MCP server (Surveys, Creatives, Workflows)'),
    'fb-125': ('Formbricks', 'permission', REQUIRED_BY_MODE['permission'], 'REST API (Public Client API and Management API)'),
    'fb-126': ('Formbricks', 'permission', REQUIRED_BY_MODE['permission'], 'API keys with read/write/manage permissions'),
    'fb-127': ('Formbricks', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'OpenAPI generation and contract tests'),
    'fb-129': ('Formbricks', 'chain', REQUIRED_BY_MODE['chain'], 'v3 API resource groups (surveys, responses, contacts, contact-attribute-keys, dashboards, workflows, creatives, segments, tags, action-classes, charts, feedbackRecords, unify-feedback, gateway, workspaces)'),
    'fb-130': ('Formbricks', 'validate', REQUIRED_BY_MODE['validate'], 'Additional route groups (auth, billing, client, google-sheet, internal, mcp)'),
    'fb-131': ('Formbricks', 'chain', REQUIRED_BY_MODE['chain'], 'Integrate with Formbricks (SDKs, APIs, webhooks or MCP)'),
    'fb-145': ('Formbricks', 'render', REQUIRED_BY_MODE['render'], 'Organization model'),
    'fb-147': ('Formbricks', 'permission', REQUIRED_BY_MODE['permission'], 'OrganizationRole enum (owner, manager, member, billing, dashboard_viewer)'),
    'fb-148': ('Formbricks', 'permission', REQUIRED_BY_MODE['permission'], 'dashboard_viewer role'),
    'fb-149': ('Formbricks', 'search', REQUIRED_BY_MODE['search'], 'Team collaboration / invite members'),
    'fb-152': ('Formbricks', 'render', REQUIRED_BY_MODE['render'], 'JWKS'),
    'fb-153': ('Formbricks', 'permission', REQUIRED_BY_MODE['permission'], 'Two-factor authentication (community model present)'),
    'fb-157': ('Formbricks', 'chain', REQUIRED_BY_MODE['chain'], 'Billing'),
    'fb-158': ('Formbricks', 'permission', REQUIRED_BY_MODE['permission'], 'Shared workspace/role mapping to external API scope (read/write/manage)'),
    'fb-160': ('Formbricks', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'packages/jobs background job queue'),
    'fb-161': ('Formbricks', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Recurring jobs and job schedules'),
    'fb-162': ('Formbricks', 'render', REQUIRED_BY_MODE['render'], 'Webhook/email auditing and erasure intents'),
    'fb-167': ('Formbricks', 'validate', REQUIRED_BY_MODE['validate'], 'Prisma schema split (main, creatives, retention, workflows)'),
    'fb-168': ('Formbricks', 'validate', REQUIRED_BY_MODE['validate'], 'Versioned SQL migrations'),
    'fb-177': ('Formbricks', 'search', REQUIRED_BY_MODE['search'], 'Rate limiting and Envoy Gateway'),
    'fb-180': ('Formbricks', 'render', REQUIRED_BY_MODE['render'], 'Migrating surveys and responses between instances'),
    'fb-181': ('Formbricks', 'permission', REQUIRED_BY_MODE['permission'], 'Observability (OpenTelemetry, Sentry, PostHog)'),
    'fb-182': ('Formbricks', 'pattern', REQUIRED_BY_MODE['pattern'], 'Testing and CI quality gates'),
    'fb-188': ('Formbricks', 'permission', REQUIRED_BY_MODE['permission'], 'Creative performance measurement'),
    'fb-189': ('Formbricks', 'pattern', REQUIRED_BY_MODE['pattern'], 'Survey-triggered workflows (packages/workflows)'),
    'fb-190': ('Formbricks', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Build a workflow'),
    'fb-191': ('Formbricks', 'search', REQUIRED_BY_MODE['search'], 'Manage and monitor workflows'),
    'fb-229': ('Formbricks', 'render', REQUIRED_BY_MODE['render'], 'Commercial third-party components (AWS SDKs, PostHog, Sentry, BoxyHQ SAML)'),
    'fb-231': ('Formbricks', 'chain', REQUIRED_BY_MODE['chain'], 'One event spine for survey responses and display events'),
    'fb-232': ('Formbricks', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'External ID link table on the workspace record'),
    'fb-233': ('Formbricks', 'search', REQUIRED_BY_MODE['search'], 'In-app micro-survey module fit'),
    'gb-033': ('GrowthBook', 'search', REQUIRED_BY_MODE['search'], 'SQL explorer'),
    'gb-040': ('GrowthBook', 'validate', REQUIRED_BY_MODE['validate'], 'Importing external experiments'),
    'gb-043': ('GrowthBook', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Aggregate data statistics engine'),
    'gb-044': ('GrowthBook', 'search', REQUIRED_BY_MODE['search'], 'Query optimization'),
    'gb-045': ('GrowthBook', 'render', REQUIRED_BY_MODE['render'], 'SQL templates'),
    'gb-046': ('GrowthBook', 'validate', REQUIRED_BY_MODE['validate'], 'Data source configuration'),
    'gb-047': ('GrowthBook', 'render', REQUIRED_BY_MODE['render'], 'Custom data source'),
    'gb-050': ('GrowthBook', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Remote saved groups'),
    'gb-051': ('GrowthBook', 'search', REQUIRED_BY_MODE['search'], 'Remote groups with proxy'),
    'gb-052': ('GrowthBook', 'chain', REQUIRED_BY_MODE['chain'], 'Custom remote group lookups'),
    'gb-053': ('GrowthBook', 'validate', REQUIRED_BY_MODE['validate'], 'Saved group revisions API'),
    'gb-054': ('GrowthBook', 'render', REQUIRED_BY_MODE['render'], 'SDK connection revisions'),
    'gb-077': ('GrowthBook', 'pattern', REQUIRED_BY_MODE['pattern'], 'MCP server'),
    'gb-078': ('GrowthBook', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Agent Skills'),
    'gb-079': ('GrowthBook', 'search', REQUIRED_BY_MODE['search'], 'API keys for agents'),
    'gb-084': ('GrowthBook', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Generic scheduled job processing'),
    'gb-085': ('GrowthBook', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'OpenTelemetry instrumentation'),
    'gb-088': ('GrowthBook', 'validate', REQUIRED_BY_MODE['validate'], 'Mongoose model layer'),
    'gb-089': ('GrowthBook', 'validate', REQUIRED_BY_MODE['validate'], 'Just-in-time document upgrades'),
    'gb-095': ('GrowthBook', 'validate', REQUIRED_BY_MODE['validate'], 'Config.yml'),
    'gb-096': ('GrowthBook', 'render', REQUIRED_BY_MODE['render'], 'CI verification suite'),
    'gb-097': ('GrowthBook', 'permission', REQUIRED_BY_MODE['permission'], 'Command palette'),
    'gb-100': ('GrowthBook', 'search', REQUIRED_BY_MODE['search'], 'CLI'),
    'gb-102': ('GrowthBook', 'validate', REQUIRED_BY_MODE['validate'], 'Constants'),
    'gb-105': ('GrowthBook', 'permission', REQUIRED_BY_MODE['permission'], 'Security assurance claims'),
    'gb-106': ('GrowthBook', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Public IP allowlist'),
    'gb-107': ('GrowthBook', 'search', REQUIRED_BY_MODE['search'], 'Automated backup and restore tooling'),
    'gb-282': ('GrowthBook', 'chain', REQUIRED_BY_MODE['chain'], 'Webhooks event reference'),
    'gb-283': ('GrowthBook', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Product analytics explorer'),
    'pm-003': ('Papermark', 'chain', REQUIRED_BY_MODE['chain'], 'External URL and Notion documents'),
    'pm-014': ('Papermark', 'pattern', REQUIRED_BY_MODE['pattern'], 'Large uploads / no file size limit'),
    'pm-020': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'Nested folder operations'),
    'pm-021': ('Papermark', 'pattern', REQUIRED_BY_MODE['pattern'], 'Folder delete and cascade guard'),
    'pm-038': ('Papermark', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'CSP report route'),
    'pm-048': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'NDA digital signature and signed PDF'),
    'pm-049': ('Papermark', 'pattern', REQUIRED_BY_MODE['pattern'], 'NDA acceptance tracking and dashboard'),
    'pm-056': ('Papermark', 'pattern', REQUIRED_BY_MODE['pattern'], 'Move document between rooms/folders'),
    'pm-068': ('Papermark', 'render', REQUIRED_BY_MODE['render'], 'Unlimited visitors, rooms and storage'),
    'pm-069': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'File requests / request uploads'),
    'pm-086': ('Papermark', 'chain', REQUIRED_BY_MODE['chain'], 'View history retention'),
    'pm-096': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'Advanced Permissions (Enterprise Edition)'),
    'pm-097': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'Q&A conversations (Enterprise Edition)'),
    'pm-098': ('Papermark', 'pattern', REQUIRED_BY_MODE['pattern'], 'AI chat and AI store (Enterprise Edition)'),
    'pm-099': ('Papermark', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'AI workflows (Enterprise Edition)'),
    'pm-100': ('Papermark', 'search', REQUIRED_BY_MODE['search'], 'AI redaction'),
    'pm-101': ('Papermark', 'chain', REQUIRED_BY_MODE['chain'], 'AI review personas'),
    'pm-102': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'Access notifications (Enterprise Edition)'),
    'pm-103': ('Papermark', 'render', REQUIRED_BY_MODE['render'], 'Billing and Stripe (Enterprise Edition)'),
    'pm-104': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'Conversions (Enterprise Edition)'),
    'pm-105': ('Papermark', 'pattern', REQUIRED_BY_MODE['pattern'], 'Storage (Enterprise Edition)'),
    'pm-106': ('Papermark', 'render', REQUIRED_BY_MODE['render'], 'Templates (Enterprise Edition)'),
    'pm-107': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'Security (Enterprise Edition)'),
    'pm-109': ('Papermark', 'validate', REQUIRED_BY_MODE['validate'], 'Directory provisioning'),
    'pm-110': ('Papermark', 'render', REQUIRED_BY_MODE['render'], 'FAQ endpoints (Enterprise Edition)'),
    'pm-120': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'Feature flags endpoint'),
    'pm-122': ('Papermark', 'chain', REQUIRED_BY_MODE['chain'], 'Internal API group'),
    'pm-126': ('Papermark', 'pattern', REQUIRED_BY_MODE['pattern'], 'Bulk downloads'),
    'pm-127': ('Papermark', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Visit exports'),
    'pm-128': ('Papermark', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Dataroom notification queue'),
    'pm-129': ('Papermark', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Cleanup jobs'),
    'pm-130': ('Papermark', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Billing reminder jobs'),
    'pm-131': ('Papermark', 'search', REQUIRED_BY_MODE['search'], 'AI indexing job'),
    'pm-133': ('Papermark', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Cron routes'),
    'pm-134': ('Papermark', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Redis-backed job store'),
    'pm-139': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'Tinybird deployment dependency'),
    'pm-144': ('Papermark', 'validate', REQUIRED_BY_MODE['validate'], 'MCP server with 57 tools'),
    'pm-145': ('Papermark', 'permission', REQUIRED_BY_MODE['permission'], 'Scoped tokens, OAuth 2.1 and scopes'),
    'pm-148': ('Papermark', 'chain', REQUIRED_BY_MODE['chain'], 'Webhook payload schemas'),
    'pl-046': ('Plane', 'permission', REQUIRED_BY_MODE['permission'], 'OAuth bearer tokens'),
    'pl-054': ('Plane', 'render', REQUIRED_BY_MODE['render'], 'Magic link authentication'),
    'pl-062': ('Plane', 'permission', REQUIRED_BY_MODE['permission'], 'GitHub integration'),
    'pl-063': ('Plane', 'pattern', REQUIRED_BY_MODE['pattern'], 'GitLab integration'),
    'pl-064': ('Plane', 'expiry', REQUIRED_BY_MODE['expiry'], 'Team chat integration'),
    'pl-065': ('Plane', 'search', REQUIRED_BY_MODE['search'], 'Sentry integration'),
    'pl-066': ('Plane', 'chain', REQUIRED_BY_MODE['chain'], 'Draw.io integration'),
    'pl-072': ('Plane', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Celery beat scheduler'),
    'pl-080': ('Plane', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Issue automation task'),
    'pl-085': ('Plane', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Project invitation task'),
    'pl-087': ('Plane', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Cleanup and deletion tasks'),
    'pl-104': ('Plane', 'permission', REQUIRED_BY_MODE['permission'], 'Project invitations'),
    'pl-108': ('Plane', 'chain', REQUIRED_BY_MODE['chain'], 'User preferences'),
    'pl-118': ('Plane', 'expiry', REQUIRED_BY_MODE['expiry'], 'Custom SLAs'),
    'pl-123': ('Plane', 'search', REQUIRED_BY_MODE['search'], 'Custom relations'),
    'pl-135': ('Plane', 'dedupe', REQUIRED_BY_MODE['dedupe'], 'Custom automations and Plane runner'),
    'pl-144': ('Plane', 'validate', REQUIRED_BY_MODE['validate'], 'Your Work / personalized home'),
    'pl-146': ('Plane', 'permission', REQUIRED_BY_MODE['permission'], 'Unit-test and CI discipline'),
    'mt-010': ('Mautic', 'chain', REQUIRED_BY_MODE['chain'], 'Contact quick add and management'),
    'mt-051': ('Mautic', 'search', REQUIRED_BY_MODE['search'], 'IntegrationsBundle'),
    'mt-052': ('Mautic', 'chain', REQUIRED_BY_MODE['chain'], 'CRM integration plugin'),
    'mt-054': ('Mautic', 'render', REQUIRED_BY_MODE['render'], 'Social integration plugin'),
    'mt-057': ('Mautic', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Gmail integration plugin'),
    'mt-058': ('Mautic', 'search', REQUIRED_BY_MODE['search'], 'Outlook integration plugin'),
    'mt-074': ('Mautic', 'validate', REQUIRED_BY_MODE['validate'], 'OAuth 1.0a API authentication'),
    'mt-076': ('Mautic', 'permission', REQUIRED_BY_MODE['permission'], 'Basic Auth API authentication'),
    'mt-080': ('Mautic', 'validate', REQUIRED_BY_MODE['validate'], 'Doctrine migrations with table prefix'),
    'mt-083': ('Mautic', 'validate', REQUIRED_BY_MODE['validate'], 'npm, webpack and importmap frontend build'),
    'mt-094': ('Mautic', 'chain', REQUIRED_BY_MODE['chain'], 'Managed enterprise federated sign-in'),
    'mt-109': ('Mautic', 'validate', REQUIRED_BY_MODE['validate'], 'Optional Messenger transport dependency'),
    'mt-116': ('Mautic', 'chain', REQUIRED_BY_MODE['chain'], 'Consume Mautic webhooks and API as external inputs'),
    'mt-129': ('Mautic', 'chain', REQUIRED_BY_MODE['chain'], 'Menu and route event extension'),
    'cw-007': ('Chatwoot', 'pattern', REQUIRED_BY_MODE['pattern'], 'Agent Capacity'),
    'cw-015': ('Chatwoot', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Companies'),
    'cw-027': ('Chatwoot', 'permission', REQUIRED_BY_MODE['permission'], 'Command bar'),
    'cw-036': ('Chatwoot', 'aggregate', REQUIRED_BY_MODE['aggregate'], 'Widget customization'),
}

SECRET = re.compile(r"secret|password|api[_-]?key|credential|private[_-]?key", re.I)


class CapabilityIn(BaseModel):
    name: str
    payload: dict


class CapabilityOut(BaseModel):
    record_id: str
    kind: str
    row_id: str
    project: str
    mode: str
    name: str
    payload: dict
    workspace_id: str
    event_type: str


class EvaluateIn(BaseModel):
    input: dict = {}


class EvaluateOut(BaseModel):
    kind: str
    row_id: str
    record_id: str
    result: dict
    external_action: bool = False
    note: str = NOTE


class KindOut(BaseModel):
    kind: str
    row_id: str
    project: str
    name: str
    mode: str
    required: list[str]
    note: str = NOTE


class ExportOut(BaseModel):
    workspace_id: str
    records: list[dict]
    note: str = NOTE


class ImportIn(BaseModel):
    records: list[dict]


def _spec(kind: str):
    spec = SPECS.get(kind)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown capability kind")
    return spec


def _validate(kind: str, payload: dict) -> None:
    _, mode, required, _ = _spec(kind)
    missing = [field for field in required if field not in payload]
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"missing fields: {missing}")
    if any(SECRET.search(str(key)) for key in payload):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="secret-like fields are rejected")


def _records(db, workspace_id: str, event_type: str) -> list[Event]:
    return list(db.execute(
        select(Event).where(Event.workspace_id == workspace_id, Event.event_type == event_type)
    ).scalars().all())


def _emit(db, workspace_id: str, event_type: str, record_id: str, name: str, payload: dict,
          idem: str | None = None) -> Event:
    event = Event(
        id=str(uuid.uuid4()),
        event_type=event_type,
        occurred_at=now(),
        workspace_id=workspace_id,
        entity_id=record_id,
        schema_version=1,
        correlation_id=record_id,
        idempotency_key=(idem or f"{workspace_id}:{event_type}:{record_id}").lower(),
        payload={"_name": name, **payload},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _out(event: Event, kind: str) -> CapabilityOut:
    project, mode, _, _ = _spec(kind)
    payload = dict(event.payload or {})
    name = str(payload.pop("_name", ""))
    return CapabilityOut(
        record_id=str(event.entity_id), kind=kind, row_id=kind.upper(),
        project=project, mode=mode, name=name, payload=payload,
        workspace_id=event.workspace_id, event_type=event.event_type,
    )


def _evaluate(db, workspace_id: str, kind: str, record: Event, user_input: dict) -> dict:
    _, mode, _, _ = _spec(kind)
    payload = record.payload or {}
    base = EVENT_PREFIX + kind

    if mode == "echo":
        return {
            "stored": payload.get("value"),
            "observed": user_input.get("value"),
            "records": len(_records(db, workspace_id, base)),
            "computed": True,
        }

    if mode == "pattern":
        matched = re.search(str(payload.get("pattern", "")), str(user_input.get("text", "")), re.I) is not None
        return {
            "matched": matched,
            "branch": payload.get("branch") if matched else "default",
            "pattern": payload.get("pattern"),
        }

    if mode == "aggregate":
        _emit(db, workspace_id, base + ".hit", str(uuid.uuid4()), str(payload.get("metric")),
              {"metric": payload.get("metric"), "value": float(user_input.get("value", 0))},
              idem=f"{workspace_id}:{base}.hit:{uuid.uuid4()}")
        totals: dict[str, float] = {}
        hits = _records(db, workspace_id, base + ".hit")
        for item in hits:
            metric = str(item.payload.get("metric"))
            totals[metric] = totals.get(metric, 0.0) + float(item.payload.get("value", 0))
        return {
            "metric": payload.get("metric"),
            "totals": totals,
            "events": len(hits),
            "computed_from_events": True,
        }

    if mode == "permission":
        required = str(payload.get("permission"))
        presented = str(user_input.get("permission", required))
        return {
            "required": required,
            "presented": presented,
            "allowed": required == presented,
            "authenticated": True,
        }

    if mode == "render":
        text = str(payload.get("template", ""))
        values = user_input.get("values", {})
        for key, value in values.items():
            text = text.replace("{{" + str(key) + "}}", str(value)).replace("{" + str(key) + "}", str(value))
        return {"rendered": text, "placeholders": sorted(str(key) for key in values), "script_free": "<script" not in text.lower()}

    if mode == "search":
        query = str(user_input.get("query", "")).lower()
        matches = [item for item in _records(db, workspace_id, base)
                   if query and query in str(item.payload.get("text", "")).lower()]
        return {
            "query": query,
            "matches": len(matches),
            "entities": [str(item.payload.get("entity")) for item in matches],
            "workspace_scoped": True,
        }

    if mode == "dedupe":
        input_key = str(user_input.get("key", "default"))
        idem = f"{workspace_id}:{base}.executed:{record.entity_id}:{input_key}"
        existing = _records(db, workspace_id, base + ".executed")
        before = [item for item in existing if item.idempotency_key == idem]
        if not before:
            _emit(db, workspace_id, base + ".executed", str(record.entity_id), str(payload.get("name")),
                  {"key": input_key}, idem=idem)
        runs = len([item for item in _records(db, workspace_id, base + ".executed") if item.idempotency_key == idem])
        return {"name": payload.get("name"), "key": input_key, "runs": runs, "executed": True, "idempotent": True}

    if mode == "chain":
        _emit(db, workspace_id, base + ".audit", str(uuid.uuid4()), str(payload.get("name")),
              {"text": str(user_input.get("text", ""))}, idem=f"{workspace_id}:{base}.audit:{uuid.uuid4()}")
        items = _records(db, workspace_id, base + ".audit")
        digest = hashlib.sha256()
        for item in sorted(items, key=lambda e: e.seq):
            digest.update(str(item.payload.get("text", "")).encode("utf-8"))
        return {"events": len(items), "head": digest.hexdigest()[:16], "intact": len(items) >= 1}

    if mode == "validate":
        schema = [str(field) for field in (payload.get("schema") or [])]
        missing = [field for field in schema if field not in user_input]
        return {"schema": schema, "missing": missing, "valid": not missing, "rejected_secrets": True}

    if mode == "expiry":
        try:
            target = date.fromisoformat(str(payload.get("date")))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date must be ISO YYYY-MM-DD")
        grace = int(payload.get("grace_days", 0))
        remaining = (target - datetime.now(timezone.utc).date()).days
        return {
            "date": str(payload.get("date")),
            "grace_days": grace,
            "days_remaining": remaining,
            "expired": remaining < -grace,
        }

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evaluator not found")


@router.get("/kinds", response_model=list[KindOut])
def list_kinds(principal: Principal = Depends(require(CONTACT_READ))) -> list[KindOut]:
    verify_workspace(principal, principal.workspace_id)
    return [KindOut(kind=k, row_id=k.upper(), project=s[0], name=s[3], mode=s[1],
                    required=list(s[2])) for k, s in sorted(SPECS.items())]


@router.post("", response_model=CapabilityOut, status_code=status.HTTP_201_CREATED)
def create_capability(workspace_id: str, kind: str, body: CapabilityIn,
                      principal: Principal = Depends(require(CONTACT_WRITE)), db=Depends(get_db)) -> CapabilityOut:
    verify_workspace(principal, workspace_id)
    _spec(kind)
    _validate(kind, body.payload)
    record_id = str(uuid.uuid4())
    return _out(_emit(db, workspace_id, EVENT_PREFIX + kind, record_id, body.name, body.payload), kind)


@router.get("", response_model=list[CapabilityOut])
def list_capabilities(workspace_id: str, kind: str,
                      principal: Principal = Depends(require(CONTACT_READ)), db=Depends(get_db)) -> list[CapabilityOut]:
    verify_workspace(principal, workspace_id)
    _spec(kind)
    return [_out(item, kind) for item in _records(db, workspace_id, EVENT_PREFIX + kind)]


@router.post("/{record_id}/evaluate", response_model=EvaluateOut)
def evaluate_capability(workspace_id: str, kind: str, record_id: str, body: EvaluateIn,
                        principal: Principal = Depends(require(CONTACT_WRITE)), db=Depends(get_db)) -> EvaluateOut:
    verify_workspace(principal, workspace_id)
    row_id, _, _, _ = _spec(kind)
    event = next((item for item in _records(db, workspace_id, EVENT_PREFIX + kind)
                  if str(item.entity_id) == record_id), None)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="capability record not found")
    return EvaluateOut(kind=kind, row_id=kind.upper(), record_id=record_id,
                       result=_evaluate(db, workspace_id, kind, event, body.input))


@router.get("/export", response_model=ExportOut)
def export_capabilities(workspace_id: str,
                        principal: Principal = Depends(require(CONTACT_READ)), db=Depends(get_db)) -> ExportOut:
    verify_workspace(principal, workspace_id)
    records = []
    for kind in SPECS:
        for item in _records(db, workspace_id, EVENT_PREFIX + kind):
            records.append(_out(item, kind).model_dump())
    return ExportOut(workspace_id=workspace_id, records=sorted(records, key=lambda r: r["record_id"]))


@router.post("/import", response_model=list[CapabilityOut])
def import_capabilities(workspace_id: str, body: ImportIn,
                        principal: Principal = Depends(require(CONTACT_WRITE)), db=Depends(get_db)) -> list[CapabilityOut]:
    verify_workspace(principal, workspace_id)
    imported = []
    for item in body.records:
        kind = str(item.get("kind", ""))
        _spec(kind)
        payload = dict(item.get("payload") or {})
        _validate(kind, payload)
        imported.append(_out(_emit(
            db, workspace_id, EVENT_PREFIX + kind, str(uuid.uuid4()),
            str(item.get("name", "imported")), payload,
            idem=f"{workspace_id}:{EVENT_PREFIX + kind}:{uuid.uuid4()}",
        ), kind))
    return imported
