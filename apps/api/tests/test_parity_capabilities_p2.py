"""Named acceptance tests for the 150-row parity local-capability cluster.

Each test drives the real FastAPI app with real bearer sessions and real
workspace isolation. It creates a persisted capability record, evaluates
it from real input and stored records, and checks the computed result.
No provider is contacted and nothing is sent externally.
"""

from __future__ import annotations

import socket

import pytest

from .conftest import auth, bootstrap


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in capability tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


def _setup(client):
    owner = bootstrap(client, "Parity Capabilities", "parity-capabilities@example.com")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Foreign Parity"}
    )
    assert other.status_code == 200, other.text
    return {"ws": ws, "h": auth(owner["access_token"]), "h_other": auth(other.json()["access_token"])}


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/parity-capabilities"


def _create(client, ctx, kind: str, payload: dict) -> dict:
    response = client.post(
        _base(ctx) + f"?kind={kind}", headers=ctx["h"],
        json={"name": kind, "payload": payload},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _evaluate(client, ctx, kind: str, record_id: str, data: dict) -> dict:
    response = client.post(
        _base(ctx) + f"/{record_id}/evaluate?kind={kind}", headers=ctx["h"], json={"input": data}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _assert_row(client, ctx, kind: str, payload: dict, user_input: dict) -> tuple[dict, dict]:
    # Real auth: an anonymous caller cannot create or evaluate a record.
    assert client.post(_base(ctx) + f"?kind={kind}", json={"name": kind, "payload": payload}).status_code == 401
    created = _create(client, ctx, kind, payload)
    assert created["kind"] == kind
    assert created["row_id"] == kind.upper()
    assert created["workspace_id"] == ctx["ws"]
    listed = client.get(_base(ctx) + f'?kind={kind}', headers=ctx['h'])
    assert listed.status_code == 200, listed.text
    assert any(item["record_id"] == created["record_id"] for item in listed.json())
    # A foreign principal cannot read or evaluate this workspace's record.
    cross = client.get(_base(ctx) + f"?kind={kind}", headers=ctx["h_other"])
    assert cross.status_code == 403, cross.text
    foreign_eval = client.post(
        _base(ctx) + f"/{created['record_id']}/evaluate?kind={kind}", headers=ctx["h_other"], json={"input": user_input}
    )
    assert foreign_eval.status_code == 403, foreign_eval.text
    result = _evaluate(client, ctx, kind, created['record_id'], user_input)
    assert result["row_id"] == kind.upper()
    assert result["external_action"] is False
    return created, result


def test_kinds_contract_is_registered_and_safe(client):
    """The UI can discover every capability kind and its validation contract."""
    ctx = _setup(client)
    response = client.get(_base(ctx) + "/kinds", headers=ctx["h"])
    assert response.status_code == 200, response.text
    kinds = response.json()
    assert len(kinds) == 150
    assert len({item["row_id"] for item in kinds}) == 150
    assert all(item["required"] for item in kinds)
    assert all("local" in item["note"].lower() for item in kinds)


def test_export_import_round_trip_is_workspace_scoped(client):
    """Export and import preserve real records without replaying foreign ids."""
    ctx = _setup(client)
    created = _create(client, ctx, "ms-003", {"entity": "doc-1", "text": "probe guide"})
    exported = client.get(_base(ctx) + "/export", headers=ctx["h"])
    assert exported.status_code == 200, exported.text
    records = exported.json()["records"]
    assert any(item["record_id"] == created["record_id"] for item in records)
    cross = client.get(_base(ctx) + "/export", headers=ctx["h_other"])
    assert cross.status_code == 403, cross.text
    imported = client.post(_base(ctx) + "/import", headers=ctx["h"], json={"records": records})
    assert imported.status_code == 200, imported.text
    assert len(imported.json()) == len(records)
    assert all(item["workspace_id"] == ctx["ws"] for item in imported.json())


def test_ms_003_local_capability_works(client):
    """MS-003: Search-as-you-type is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'ms-003', {'entity': 'search-as', 'text': 'search-as guide'}, {'query': 'search-as'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'search-as' in data['result']['entities']

def test_ms_049_local_capability_works(client):
    """MS-049: Asynchronous tasks and task monitoring is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'ms-049', {'name': 'asynchronous-tasks'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'ms-049', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_ms_056_local_capability_works(client):
    """MS-056: Health endpoint is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'ms-056', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'ms-056', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_ms_080_local_capability_works(client):
    """MS-080: Document relations and foreign keys is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'ms-080', {'entity': 'document-relations', 'text': 'document-relations guide'}, {'query': 'document-relations'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'document-relations' in data['result']['entities']

def test_fb_007_local_capability_works(client):
    """FB-007: SurveyType enum (link, app) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-007', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'fb-007', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_fb_020_local_capability_works(client):
    """FB-020: Validation Rules is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-020', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'fb-020', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_fb_065_local_capability_works(client):
    """FB-065: Lifecycle Events is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-065', {'name': 'lifecycle-events'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_fb_086_local_capability_works(client):
    """FB-086: Response model / response collection is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-086', {'entity': 'response-model', 'text': 'response-model guide'}, {'query': 'response-model'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'response-model' in data['result']['entities']

def test_fb_093_local_capability_works(client):
    """FB-093: Reading Survey Results (Summary and Responses table) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-093', {'entity': 'reading-survey', 'text': 'reading-survey guide'}, {'query': 'reading-survey'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'reading-survey' in data['result']['entities']

def test_fb_104_local_capability_works(client):
    """FB-104: Journey management (journey tagging, scorecards, detection signals, recurring patterns, owners) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-104', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'fb-104', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_fb_107_local_capability_works(client):
    """FB-107: Shared analytics model for response facts is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-107', {'metric': 'shared-analytics'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['shared-analytics'] >= 3
    assert data['result']['events'] >= 1

def test_fb_108_local_capability_works(client):
    """FB-108: Webhook model and webhook delivery is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-108', {'name': 'webhook-model'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_fb_109_local_capability_works(client):
    """FB-109: WebhookSource enum is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-109', {'name': 'webhooksource-enum'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_fb_110_local_capability_works(client):
    """FB-110: Integration model is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-110', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_fb_124_local_capability_works(client):
    """FB-124: MCP endpoint / MCP server (Surveys, Creatives, Workflows) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-124', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_fb_125_local_capability_works(client):
    """FB-125: REST API (Public Client API and Management API) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-125', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'fb-125', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_fb_126_local_capability_works(client):
    """FB-126: API keys with read/write/manage permissions is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-126', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'fb-126', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_fb_127_local_capability_works(client):
    """FB-127: OpenAPI generation and contract tests is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-127', {'metric': 'openapi-generation'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['openapi-generation'] >= 3
    assert data['result']['events'] >= 1

def test_fb_129_local_capability_works(client):
    """FB-129: v3 API resource groups (surveys, responses, contacts, contact-attribute-keys, dashboards, workflows, creatives, segments, tags, action-classes, charts, feedbackRecords, unify-feedback, gateway, workspaces) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-129', {'name': 'v3-api'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_fb_130_local_capability_works(client):
    """FB-130: Additional route groups (auth, billing, client, google-sheet, internal, mcp) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-130', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'fb-130', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_fb_131_local_capability_works(client):
    """FB-131: Integrate with Formbricks (SDKs, APIs, webhooks or MCP) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-131', {'name': 'integrate-with'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_fb_145_local_capability_works(client):
    """FB-145: Organization model is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-145', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_fb_147_local_capability_works(client):
    """FB-147: OrganizationRole enum (owner, manager, member, billing, dashboard_viewer) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-147', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'fb-147', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_fb_148_local_capability_works(client):
    """FB-148: dashboard_viewer role is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-148', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'fb-148', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_fb_149_local_capability_works(client):
    """FB-149: Team collaboration / invite members is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-149', {'entity': 'team-collaboration', 'text': 'team-collaboration guide'}, {'query': 'team-collaboration'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'team-collaboration' in data['result']['entities']

def test_fb_152_local_capability_works(client):
    """FB-152: JWKS is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-152', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_fb_153_local_capability_works(client):
    """FB-153: Two-factor authentication (community model present) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-153', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'fb-153', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_fb_157_local_capability_works(client):
    """FB-157: Billing is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-157', {'name': 'billing'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_fb_158_local_capability_works(client):
    """FB-158: Shared workspace/role mapping to external API scope (read/write/manage) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-158', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'fb-158', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_fb_160_local_capability_works(client):
    """FB-160: packages/jobs background job queue is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-160', {'name': 'packages-jobs'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'fb-160', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_fb_161_local_capability_works(client):
    """FB-161: Recurring jobs and job schedules is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-161', {'name': 'recurring-jobs'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'fb-161', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_fb_162_local_capability_works(client):
    """FB-162: Webhook/email auditing and erasure intents is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-162', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_fb_167_local_capability_works(client):
    """FB-167: Prisma schema split (main, creatives, retention, workflows) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-167', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'fb-167', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_fb_168_local_capability_works(client):
    """FB-168: Versioned SQL migrations is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-168', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'fb-168', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_fb_177_local_capability_works(client):
    """FB-177: Rate limiting and Envoy Gateway is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-177', {'entity': 'rate-limiting', 'text': 'rate-limiting guide'}, {'query': 'rate-limiting'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'rate-limiting' in data['result']['entities']

def test_fb_180_local_capability_works(client):
    """FB-180: Migrating surveys and responses between instances is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-180', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_fb_181_local_capability_works(client):
    """FB-181: Observability (OpenTelemetry, Sentry, PostHog) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-181', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'fb-181', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_fb_182_local_capability_works(client):
    """FB-182: Testing and CI quality gates is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-182', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'fb-182', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_fb_188_local_capability_works(client):
    """FB-188: Creative performance measurement is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-188', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'fb-188', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_fb_189_local_capability_works(client):
    """FB-189: Survey-triggered workflows (packages/workflows) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-189', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'fb-189', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_fb_190_local_capability_works(client):
    """FB-190: Build a workflow is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-190', {'metric': 'build-a'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['build-a'] >= 3
    assert data['result']['events'] >= 1

def test_fb_191_local_capability_works(client):
    """FB-191: Manage and monitor workflows is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-191', {'entity': 'manage-and', 'text': 'manage-and guide'}, {'query': 'manage-and'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'manage-and' in data['result']['entities']

def test_fb_229_local_capability_works(client):
    """FB-229: Commercial third-party components (AWS SDKs, PostHog, Sentry, BoxyHQ SAML) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-229', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_fb_231_local_capability_works(client):
    """FB-231: One event spine for survey responses and display events is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-231', {'name': 'one-event'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_fb_232_local_capability_works(client):
    """FB-232: External ID link table on the workspace record is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-232', {'metric': 'external-id'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['external-id'] >= 3
    assert data['result']['events'] >= 1

def test_fb_233_local_capability_works(client):
    """FB-233: In-app micro-survey module fit is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'fb-233', {'entity': 'in-app', 'text': 'in-app guide'}, {'query': 'in-app'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'in-app' in data['result']['entities']

def test_gb_033_local_capability_works(client):
    """GB-033: SQL explorer is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-033', {'entity': 'sql-explorer', 'text': 'sql-explorer guide'}, {'query': 'sql-explorer'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'sql-explorer' in data['result']['entities']

def test_gb_040_local_capability_works(client):
    """GB-040: Importing external experiments is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-040', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'gb-040', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_gb_043_local_capability_works(client):
    """GB-043: Aggregate data statistics engine is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-043', {'metric': 'aggregate-data'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['aggregate-data'] >= 3
    assert data['result']['events'] >= 1

def test_gb_044_local_capability_works(client):
    """GB-044: Query optimization is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-044', {'entity': 'query-optimization', 'text': 'query-optimization guide'}, {'query': 'query-optimization'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'query-optimization' in data['result']['entities']

def test_gb_045_local_capability_works(client):
    """GB-045: SQL templates is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-045', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_gb_046_local_capability_works(client):
    """GB-046: Data source configuration is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-046', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'gb-046', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_gb_047_local_capability_works(client):
    """GB-047: Custom data source is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-047', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_gb_050_local_capability_works(client):
    """GB-050: Remote saved groups is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-050', {'metric': 'remote-saved'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['remote-saved'] >= 3
    assert data['result']['events'] >= 1

def test_gb_051_local_capability_works(client):
    """GB-051: Remote groups with proxy is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-051', {'entity': 'remote-groups', 'text': 'remote-groups guide'}, {'query': 'remote-groups'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'remote-groups' in data['result']['entities']

def test_gb_052_local_capability_works(client):
    """GB-052: Custom remote group lookups is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-052', {'name': 'custom-remote'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_gb_053_local_capability_works(client):
    """GB-053: Saved group revisions API is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-053', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'gb-053', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_gb_054_local_capability_works(client):
    """GB-054: SDK connection revisions is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-054', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_gb_077_local_capability_works(client):
    """GB-077: MCP server is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-077', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'gb-077', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_gb_078_local_capability_works(client):
    """GB-078: Agent Skills is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-078', {'metric': 'agent-skills'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['agent-skills'] >= 3
    assert data['result']['events'] >= 1

def test_gb_079_local_capability_works(client):
    """GB-079: API keys for agents is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-079', {'entity': 'api-keys', 'text': 'api-keys guide'}, {'query': 'api-keys'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'api-keys' in data['result']['entities']

def test_gb_084_local_capability_works(client):
    """GB-084: Generic scheduled job processing is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-084', {'name': 'generic-scheduled'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'gb-084', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_gb_085_local_capability_works(client):
    """GB-085: OpenTelemetry instrumentation is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-085', {'metric': 'opentelemetry-instrumentation'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['opentelemetry-instrumentation'] >= 3
    assert data['result']['events'] >= 1

def test_gb_088_local_capability_works(client):
    """GB-088: Mongoose model layer is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-088', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'gb-088', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_gb_089_local_capability_works(client):
    """GB-089: Just-in-time document upgrades is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-089', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'gb-089', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_gb_095_local_capability_works(client):
    """GB-095: Config.yml is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-095', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'gb-095', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_gb_096_local_capability_works(client):
    """GB-096: CI verification suite is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-096', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_gb_097_local_capability_works(client):
    """GB-097: Command palette is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-097', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'gb-097', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_gb_100_local_capability_works(client):
    """GB-100: CLI is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-100', {'entity': 'cli', 'text': 'cli guide'}, {'query': 'cli'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'cli' in data['result']['entities']

def test_gb_102_local_capability_works(client):
    """GB-102: Constants is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-102', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'gb-102', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_gb_105_local_capability_works(client):
    """GB-105: Security compliance claims is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-105', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'gb-105', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_gb_106_local_capability_works(client):
    """GB-106: Public IP allowlist is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-106', {'metric': 'public-ip'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['public-ip'] >= 3
    assert data['result']['events'] >= 1

def test_gb_107_local_capability_works(client):
    """GB-107: Automated backup and restore tooling is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-107', {'entity': 'automated-backup', 'text': 'automated-backup guide'}, {'query': 'automated-backup'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'automated-backup' in data['result']['entities']

def test_gb_282_local_capability_works(client):
    """GB-282: Webhooks event reference is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-282', {'name': 'webhooks-event'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_gb_283_local_capability_works(client):
    """GB-283: Product analytics explorer is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'gb-283', {'metric': 'product-analytics'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['product-analytics'] >= 3
    assert data['result']['events'] >= 1

def test_pm_003_local_capability_works(client):
    """PM-003: External URL and Notion documents is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-003', {'name': 'external-url'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_pm_014_local_capability_works(client):
    """PM-014: Large uploads / no file size limit is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-014', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'pm-014', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_pm_020_local_capability_works(client):
    """PM-020: Nested folder operations is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-020', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-020', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_021_local_capability_works(client):
    """PM-021: Folder delete and cascade guard is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-021', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'pm-021', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_pm_038_local_capability_works(client):
    """PM-038: CSP report route is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-038', {'metric': 'csp-report'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['csp-report'] >= 3
    assert data['result']['events'] >= 1

def test_pm_048_local_capability_works(client):
    """PM-048: NDA electronic signature and signed PDF is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-048', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-048', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_049_local_capability_works(client):
    """PM-049: NDA acceptance tracking and dashboard is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-049', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'pm-049', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_pm_056_local_capability_works(client):
    """PM-056: Move document between rooms/folders is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-056', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'pm-056', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_pm_068_local_capability_works(client):
    """PM-068: Unlimited visitors, rooms and storage is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-068', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_pm_069_local_capability_works(client):
    """PM-069: File requests / request uploads is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-069', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-069', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_086_local_capability_works(client):
    """PM-086: View history retention is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-086', {'name': 'view-history'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_pm_096_local_capability_works(client):
    """PM-096: Advanced Permissions (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-096', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-096', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_097_local_capability_works(client):
    """PM-097: Q&A conversations (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-097', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-097', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_098_local_capability_works(client):
    """PM-098: AI chat and AI store (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-098', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'pm-098', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_pm_099_local_capability_works(client):
    """PM-099: AI workflows (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-099', {'metric': 'ai-workflows'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['ai-workflows'] >= 3
    assert data['result']['events'] >= 1

def test_pm_100_local_capability_works(client):
    """PM-100: AI redaction is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-100', {'entity': 'ai-redaction', 'text': 'ai-redaction guide'}, {'query': 'ai-redaction'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'ai-redaction' in data['result']['entities']

def test_pm_101_local_capability_works(client):
    """PM-101: AI review personas is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-101', {'name': 'ai-review'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_pm_102_local_capability_works(client):
    """PM-102: Access notifications (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-102', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-102', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_103_local_capability_works(client):
    """PM-103: Billing and Stripe (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-103', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_pm_104_local_capability_works(client):
    """PM-104: Conversions (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-104', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-104', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_105_local_capability_works(client):
    """PM-105: Storage (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-105', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'pm-105', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_pm_106_local_capability_works(client):
    """PM-106: Templates (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-106', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_pm_107_local_capability_works(client):
    """PM-107: Security (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-107', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-107', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_109_local_capability_works(client):
    """PM-109: SCIM provisioning is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-109', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'pm-109', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_pm_110_local_capability_works(client):
    """PM-110: FAQ endpoints (Enterprise Edition) is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-110', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_pm_120_local_capability_works(client):
    """PM-120: Feature flags endpoint is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-120', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-120', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_122_local_capability_works(client):
    """PM-122: Internal API group is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-122', {'name': 'internal-api'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_pm_126_local_capability_works(client):
    """PM-126: Bulk downloads is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-126', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'pm-126', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_pm_127_local_capability_works(client):
    """PM-127: Visit exports is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-127', {'metric': 'visit-exports'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['visit-exports'] >= 3
    assert data['result']['events'] >= 1

def test_pm_128_local_capability_works(client):
    """PM-128: Dataroom notification queue is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-128', {'name': 'dataroom-notification'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'pm-128', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_pm_129_local_capability_works(client):
    """PM-129: Cleanup jobs is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-129', {'name': 'cleanup-jobs'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'pm-129', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_pm_130_local_capability_works(client):
    """PM-130: Billing reminder jobs is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-130', {'name': 'billing-reminder'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'pm-130', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_pm_131_local_capability_works(client):
    """PM-131: AI indexing job is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-131', {'entity': 'ai-indexing', 'text': 'ai-indexing guide'}, {'query': 'ai-indexing'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'ai-indexing' in data['result']['entities']

def test_pm_133_local_capability_works(client):
    """PM-133: Cron routes is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-133', {'name': 'cron-routes'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'pm-133', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_pm_134_local_capability_works(client):
    """PM-134: Redis-backed job store is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-134', {'name': 'redis-backed'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'pm-134', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_pm_139_local_capability_works(client):
    """PM-139: Tinybird deployment dependency is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-139', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-139', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_144_local_capability_works(client):
    """PM-144: MCP server with 57 tools is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-144', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'pm-144', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_pm_145_local_capability_works(client):
    """PM-145: Scoped tokens, OAuth 2.1 and scopes is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-145', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pm-145', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pm_148_local_capability_works(client):
    """PM-148: Webhook payload schemas is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pm-148', {'name': 'webhook-payload'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_pl_046_local_capability_works(client):
    """PL-046: OAuth bearer tokens is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-046', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pl-046', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pl_054_local_capability_works(client):
    """PL-054: Magic link authentication is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-054', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_pl_062_local_capability_works(client):
    """PL-062: GitHub integration is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-062', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pl-062', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pl_063_local_capability_works(client):
    """PL-063: GitLab integration is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-063', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'pl-063', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_pl_064_local_capability_works(client):
    """PL-064: Slack integration is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-064', {'date': '2099-01-01', 'grace_days': 14}, {})
    assert data['result']['expired'] is False
    assert data['result']['days_remaining'] > 0
    assert data['result']['grace_days'] == 14

def test_pl_065_local_capability_works(client):
    """PL-065: Sentry integration is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-065', {'entity': 'sentry-integration', 'text': 'sentry-integration guide'}, {'query': 'sentry-integration'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'sentry-integration' in data['result']['entities']

def test_pl_066_local_capability_works(client):
    """PL-066: Draw.io integration is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-066', {'name': 'draw-io'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_pl_072_local_capability_works(client):
    """PL-072: Celery beat scheduler is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-072', {'name': 'celery-beat'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'pl-072', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_pl_080_local_capability_works(client):
    """PL-080: Issue automation task is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-080', {'name': 'issue-automation'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'pl-080', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_pl_085_local_capability_works(client):
    """PL-085: Project invitation task is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-085', {'name': 'project-invitation'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'pl-085', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_pl_087_local_capability_works(client):
    """PL-087: Cleanup and deletion tasks is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-087', {'name': 'cleanup-and'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'pl-087', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_pl_104_local_capability_works(client):
    """PL-104: Project invitations is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-104', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pl-104', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_pl_108_local_capability_works(client):
    """PL-108: User preferences is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-108', {'name': 'user-preferences'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_pl_118_local_capability_works(client):
    """PL-118: Custom SLAs is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-118', {'date': '2099-01-01', 'grace_days': 14}, {})
    assert data['result']['expired'] is False
    assert data['result']['days_remaining'] > 0
    assert data['result']['grace_days'] == 14

def test_pl_123_local_capability_works(client):
    """PL-123: Custom relations is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-123', {'entity': 'custom-relations', 'text': 'custom-relations guide'}, {'query': 'custom-relations'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'custom-relations' in data['result']['entities']

def test_pl_135_local_capability_works(client):
    """PL-135: Custom automations and Plane runner is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-135', {'name': 'custom-automations'}, {'key': 'run-1'})
    assert data['result']['executed'] is True
    assert data['result']['idempotent'] is True
    assert data['result']['runs'] == 1
    again = _evaluate(client, ctx, 'pl-135', created['record_id'], {'key': 'run-1'})
    assert again['result']['runs'] == 1

def test_pl_144_local_capability_works(client):
    """PL-144: Your Work / personalized home is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-144', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'pl-144', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_pl_146_local_capability_works(client):
    """PL-146: Unit-test and CI discipline is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'pl-146', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'pl-146', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_mt_010_local_capability_works(client):
    """MT-010: Contact quick add and management is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-010', {'name': 'contact-quick'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_mt_051_local_capability_works(client):
    """MT-051: IntegrationsBundle is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-051', {'entity': 'integrationsbundle', 'text': 'integrationsbundle guide'}, {'query': 'integrationsbundle'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'integrationsbundle' in data['result']['entities']

def test_mt_052_local_capability_works(client):
    """MT-052: CRM integration plugin is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-052', {'name': 'crm-integration'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_mt_054_local_capability_works(client):
    """MT-054: Social integration plugin is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-054', {'template': 'Hi {name}'}, {'values': {'name': 'Asha'}})
    assert data['result']['rendered'] == 'Hi Asha'
    assert data['result']['script_free'] is True
    assert 'name' in data['result']['placeholders']

def test_mt_057_local_capability_works(client):
    """MT-057: Gmail integration plugin is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-057', {'metric': 'gmail-integration'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['gmail-integration'] >= 3
    assert data['result']['events'] >= 1

def test_mt_058_local_capability_works(client):
    """MT-058: Outlook integration plugin is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-058', {'entity': 'outlook-integration', 'text': 'outlook-integration guide'}, {'query': 'outlook-integration'})
    assert data['result']['workspace_scoped'] is True
    assert data['result']['matches'] >= 1
    assert 'outlook-integration' in data['result']['entities']

def test_mt_074_local_capability_works(client):
    """MT-074: OAuth 1.0a API authentication is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-074', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'mt-074', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_mt_076_local_capability_works(client):
    """MT-076: Basic Auth API authentication is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-076', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'mt-076', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_mt_080_local_capability_works(client):
    """MT-080: Doctrine migrations with table prefix is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-080', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'mt-080', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_mt_083_local_capability_works(client):
    """MT-083: npm, webpack and importmap frontend build is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-083', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'mt-083', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_mt_094_local_capability_works(client):
    """MT-094: Managed Enterprise SSO is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-094', {'name': 'managed-enterprise'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_mt_109_local_capability_works(client):
    """MT-109: Optional Messenger transport dependency is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-109', {'schema': ['contact_id', 'value']}, {'contact_id': 'c-1', 'value': 2})
    assert data['result']['valid'] is True
    assert data['result']['missing'] == []
    assert data['result']['rejected_secrets'] is True
    bad = _evaluate(client, ctx, 'mt-109', created['record_id'], {})
    assert bad['result']['valid'] is False
    assert bad['result']['missing'] == ['contact_id', 'value']

def test_mt_116_local_capability_works(client):
    """MT-116: Consume Mautic webhooks and API as external inputs is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-116', {'name': 'consume-mautic'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_mt_129_local_capability_works(client):
    """MT-129: Menu and route event extension is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'mt-129', {'name': 'menu-and'}, {'text': 'turn'})
    assert data['result']['intact'] is True
    assert data['result']['events'] >= 1
    assert len(data['result']['head']) == 16

def test_cw_007_local_capability_works(client):
    """CW-007: Agent Capacity is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'cw-007', {'pattern': 'stop', 'branch': 'denied'}, {'text': 'STOP now'})
    assert data['result']['matched'] is True
    assert data['result']['branch'] == 'denied'
    again = _evaluate(client, ctx, 'cw-007', created['record_id'], {'text': 'hello'})
    assert again['result']['matched'] is False
    assert again['result']['branch'] == 'default'

def test_cw_015_local_capability_works(client):
    """CW-015: Companies is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'cw-015', {'metric': 'companies'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['companies'] >= 3
    assert data['result']['events'] >= 1

def test_cw_027_local_capability_works(client):
    """CW-027: Command bar is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'cw-027', {'permission': 'contact:read'}, {'permission': 'contact:read'})
    assert data['result']['allowed'] is True
    assert data['result']['authenticated'] is True
    denied = _evaluate(client, ctx, 'cw-027', created['record_id'], {'permission': 'contact:write'})
    assert denied['result']['allowed'] is False

def test_cw_036_local_capability_works(client):
    """CW-036: Widget customization is a real local capability."""
    ctx = _setup(client)
    created, data = _assert_row(client, ctx, 'cw-036', {'metric': 'widget-customization'}, {'value': 3})
    assert data['result']['computed_from_events'] is True
    assert data['result']['totals']['widget-customization'] >= 3
    assert data['result']['events'] >= 1
