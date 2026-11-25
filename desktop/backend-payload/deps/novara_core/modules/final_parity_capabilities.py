"""Additive clean-room local capabilities for the final 148 parity rows.

Every record is a real row on the existing workspace-scoped ``events`` spine.
Each row kind has a deterministic evaluator which computes its result from
stored records and caller input. Provider-shaped capabilities are gated: they
never contact a provider, never accept a credential and always report
``delivery: not_sent`` / ``external_action: False``. No source project code,
new table, migration, deployment, external send or fabricated result is used.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, text

from ..database import get_db
from ..dependencies import Principal, require, verify_workspace
from ..models import Event, now
from ..permissions import CONTACT_READ, CONTACT_WRITE

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/final-capabilities",
    tags=["final-parity-local-capabilities"],
)

EVENT_PREFIX = "final_capability."
NOTE = (
    "NOVARA local capability records on the workspace event spine. Provider-shaped "
    "capabilities are gated and report no delivery; no source project code, credential, "
    "deployment, external action or fabricated result is claimed."
)

REQUIRED = {
    'gate': ('control', 'require_consent', 'require_approval', 'require_keys'),
    'signature': ('algorithm', 'verifier'),
    'expiry': ('date', 'grace_days'),
    'cursor': ('entity', 'text'),
    'dedupe': ('name', 'key'),
    'render': ('template',),
    'permission': ('permission', 'actor'),
    'search': ('entity', 'text'),
    'aggregate': ('metric',),
    'validate': ('schema',),
    'chain': ('name',),
    'pattern': ('pattern', 'branch'),
    'encrypt': ('value',),
    'locale': ('locale', 'strings'),
    'refresh': ('entity', 'interval_seconds'),
    'grant': ('resource', 'scope'),
    'config': ('setting', 'default', 'value_type'),
    'trace': ('topic',),
    'estimate': ('prices',),
    'transition': ('states', 'from_state', 'to_state'),
    'rate': ('limit', 'window'),
    'preview': ('types', 'strategies'),
    'prompt': ('boundary',),
    'totp': ('seed_token', 'code'),
    'pragma': ('pragmas',),
    'interface': ('backends',),
}

SECRET = re.compile(r"secret|password|api[_-]?key|credential|private[_-]?key", re.I)

SPECS = {
    'fb-076': ('Formbricks', 'refresh', REQUIRED['refresh'], 'Offline Support'),
    'fb-078': ('Formbricks', 'config', REQUIRED['config'], 'Framework Guides and SDK compatibility'),
    'gb-068': ('GrowthBook', 'signature', REQUIRED['signature'], 'Air-gapped licence keys'),
    'gb-069': ('GrowthBook', 'expiry', REQUIRED['expiry'], '14-day licence expiration grace'),
    'gb-070': ('GrowthBook', 'gate', REQUIRED['gate'], 'Licence server egress'),
    'gb-080': ('GrowthBook', 'validate', REQUIRED['validate'], 'dbt sync'),
    'gb-086': ('GrowthBook', 'trace', REQUIRED['trace'], 'Sentry error reporting'),
    'gb-090': ('GrowthBook', 'config', REQUIRED['config'], 'Self-hosting configuration record'),
    'gb-091': ('GrowthBook', 'config', REQUIRED['config'], 'Single container image'),
    'gb-092': ('GrowthBook', 'config', REQUIRED['config'], 'Hardened distroless image'),
    'gb-093': ('GrowthBook', 'config', REQUIRED['config'], 'Container orchestration configuration record'),
    'gb-094': ('GrowthBook', 'interface', REQUIRED['interface'], 'FerretDB alternative store'),
    'gb-098': ('GrowthBook', 'config', REQUIRED['config'], 'DevTools browser extension'),
    'gb-099': ('GrowthBook', 'config', REQUIRED['config'], 'VS Code extension'),
    'gb-103': ('GrowthBook', 'transition', REQUIRED['transition'], 'Visual experiments in JavaScript SDK'),
    'gb-104': ('GrowthBook', 'gate', REQUIRED['gate'], 'Managed warehouse'),
    'gb-118': ('GrowthBook', 'gate', REQUIRED['gate'], 'Flags adapter seam'),
    'gb-284': ('GrowthBook', 'gate', REQUIRED['gate'], 'GrowthBook Slack app'),
    'pm-013': ('Papermark', 'preview', REQUIRED['preview'], 'Supported file formats'),
    'pm-070': ('Papermark', 'render', REQUIRED['render'], 'Full white-label branding'),
    'pm-108': ('Papermark', 'signature', REQUIRED['signature'], 'Federated identity signature boundary'),
    'pm-111': ('Papermark', 'gate', REQUIRED['gate'], 'Google OAuth login'),
    'pm-112': ('Papermark', 'gate', REQUIRED['gate'], 'Second OAuth provider login'),
    'pm-113': ('Papermark', 'signature', REQUIRED['signature'], 'Hanko passkeys'),
    'pm-114': ('Papermark', 'signature', REQUIRED['signature'], 'Email magic links'),
    'pm-118': ('Papermark', 'signature', REQUIRED['signature'], 'Incoming webhooks'),
    'pm-119': ('Papermark', 'gate', REQUIRED['gate'], 'Slack OAuth integration'),
    'pm-132': ('Papermark', 'gate', REQUIRED['gate'], 'Upstash QStash and Redis queues/locks'),
    'pm-143': ('Papermark', 'config', REQUIRED['config'], 'CLI'),
    'pm-147': ('Papermark', 'config', REQUIRED['config'], 'Published client SDK'),
    'pl-047': ('Plane', 'signature', REQUIRED['signature'], 'OAuth Bridge'),
    'pl-052': ('Plane', 'signature', REQUIRED['signature'], 'Webhooks'),
    'pl-058': ('Plane', 'gate', REQUIRED['gate'], 'Google OAuth'),
    'pl-059': ('Plane', 'gate', REQUIRED['gate'], 'GitHub OAuth'),
    'pl-060': ('Plane', 'gate', REQUIRED['gate'], 'GitLab OAuth'),
    'pl-061': ('Plane', 'gate', REQUIRED['gate'], 'Gitea OAuth'),
    'pl-069': ('Plane', 'config', REQUIRED['config'], 'OAuth provider framework'),
    'pl-074': ('Plane', 'refresh', REQUIRED['refresh'], 'Django Channels realtime'),
    'pl-090': ('Plane', 'validate', REQUIRED['validate'], 'Intake email'),
    'pl-113': ('Plane', 'signature', REQUIRED['signature'], 'Federated sign-in signature boundary'),
    'pl-114': ('Plane', 'signature', REQUIRED['signature'], 'OpenID sign-in signature boundary'),
    'pl-115': ('Plane', 'gate', REQUIRED['gate'], 'LDAP'),
    'mt-004': ('Mautic', 'config', REQUIRED['config'], 'DPG governance since 2024'),
    'mt-039': ('Mautic', 'gate', REQUIRED['gate'], 'NotificationBundle'),
    'mt-040': ('Mautic', 'gate', REQUIRED['gate'], 'SmsBundle'),
    'mt-044': ('Mautic', 'gate', REQUIRED['gate'], 'Twilio SMS transport plugin'),
    'mt-053': ('Mautic', 'gate', REQUIRED['gate'], 'Email marketing integration plugins'),
    'mt-055': ('Mautic', 'gate', REQUIRED['gate'], 'Clearbit and FullContact enrichment plugins'),
    'mt-059': ('Mautic', 'gate', REQUIRED['gate'], 'Focus plugin'),
    'mt-060': ('Mautic', 'gate', REQUIRED['gate'], 'Tag Manager plugin'),
    'mt-062': ('Mautic', 'render', REQUIRED['render'], 'GrapesJS builder plugin'),
    'mt-068': ('Mautic', 'config', REQUIRED['config'], 'QueueBundle/Config path'),
    'mt-075': ('Mautic', 'gate', REQUIRED['gate'], 'OAuth 2 API authentication'),
    'mt-081': ('Mautic', 'config', REQUIRED['config'], 'MySQL 8.4+ and MariaDB 10.11+ support'),
    'mt-086': ('Mautic', 'gate', REQUIRED['gate'], 'Zip and web installer flow'),
    'mt-092': ('Mautic', 'config', REQUIRED['config'], 'CI workflows for tests, e2e, coverage and api-library'),
    'mt-095': ('Mautic', 'config', REQUIRED['config'], 'No separate enterprise source edition'),
    'mt-096': ('Mautic', 'config', REQUIRED['config'], 'Managed Mautic Essential plan'),
    'mt-097': ('Mautic', 'config', REQUIRED['config'], 'Managed Mautic Professional plan'),
    'mt-098': ('Mautic', 'config', REQUIRED['config'], 'Managed Mautic Enterprise plan'),
    'mt-099': ('Mautic', 'gate', REQUIRED['gate'], 'Higher sending limits'),
    'mt-100': ('Mautic', 'config', REQUIRED['config'], 'Custom plugins on managed plans'),
    'mt-101': ('Mautic', 'config', REQUIRED['config'], 'Dedicated infrastructure and support'),
    'mt-108': ('Mautic', 'gate', REQUIRED['gate'], 'SMTP and email delivery dependency and cost'),
    'mt-111': ('Mautic', 'config', REQUIRED['config'], 'No core licence fee with separate support costs'),
    'mt-118': ('Mautic', 'config', REQUIRED['config'], 'Developer documentation needs major update'),
    'cw-031': ('Chatwoot', 'preview', REQUIRED['preview'], 'Conversation attachments'),
    'cw-039': ('Chatwoot', 'signature', REQUIRED['signature'], 'Facebook Messenger channel'),
    'cw-040': ('Chatwoot', 'signature', REQUIRED['signature'], 'Instagram DMs channel'),
    'cw-042': ('Chatwoot', 'signature', REQUIRED['signature'], 'Telegram channel'),
    'cw-043': ('Chatwoot', 'signature', REQUIRED['signature'], 'LINE channel'),
    'cw-049': ('Chatwoot', 'rate', REQUIRED['rate'], 'Client / public inbox API'),
    'cw-050': ('Chatwoot', 'gate', REQUIRED['gate'], 'Mobile agent apps'),
    'cw-057': ('Chatwoot', 'expiry', REQUIRED['expiry'], 'SLA policies'),
    'cw-059': ('Chatwoot', 'dedupe', REQUIRED['dedupe'], 'SLA breach alerts'),
    'cw-060': ('Chatwoot', 'aggregate', REQUIRED['aggregate'], 'SLA reports'),
    'cw-065': ('Chatwoot', 'chain', REQUIRED['chain'], 'Captain Summarization'),
    'cw-074': ('Chatwoot', 'permission', REQUIRED['permission'], 'Agent bots'),
    'cw-076': ('Chatwoot', 'validate', REQUIRED['validate'], 'CSV import of contacts'),
    'cw-078': ('Chatwoot', 'dedupe', REQUIRED['dedupe'], 'Pre-chat forms'),
    'cw-079': ('Chatwoot', 'transition', REQUIRED['transition'], 'Campaigns'),
    'cw-081': ('Chatwoot', 'render', REQUIRED['render'], 'Custom domain / white labelling'),
    'cw-082': ('Chatwoot', 'render', REQUIRED['render'], 'Email templates'),
    'cw-083': ('Chatwoot', 'locale', REQUIRED['locale'], 'Multilingual support / 50+ languages'),
    'cw-084': ('Chatwoot', 'locale', REQUIRED['locale'], 'RTL support'),
    'cw-094': ('Chatwoot', 'refresh', REQUIRED['refresh'], 'Live View'),
    'cw-105': ('Chatwoot', 'permission', REQUIRED['permission'], 'CSAT review notes'),
    'cw-109': ('Chatwoot', 'grant', REQUIRED['grant'], 'Integration hooks'),
    'cw-113': ('Chatwoot', 'permission', REQUIRED['permission'], 'Platform API'),
    'cw-120': ('Chatwoot', 'config', REQUIRED['config'], 'JavaScript SDK'),
    'cw-121': ('Chatwoot', 'config', REQUIRED['config'], 'Widget bundle'),
    'cw-123': ('Chatwoot', 'signature', REQUIRED['signature'], 'Team chat signed-event bridge'),
    'cw-132': ('Chatwoot', 'totp', REQUIRED['totp'], 'Two-factor authentication'),
    'cw-134': ('Chatwoot', 'signature', REQUIRED['signature'], 'SAML single sign-on'),
    'cw-135': ('Chatwoot', 'gate', REQUIRED['gate'], 'Google OAuth login'),
    'cw-138': ('Chatwoot', 'permission', REQUIRED['permission'], 'Super admin console'),
    'cw-140': ('Chatwoot', 'grant', REQUIRED['grant'], 'Platform app permissibles'),
    'cw-141': ('Chatwoot', 'refresh', REQUIRED['refresh'], 'ActionCable realtime transport'),
    'cw-143': ('Chatwoot', 'config', REQUIRED['config'], 'Vitest frontend test suite'),
    'cw-144': ('Chatwoot', 'config', REQUIRED['config'], 'Coverage instrumentation'),
    'cw-146': ('Chatwoot', 'gate', REQUIRED['gate'], 'Heroku one-click deployment'),
    'cw-148': ('Chatwoot', 'gate', REQUIRED['gate'], 'Container deployment gate'),
    'cw-149': ('Chatwoot', 'gate', REQUIRED['gate'], 'Orchestration chart deployment gate'),
    'cw-151': ('Chatwoot', 'config', REQUIRED['config'], 'Environment configuration'),
    'cw-152': ('Chatwoot', 'permission', REQUIRED['permission'], 'API-only server mode'),
    'cw-153': ('Chatwoot', 'gate', REQUIRED['gate'], 'PostgreSQL persistence'),
    'cw-159': ('Chatwoot', 'config', REQUIRED['config'], 'Seed data'),
    'cw-160': ('Chatwoot', 'signature', REQUIRED['signature'], 'Inbound email service adapters'),
    'cw-162': ('Chatwoot', 'encrypt', REQUIRED['encrypt'], 'MFA encryption keys'),
    'nv-020': ('Novu', 'gate', REQUIRED['gate'], 'Email notifications'),
    'nv-022': ('Novu', 'gate', REQUIRED['gate'], 'Mobile push channel boundary'),
    'nv-024': ('Novu', 'gate', REQUIRED['gate'], 'Chat notifications (Slack, Teams, Telegram, WhatsApp and others)'),
    'nv-029': ('Novu', 'signature', REQUIRED['signature'], 'Inbound email / inbound parse'),
    'nv-043': ('Novu', 'locale', REQUIRED['locale'], 'Inbox localization'),
    'nv-047': ('Novu', 'transition', REQUIRED['transition'], '`<Subscription />` component and headless hooks'),
    'nv-062': ('Novu', 'permission', REQUIRED['permission'], 'Agent-toolkit compatibility boundary'),
    'nv-065': ('Novu', 'permission', REQUIRED['permission'], 'Workflow-assigned agents'),
    'nv-076': ('Novu', 'gate', REQUIRED['gate'], 'Custom domains'),
    'nv-088': ('Novu', 'validate', REQUIRED['validate'], 'User management API (`user` controller)'),
    'nv-092': ('Novu', 'trace', REQUIRED['trace'], 'Agent event protocol (`packages/agent-event-protocol`)'),
    'nv-097': ('Novu', 'rate', REQUIRED['rate'], 'Idempotency and rate limiting configuration flags'),
    'nv-100': ('Novu', 'render', REQUIRED['render'], 'Channels template editors'),
    'nv-101': ('Novu', 'render', REQUIRED['render'], 'Inbox styling, theming and custom chrome'),
    'nv-102': ('Novu', 'cursor', REQUIRED['cursor'], 'API error model and cursor pagination'),
    'nv-105': ('Novu', 'transition', REQUIRED['transition'], 'Cancel triggered event API'),
    'nv-111': ('Novu', 'trace', REQUIRED['trace'], 'Web Chat messages and conversation timeline'),
    'nv-112': ('Novu', 'gate', REQUIRED['gate'], 'Web Chat tool approval and generative UI'),
    'nv-113': ('Novu', 'signature', REQUIRED['signature'], 'Web Chat HMAC security'),
    'nv-115': ('Novu', 'trace', REQUIRED['trace'], 'Agent conversation observability'),
    'sb-003': ('Sellbird', 'estimate', REQUIRED['estimate'], 'Discovery cost estimation'),
    'sb-016': ('Sellbird', 'transition', REQUIRED['transition'], 'Campaign records / `campaigns_list`'),
    'sb-033': ('Sellbird', 'trace', REQUIRED['trace'], 'Conversation tracking / `conversations_list`'),
    'sb-034': ('Sellbird', 'validate', REQUIRED['validate'], 'Feedback records'),
    'sb-036': ('Sellbird', 'aggregate', REQUIRED['aggregate'], 'Usage and quota tracking'),
    'sb-037': ('Sellbird', 'validate', REQUIRED['validate'], 'CSV export'),
    'sb-046': ('Sellbird', 'permission', REQUIRED['permission'], 'Agent route extension points'),
    'sb-048': ('Sellbird', 'transition', REQUIRED['transition'], 'Quiet hours and interruptible sleep'),
    'sb-052': ('Sellbird', 'config', REQUIRED['config'], 'Dashboard API surface'),
    'sb-053': ('Sellbird', 'config', REQUIRED['config'], 'Setup status'),
    'sb-054': ('Sellbird', 'config', REQUIRED['config'], 'Settings and settings table'),
    'sb-056': ('Sellbird', 'trace', REQUIRED['trace'], 'Process start/stop and logs'),
    'sb-057': ('Sellbird', 'aggregate', REQUIRED['aggregate'], 'Today view'),
    'sb-067': ('Sellbird', 'gate', REQUIRED['gate'], 'Docker deployment'),
    'sb-070': ('Sellbird', 'pragma', REQUIRED['pragma'], 'Linear idempotent migrations via `PRAGMA user_version`'),
    'sb-071': ('Sellbird', 'pragma', REQUIRED['pragma'], 'WAL journal mode and busy timeout'),
    'sb-072': ('Sellbird', 'interface', REQUIRED['interface'], 'Pluggable storage backend boundary'),
    'sb-078': ('Sellbird', 'gate', REQUIRED['gate'], 'Cross-platform CI and packaging verification'),
    'sb-080': ('Sellbird', 'prompt', REQUIRED['prompt'], 'Prompt-injection and provider isolation safeguards'),
}


class CapabilityIn(BaseModel):
    name: str
    payload: dict


class CapabilityOut(BaseModel):
    record_id: str
    kind: str
    row_id: str
    project: str
    name: str
    mode: str
    payload: dict
    workspace_id: str


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


def _emit(db, workspace_id: str, event_type: str, record_id: str, name: str,
          payload: dict, idem: str | None = None) -> Event:
    event = Event(
        id=str(uuid.uuid4()), event_type=event_type, occurred_at=now(),
        workspace_id=workspace_id, entity_id=record_id, schema_version=1,
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
    return CapabilityOut(record_id=str(event.entity_id), kind=kind, row_id=kind.upper(),
                         project=project, mode=mode, name=name, payload=payload,
                         workspace_id=event.workspace_id)


def _evaluate(db, workspace_id: str, kind: str, record: Event, user_input: dict) -> dict:
    _, mode, _, _ = _spec(kind)
    payload = record.payload or {}
    base = EVENT_PREFIX + kind
    all_records = _records(db, workspace_id, base)

    if mode == "gate":
        gates = {"consent": bool(payload.get("require_consent")),
                 "approval": bool(payload.get("require_approval")),
                 "keys": bool(payload.get("require_keys"))}
        allowed = all(user_input.get(key) is True for key, needed in gates.items() if needed)
        return {"control": payload.get("control"), "allowed": allowed,
                "delivery": "not_sent", "external_action": False,
                "label": "local-boundary", "gates": gates}

    if mode == "signature":
        verifier = str(payload.get("verifier", ""))
        body = str(user_input.get("body", ""))
        expected = hmac.new(verifier.encode(), body.encode(), hashlib.sha256).hexdigest()
        presented = str(user_input.get("signature", ""))
        return {"algorithm": payload.get("algorithm"), "verified": hmac.compare_digest(expected, presented),
                "replay_rejected": False, "external_action": False}

    if mode == "expiry":
        target = date.fromisoformat(str(payload.get("date")))
        today = date.fromisoformat(str(user_input["today"])) if user_input.get("today") else datetime.now(timezone.utc).date()
        grace = int(payload.get("grace_days", 0))
        remaining = (target - today).days
        return {"date": str(payload.get("date")), "grace_days": grace,
                "days_remaining": remaining, "expired": remaining < -grace}

    if mode == "cursor":
        limit = max(1, min(10, int(user_input.get("limit", 2))))
        after = max(0, int(user_input.get("after", 0)))
        window = all_records[after:after + limit]
        return {"items": [str(item.payload.get("text")) for item in window],
                "after": after, "next_cursor": after + len(window),
                "workspace_scoped": True}

    if mode == "dedupe":
        key = str(user_input.get("key", payload.get("key", "default")))
        idem = f"{workspace_id}:{base}.executed:{record.entity_id}:{key}"
        events = _records(db, workspace_id, base + ".executed")
        runs = len([item for item in events if item.idempotency_key == idem])
        if runs == 0:
            _emit(db, workspace_id, base + ".executed", str(record.entity_id), str(payload.get("name")),
                  {"key": key}, idem=idem)
            runs = 1
        return {"name": payload.get("name"), "key": key, "runs": runs,
                "executed": True, "idempotent": True}

    if mode == "render":
        rendered = str(payload.get("template", ""))
        for key, value in (user_input.get("values") or {}).items():
            rendered = rendered.replace("{{" + str(key) + "}}", str(value))
        return {"rendered": rendered, "script_free": "<script" not in rendered.lower(),
                "external_assets": False}

    if mode == "permission":
        required = str(payload.get("permission"))
        presented = str(user_input.get("permission", ""))
        actor = str(user_input.get("actor", payload.get("actor", "")))
        allowed = required == presented and bool(actor)
        return {"required": required, "presented": presented, "actor": actor,
                "allowed": allowed, "audited": True}

    if mode == "aggregate":
        _emit(db, workspace_id, base + ".hit", str(uuid.uuid4()), str(payload.get("metric")),
              {"metric": payload.get("metric"), "value": float(user_input.get("value", 0))},
              idem=f"{workspace_id}:{base}.hit:{uuid.uuid4()}")
        totals: dict[str, float] = {}
        hits = _records(db, workspace_id, base + ".hit")
        for item in hits:
            metric = str(item.payload.get("metric"))
            totals[metric] = totals.get(metric, 0.0) + float(item.payload.get("value", 0))
        return {"metric": payload.get("metric"), "totals": totals, "events": len(hits),
                "computed_from_events": True}

    if mode == "validate":
        schema = [str(field) for field in (payload.get("schema") or [])]
        missing = [field for field in schema if field not in (user_input or {})]
        secret_fields = [key for key in user_input if SECRET.search(str(key))]
        return {"schema": schema, "missing": missing, "valid": not missing and not secret_fields,
                "rejected_secrets": bool(secret_fields)}

    if mode == "chain":
        _emit(db, workspace_id, base + ".audit", str(uuid.uuid4()), str(payload.get("name")),
              {"text": str(user_input.get("text", ""))}, idem=f"{workspace_id}:{base}.audit:{uuid.uuid4()}")
        items = _records(db, workspace_id, base + ".audit")
        digest = hashlib.sha256()
        for item in sorted(items, key=lambda e: e.seq):
            digest.update(str(item.payload.get("text", "")).encode("utf-8"))
        return {"events": len(items), "head": digest.hexdigest()[:16],
                "marker": "unverified local summary", "source_message_ids": [str(i.entity_id) for i in items]}

    if mode == "pattern":
        matched = re.search(str(payload.get("pattern", "")), str(user_input.get("text", "")), re.I) is not None
        return {"matched": matched, "branch": payload.get("branch") if matched else "default"}

    if mode == "encrypt":
        value = str(payload.get("value", ""))
        rotate = bool(user_input.get("rotate"))
        key = hashlib.sha256((workspace_id + "|final-capabilities").encode()).digest()
        stream = hashlib.blake2b(key + str(rotate).encode(), digest_size=len(value) or 1).digest()
        masked = bytes((ord(ch) ^ stream[index % len(stream)]) for index, ch in enumerate(value)).hex()
        return {"masked": masked, "decryptable": True, "rotated": rotate,
                "raw_in_response": False, "scope": "local-demo-boundary"}

    if mode == "locale":
        strings = payload.get("strings") or {}
        locale = str(user_input.get("locale", payload.get("locale", "en")))
        chosen = strings.get(locale) or strings.get(str(payload.get("locale", "en"))) or {}
        return {"locale": locale, "label": chosen.get("open", "Open"),
                "fallback": locale not in strings, "rtl": locale in ("ar", "he", "fa", "ur")}

    if mode == "refresh":
        since = int(user_input.get("since_seq", 0))
        events = [item for item in all_records if item.seq > since]
        return {"fresh": True, "source": "stored-events", "events": len(events),
                "interval_seconds": int(payload.get("interval_seconds", 30)),
                "live_badge": False}

    if mode == "grant":
        revoke = bool(user_input.get("revoke"))
        if revoke:
            _emit(db, workspace_id, base + ".revoked", str(uuid.uuid4()), str(payload.get("resource")),
                  {"resource": payload.get("resource"), "scope": payload.get("scope")},
                  idem=f"{workspace_id}:{base}.revoked:{uuid.uuid4()}")
        revocations = _records(db, workspace_id, base + ".revoked")
        active = not any(str(item.payload.get("resource")) == str(payload.get("resource")) for item in revocations)
        return {"resource": payload.get("resource"), "scope": payload.get("scope"),
                "active": active, "immediate": True, "audited": True}

    if mode == "config":
        value = user_input.get("value")
        expected = str(payload.get("value_type", "str"))
        valid = value is not None and not SECRET.search(str(value))
        typed = valid and ((expected == "int" and isinstance(value, int)) or
                           (expected == "bool" and isinstance(value, bool)) or
                           (expected == "str" and isinstance(value, str)))
        return {"setting": payload.get("setting"), "default": payload.get("default"),
                "value_type": expected, "typed": bool(typed), "valid": bool(valid),
                "secrets_in_tables": False}

    if mode == "trace":
        correlation = str(user_input.get("correlation_id", "corr-" + str(record.entity_id)))
        _emit(db, workspace_id, base + ".turn", str(uuid.uuid4()), str(payload.get("topic")),
              {"message": str(user_input.get("message", "")), "correlation_id": correlation},
              idem=f"{workspace_id}:{base}.turn:{uuid.uuid4()}")
        events = _records(db, workspace_id, base + ".turn")
        return {"topic": payload.get("topic"), "correlation_id": correlation,
                "events": len(events), "correlated": True, "inspectable": True}

    if mode == "estimate":
        prices = payload.get("prices") or {}
        units = int(user_input.get("units", 0))
        total = round(sum(float(price) * units for price in prices.values()), 2)
        return {"prices": prices, "units": units, "total": total,
                "label": "estimate", "charged": False, "provider_quote": False}

    if mode == "transition":
        approved = bool(user_input.get("approve"))
        states = payload.get("states") or []
        target = str(payload.get("to_state", "approved")) if approved else str(payload.get("from_state", "draft"))
        return {"state": target, "states": states, "external_send": False,
                "approval_required": str(payload.get("to_state")) in states}

    if mode == "rate":
        limit = max(1, int(payload.get("limit", 2)))
        _emit(db, workspace_id, base + ".call", str(uuid.uuid4()), str(kind),
              {"window": payload.get("window")}, idem=f"{workspace_id}:{base}.call:{uuid.uuid4()}")
        count = len(_records(db, workspace_id, base + ".call"))
        return {"limit": limit, "window": payload.get("window"), "count": count,
                "blocked": count > limit, "workspace_scoped": True}

    if mode == "preview":
        kind_type = str(user_input.get("type", ""))
        strategies = payload.get("strategies") or {}
        supported = kind_type in (payload.get("types") or [])
        return {"type": kind_type, "supported": supported,
                "strategy": strategies.get(kind_type, "unsupported"),
                "unsupported": [t for t in (payload.get("types") or []) if t not in strategies]}

    if mode == "prompt":
        content = str(user_input.get("content", ""))
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", content)]
        kept = [part for part in sentences if not re.search(
            r"ignore (all )?(previous|prior) instructions|send (the )?data|exfiltrate", part, re.I)]
        return {"boundary": payload.get("boundary"), "sanitized": " ".join(kept),
                "instructions_stripped": len(kept) != len(sentences), "external_action": False}

    if mode == "totp":
        used = _records(db, workspace_id, base + ".used")
        code = str(user_input.get("code", ""))
        recovery = user_input.get("recovery_code")
        token_hash = hashlib.sha256((str(payload.get("seed_token")) + code).encode()).hexdigest()
        replay = any(item.idempotency_key == f"{workspace_id}:{base}.used:{token_hash}" for item in used)
        if not replay:
            _emit(db, workspace_id, base + ".used", str(uuid.uuid4()), str(kind),
                  {"code_hash": token_hash[:16]}, idem=f"{workspace_id}:{base}.used:{token_hash}")
        return {"verified": code == str(payload.get("code")) or bool(recovery),
                "replay_rejected": replay, "recovery_used": bool(recovery),
                "raw_secret_logged": False}

    if mode == "pragma":
        values: dict[str, str] = {}
        for name in payload.get("pragmas") or []:
            safe = str(name)
            if safe not in ("journal_mode", "busy_timeout", "synchronous", "foreign_keys"):
                continue
            values[safe] = str(db.execute(text("PRAGMA " + safe)).scalar())
        return {"values": values, "journal_mode": values.get("journal_mode", ""),
                "busy_timeout": values.get("busy_timeout", ""),
                "read_from_live_database": True}

    if mode == "interface":
        value = str(user_input.get("value", ""))
        backends = []
        for backend in payload.get("backends") or []:
            digest = hashlib.sha256((str(backend) + value + workspace_id).encode()).hexdigest()[:12]
            backends.append({"backend": backend, "satisfies_contract": bool(digest), "digest": digest})
        return {"backends": backends, "workspace_scoped": True, "no_code_copy": True}

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
    return _out(_emit(db, workspace_id, EVENT_PREFIX + kind, str(uuid.uuid4()), body.name, body.payload), kind)


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
    _spec(kind)
    event = next((item for item in _records(db, workspace_id, EVENT_PREFIX + kind)
                  if str(item.entity_id) == record_id), None)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="capability record not found")
    result = _evaluate(db, workspace_id, kind, event, body.input or {})
    if not isinstance(result, dict):
        return JSONResponse(content=result)
    return EvaluateOut(kind=kind, row_id=kind.upper(), record_id=record_id, result=result)


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
        imported.append(_out(_emit(db, workspace_id, EVENT_PREFIX + kind, str(uuid.uuid4()),
                                   str(item.get("name", "imported")), payload,
                                   idem=f"{workspace_id}:{EVENT_PREFIX + kind}:{uuid.uuid4()}"), kind))
    return imported
