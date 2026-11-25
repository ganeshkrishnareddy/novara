"""Clean-room P2/P3 Plane local background-task ledger acceptance tests.

Named rows: PL-073, PL-076, PL-078, PL-081, PL-082, PL-083, PL-084, PL-086.
No upstream source copied. No external service, broker, outbound email or
outbound webhook is contacted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import socket

import pytest
from sqlalchemy import select

from novara_core.models import new_id, now
from novara_core.modules.plane_task_ledger import SEED_DEFAULTS, WebhookEndpoint
from novara_core.modules.projects import Project, ProjectItem, ProjectPage
from novara_core.modules.storage import StoredFile

from .conftest import auth, bootstrap

MEMBER_EMAIL = "plt-member@example.com"


@pytest.fixture(autouse=True)
def _ban_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("external network forbidden in clean-room P2 acceptance tests")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


def _setup(client):
    owner = bootstrap(client, email="plt-owner@example.com", workspace_name="PLT WS")
    ws = owner["workspace_id"]
    other = client.post(
        "/api/v1/workspaces", headers=auth(owner["access_token"]), json={"name": "Other PLT"}
    )
    assert other.status_code == 200, other.text
    return {
        "ws": ws,
        "h": auth(owner["access_token"]),
        "other_ws": other.json()["workspace_id"],
        "h_other": auth(other.json()["access_token"]),
        "owner": owner,
    }


def _base(ctx) -> str:
    return f"/api/v1/workspaces/{ctx['ws']}/plane-tasks"


def _cycle(client, ctx) -> dict:
    response = client.post(_base(ctx) + "/jobs/run", headers=ctx["h"], params={"limit": 20})
    assert response.status_code == 200, response.text
    return response.json()


def _project(db, workspace_id: str, name: str) -> Project:
    row = Project(
        id=new_id(), workspace_id=workspace_id, name=name,
        description="clean-room task fixture", status="planning", owner_id="plt-owner",
        created_at=now(), updated_at=now(),
    )
    db.add(row)
    db.commit()
    return row


def test_pl073_task_result_queryable_after_worker_completion(client, db_session):
    """PL-073: a completed local task leaves a durable, queryable result."""
    ctx = _setup(client)
    created = client.post(
        _base(ctx) + "/results", headers=ctx["h"],
        json={
            "task_type": "metrics.refresh",
            "result": {"contacts": 3, "leads": 1},
            "request_key": "plt-073-result",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "queued"
    assert client.get(_base(ctx) + "/results/plt-073-result", headers=ctx["h"]).status_code == 404

    summary = _cycle(client, ctx)
    assert summary["succeeded"] >= 1

    result = client.get(_base(ctx) + "/results/plt-073-result", headers=ctx["h"])
    assert result.status_code == 200, result.text
    assert result.json()["task_type"] == "metrics.refresh"
    assert result.json()["result"] == {"contacts": 3, "leads": 1}

    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/plane-tasks/results/plt-073-result",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 404, cross.text


def test_pl076_no_external_email_without_explicit_configuration_and_authorization(client, db_session):
    """PL-076: default install sends nothing; explicit opt-in stays local-only."""
    ctx = _setup(client)
    policy = client.get(_base(ctx) + "/email/policy", headers=ctx["h"])
    assert policy.status_code == 200 and policy.json()["enabled"] is False
    assert policy.json()["authorized_by"] is None

    body = {"recipient": "viewer@example.com", "subject": "Your export", "body": "Ready"}
    created = client.post(_base(ctx) + "/email/drafts", headers=ctx["h"], json=body)
    assert created.status_code == 201, created.text
    _cycle(client, ctx)
    assert client.get(_base(ctx) + "/email/drafts", headers=ctx["h"]).json() == []

    denied = client.put(
        _base(ctx) + "/email/policy", headers=ctx["h"],
        json={"enabled": True, "authorization": "just-because"},
    )
    assert denied.status_code == 403, denied.text

    enabled = client.put(
        _base(ctx) + "/email/policy", headers=ctx["h"],
        json={"enabled": True, "authorization": "EXPLICIT-LOCAL-AUTHORIZATION"},
    )
    assert enabled.status_code == 200 and enabled.json()["enabled"] is True
    assert enabled.json()["authorized_by"]

    client.post(_base(ctx) + "/email/drafts", headers=ctx["h"], json=body)
    _cycle(client, ctx)
    drafts = client.get(_base(ctx) + "/email/drafts", headers=ctx["h"]).json()
    assert len(drafts) == 1
    assert drafts[0]["recipient"] == "viewer@example.com"
    assert drafts[0]["dispatch_mode"] == "local_only"
    assert client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/plane-tasks/email/drafts", headers=ctx["h_other"]
    ).json() == []


def test_pl078_webhook_delivery_is_signed_retried_and_auditable(client, db_session):
    """PL-078: signed attempts, retries and an audit record all persist locally."""
    ctx = _setup(client)
    created = client.post(
        _base(ctx) + "/webhooks", headers=ctx["h"],
        json={
            "name": "Local receiver",
            "target_hint": "local://tasks/receiver",
            "failures_before_success": 2,
        },
    )
    assert created.status_code == 201, created.text
    endpoint = created.json()
    assert endpoint["algorithm"] == "hmac-sha256"
    assert endpoint["signing_secret"]

    delivered = client.post(
        _base(ctx) + f"/webhooks/{endpoint['id']}/deliveries", headers=ctx["h"],
        json={"body": {"event": "work_item.created"}, "max_attempts": 3},
    )
    assert delivered.status_code == 201, delivered.text

    # One local worker cycle follows the enqueued retry chain to success.
    summary = _cycle(client, ctx)
    assert summary["claimed"] >= 3

    deliveries = client.get(
        _base(ctx) + f"/webhooks/{endpoint['id']}/deliveries", headers=ctx["h"]
    ).json()
    assert [item["attempt"] for item in deliveries] == [1, 2, 3]
    assert [item["outcome"] for item in deliveries] == ["failed", "failed", "succeeded"]
    assert all(item["algorithm"] == "hmac-sha256" for item in deliveries)
    assert all(len(item["signature"]) == 64 for item in deliveries)

    from novara_core.security import hash_token

    endpoint_row = db_session.execute(
        select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint["id"])
    ).scalar_one()
    expected = hmac.new(
        bytes.fromhex(hash_token(endpoint["signing_secret"])),
        b'{"event":"work_item.created"}',
        hashlib.sha256,
    ).hexdigest()
    assert all(item["signature"] == expected for item in deliveries)
    assert endpoint_row.secret_hash == hash_token(endpoint["signing_secret"])
    assert len(str(endpoint_row.secret_hash)) == 64

    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/plane-tasks/webhooks/{endpoint['id']}/deliveries",
        headers=ctx["h_other"],
    ).json()
    assert cross == []


def test_pl081_work_item_export_downloads_workspace_scoped_data(client, db_session):
    """PL-081: an export completes and its download contains only this workspace."""
    ctx = _setup(client)
    mine = _project(db_session, ctx["ws"], "Mine")
    theirs = _project(db_session, ctx["other_ws"], "Theirs")
    db_session.add(
        ProjectItem(
            id=new_id(), workspace_id=ctx["ws"], project_id=mine.id,
            title="Visible work item", status="todo", priority="high",
            tags=[], created_at=now(), updated_at=now(),
        )
    )
    db_session.add(
        ProjectItem(
            id=new_id(), workspace_id=ctx["other_ws"], project_id=theirs.id,
            title="Foreign secret item", status="todo", priority="low",
            tags=[], created_at=now(), updated_at=now(),
        )
    )
    db_session.commit()

    created = client.post(
        _base(ctx) + "/exports/work-items", headers=ctx["h"], json={"format": "csv"}
    )
    assert created.status_code == 201, created.text
    _cycle(client, ctx)

    exports = client.get(_base(ctx) + "/exports", headers=ctx["h"]).json()
    export = next(item for item in exports if item["export_type"] == "work_items")
    assert export["row_count"] == 1
    download = client.get(_base(ctx) + f"/exports/{export['id']}/download", headers=ctx["h"])
    assert download.status_code == 200, download.text
    assert "Visible work item" in download.text
    assert "Foreign secret item" not in download.text
    assert "attachment" in download.headers["content-disposition"]

    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/plane-tasks/exports/{export['id']}/download",
        headers=ctx["h_other"],
    )
    assert cross.status_code == 404, cross.text


def test_pl082_chart_export_matches_displayed_aggregate(client, db_session):
    """PL-082: chart export data equals the chart series shown by the API."""
    ctx = _setup(client)
    from novara_core.events import publish_event

    for _ in range(3):
        publish_event(
            db_session, workspace_id=ctx["ws"], event_type="task.created", entity_id=new_id()
        )
    publish_event(
        db_session, workspace_id=ctx["ws"], event_type="task.updated", entity_id=new_id()
    )
    publish_event(
        db_session, workspace_id=ctx["other_ws"], event_type="task.created", entity_id=new_id()
    )
    db_session.commit()

    shown = client.get(_base(ctx) + "/charts/series", headers=ctx["h"]).json()["series"]
    assert shown == [
        {"event_type": "task.created", "count": 3},
        {"event_type": "task.updated", "count": 1},
    ]

    created = client.post(_base(ctx) + "/exports/chart", headers=ctx["h"])
    assert created.status_code == 201, created.text
    _cycle(client, ctx)

    exports = client.get(_base(ctx) + "/exports", headers=ctx["h"]).json()
    export = next(item for item in exports if item["export_type"] == "chart")
    download = client.get(_base(ctx) + f"/exports/{export['id']}/download", headers=ctx["h"])
    assert download.status_code == 200, download.text
    assert json.loads(download.text) == shown


def test_pl083_each_page_edit_creates_a_retrievable_version(client, db_session):
    """PL-083: every page edit task creates the next retrievable version."""
    ctx = _setup(client)
    project = _project(db_session, ctx["ws"], "Docs")
    page = ProjectPage(
        id=new_id(), workspace_id=ctx["ws"], project_id=project.id, scope="project",
        title="Runbook", body="First", author_id="plt-owner",
        created_at=now(), updated_at=now(),
    )
    db_session.add(page)
    db_session.commit()

    first = client.post(
        _base(ctx) + f"/pages/{page.id}/versions", headers=ctx["h"], json={}
    )
    assert first.status_code == 201, first.text
    _cycle(client, ctx)

    page.body = "Second"
    db_session.commit()
    second = client.post(
        _base(ctx) + f"/pages/{page.id}/versions", headers=ctx["h"],
        json={"editor_id": "plt-editor"},
    )
    assert second.status_code == 201, second.text
    _cycle(client, ctx)

    versions = client.get(_base(ctx) + f"/pages/{page.id}/versions", headers=ctx["h"]).json()
    assert [item["version"] for item in versions] == [1, 2]
    assert [item["body"] for item in versions] == ["First", "Second"]
    assert versions[1]["editor_id"] == "plt-editor"

    missing = client.post(
        _base(ctx) + f"/pages/{new_id()}/versions", headers=ctx["h"], json={}
    )
    assert missing.status_code == 404, missing.text


def test_pl084_file_metadata_only_after_successful_storage_processing(client, db_session, tmp_path):
    """PL-084: asset metadata appears only after real local bytes are processed."""
    ctx = _setup(client)
    payload = b"clean-room asset bytes"
    path = tmp_path / "asset.bin"
    path.write_bytes(payload)
    good = StoredFile(
        id=new_id(), workspace_id=ctx["ws"], original_name="asset.bin",
        filename="asset.bin", mime_type="application/octet-stream",
        size_bytes=len(payload), storage_path=str(path),
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
        uploaded_by="plt-owner", created_at=now(),
    )
    missing_path = tmp_path / "missing.bin"
    bad = StoredFile(
        id=new_id(), workspace_id=ctx["ws"], original_name="missing.bin",
        filename="missing.bin", mime_type="application/octet-stream",
        size_bytes=10, storage_path=str(missing_path),
        checksum_sha256="0" * 64, uploaded_by="plt-owner", created_at=now(),
    )
    db_session.add_all([good, bad])
    db_session.commit()

    assert client.post(
        _base(ctx) + f"/assets/{bad.id}/process", headers=ctx["h"]
    ).status_code == 201
    _cycle(client, ctx)
    assets = client.get(_base(ctx) + "/assets", headers=ctx["h"]).json()
    assert all(item["file_id"] != bad.id for item in assets)

    assert client.post(
        _base(ctx) + f"/assets/{good.id}/process", headers=ctx["h"]
    ).status_code == 201
    _cycle(client, ctx)
    assets = client.get(_base(ctx) + "/assets", headers=ctx["h"]).json()
    assert len(assets) == 1
    assert assets[0]["file_id"] == good.id
    assert assets[0]["status"] == "processed"
    assert assets[0]["size_bytes"] == len(payload)
    assert assets[0]["checksum_sha256"] == hashlib.sha256(payload).hexdigest()

    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/plane-tasks/assets", headers=ctx["h_other"]
    ).json()
    assert cross == []


def test_pl086_workspace_seed_is_repeatable_and_exact(client, db_session):
    """PL-086: seeding twice creates only the expected default records once."""
    ctx = _setup(client)
    for _ in range(2):
        created = client.post(_base(ctx) + "/workspace/seed", headers=ctx["h"])
        assert created.status_code == 201, created.text
        _cycle(client, ctx)

    rows = client.get(_base(ctx) + "/workspace/seed/defaults", headers=ctx["h"]).json()
    assert [row["seed_key"] for row in rows] == sorted(SEED_DEFAULTS)
    assert {row["seed_key"]: row["values"] for row in rows} == SEED_DEFAULTS

    cross = client.get(
        f"/api/v1/workspaces/{ctx['other_ws']}/plane-tasks/workspace/seed/defaults",
        headers=ctx["h_other"],
    ).json()
    assert cross == []
