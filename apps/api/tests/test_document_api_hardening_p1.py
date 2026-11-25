"""Named acceptance tests for Papermark P1 document hardening.

PM-123 (document jobs), PM-141 (published OpenAPI spec) and PM-146 (document
rate limit + canonical error envelope). Every test drives the real FastAPI app
through the ``client`` fixture and inspects real persisted rows and audit
events. There are no app mocks, fake spec files or fabricated passes.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.main import app
from novara_core.middleware import (
    DOCUMENT_RATE_LIMIT_CODE,
    DOCUMENT_RATE_LIMIT_MESSAGE,
    SECURITY_HEADERS,
    document_limiter,
)
from novara_core.models import Event, User
from novara_core.modules.jobs import Job
from novara_core.modules.storage import ConversionJob

from .conftest import auth, bootstrap

DOCUMENTS = "/api/v1/workspaces/{wid}/documents"
STORAGE = "/api/v1/workspaces/{wid}/storage"
JOBS = "/api/v1/workspaces/{wid}/jobs"
SPEC_PATH = "/api/v1/workspaces/{wid}/storage/openapi-document-spec"


def test_pm123_document_job_enqueued_executed_and_audited(client, db_session):
    """A document conversion job is enqueued, executed and audited end to end."""
    tokens = bootstrap(client, "DocJobs", "docjobs@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    owner_id = db_session.execute(
        select(User.id).where(User.email == "docjobs@example.com")
    ).scalar_one()

    payload_text = b"NOVARA queued conversion"
    uploaded = client.post(
        STORAGE.format(wid=wid) + "/files",
        headers=headers,
        files={"file": ("notes.txt", payload_text, "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    source_id = uploaded.json()["id"]

    enqueued = client.post(
        JOBS.format(wid=wid),
        headers=headers,
        json={
            "job_type": "document_conversion",
            "payload": {
                "workspace_id": wid,
                "source_file_id": source_id,
                "target_format": "text",
            },
        },
    )
    assert enqueued.status_code == 201, enqueued.text
    job_id = enqueued.json()["id"]
    assert enqueued.json()["status"] == "queued"

    ran = client.post(
        JOBS.format(wid=wid) + "/run",
        headers=headers,
        json={"job_types": ["document_conversion"]},
    )
    assert ran.status_code == 200, ran.text
    assert ran.json()["succeeded"] == 1, ran.json()

    fetched = client.get(JOBS.format(wid=wid) + f"/{job_id}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["status"] == "succeeded"
    assert body["result"]["job_id"] in db_session.execute(
        select(ConversionJob.id).where(ConversionJob.workspace_id == wid)
    ).scalars().all()
    result_file_id = body["result"]["result_file_id"]
    assert result_file_id

    conversion = db_session.get(ConversionJob, body["result"]["job_id"])
    assert conversion.workspace_id == wid
    assert conversion.status == "completed"
    assert conversion.result_file_id == result_file_id
    assert conversion.created_by == owner_id  # real owner used as audit actor
    converted = client.get(
        STORAGE.format(wid=wid) + f"/files/{result_file_id}/download", headers=headers
    )
    assert converted.status_code == 200, converted.text
    assert converted.content == payload_text

    events = db_session.execute(
        select(Event).where(Event.workspace_id == wid)
    ).scalars().all()
    for event_type in ("job.queued", "job.started", "job.completed"):
        assert any(e.event_type == event_type and e.entity_id == job_id for e in events)
    assert any(
        e.event_type == "file.converted"
        and e.entity_id == conversion.id
        and e.payload.get("result_file_id") == result_file_id
        for e in events
    )

    # Both workspaces now queue the same job type. A run scoped to one workspace
    # must never claim the other workspace's queued job.
    ours_probe_text = b"queued in owner workspace"
    ours_probe_upload = client.post(
        STORAGE.format(wid=wid) + "/files",
        headers=headers,
        files={"file": ("ours-probe.txt", ours_probe_text, "text/plain")},
    )
    assert ours_probe_upload.status_code == 201, ours_probe_upload.text
    ours_probe = client.post(
        JOBS.format(wid=wid),
        headers=headers,
        json={
            "job_type": "document_conversion",
            "payload": {
                "workspace_id": wid,
                "source_file_id": ours_probe_upload.json()["id"],
                "target_format": "text",
            },
        },
    )
    assert ours_probe.status_code == 201, ours_probe.text
    ours_probe_id = ours_probe.json()["id"]

    other = client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-docjobs@example.com",
            "display_name": "Other owner",
            "password": "Password123!",
        },
    )
    assert other.status_code == 200, other.text
    other_wid, other_headers = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(
        JOBS.format(wid=wid) + f"/{job_id}", headers=other_headers
    ).status_code == 403
    assert client.get(JOBS.format(wid=wid), headers=other_headers).status_code == 403

    other_upload = client.post(
        STORAGE.format(wid=other_wid) + "/files",
        headers=other_headers,
        files={"file": ("other-probe.txt", b"queued in other workspace", "text/plain")},
    )
    assert other_upload.status_code == 201, other_upload.text
    other_job = client.post(
        JOBS.format(wid=other_wid),
        headers=other_headers,
        json={
            "job_type": "document_conversion",
            "payload": {
                "workspace_id": other_wid,
                "source_file_id": other_upload.json()["id"],
                "target_format": "text",
            },
        },
    )
    assert other_job.status_code == 201, other_job.text
    other_job_id = other_job.json()["id"]

    foreign_run = client.post(
        JOBS.format(wid=other_wid) + "/run",
        headers=other_headers,
        json={"job_types": ["document_conversion"]},
    )
    assert foreign_run.status_code == 200, foreign_run.text
    assert foreign_run.json()["claimed"] == 1
    assert foreign_run.json()["succeeded"] == 1
    assert db_session.get(Job, other_job_id).status == "succeeded"
    assert db_session.get(Job, ours_probe_id).status == "queued"
    assert db_session.get(Job, job_id).status == "succeeded"
    other_events = db_session.execute(
        select(Event).where(Event.workspace_id == other_wid)
    ).scalars().all()
    assert other_events
    assert all(event.entity_id != ours_probe_id for event in other_events)


def test_pm141_published_openapi_spec_matches_real_document_routes(client):
    """The published spec is generated from, and matches, real document routes."""
    tokens = bootstrap(client, "DocSpec", "docspec@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])

    response = client.get(SPEC_PATH.format(wid=wid), headers=headers)
    assert response.status_code == 200, response.text
    published = response.json()

    expected = {
        path: operations
        for path, operations in app.openapi()["paths"].items()
        if "/documents" in path or "/storage" in path
    }
    assert expected, "the real app must expose document/storage routes"
    assert set(published["paths"]) == set(expected)
    assert published["paths"] == expected
    known = "/api/v1/workspaces/{workspace_id}/storage/files"
    assert known in published["paths"]
    assert "get" in published["paths"][known]
    assert all("/documents" in p or "/storage" in p for p in published["paths"])
    assert published.get("components", {}).get("schemas"), "referenced schemas must be preserved"
    assert published["info"] == app.openapi()["info"]


def test_pm146_document_rate_limit_returns_canonical_envelope(client):
    """Over-limit document requests get the documented envelope and headers."""
    tokens = bootstrap(client, "DocLimit", "doclimit@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    document_url = DOCUMENTS.format(wid=wid)

    original_limit, original_window = document_limiter.limit, document_limiter.window_seconds
    document_limiter.configure(3, 60)
    document_limiter.reset()
    try:
        for allowed in range(3):
            response = client.get(document_url, headers=headers)
            assert response.status_code == 200, response.text
            assert response.headers["X-RateLimit-Limit"] == "3"
            assert response.headers["X-RateLimit-Remaining"] == str(2 - allowed)
            assert response.headers["X-RateLimit-Window"] == "60"

        blocked = client.get(document_url, headers=headers)
        assert blocked.status_code == 429
        assert blocked.json() == {
            "error": {
                "code": DOCUMENT_RATE_LIMIT_CODE,
                "message": DOCUMENT_RATE_LIMIT_MESSAGE,
                "retry_after": 60,
            }
        }
        assert blocked.headers["Retry-After"] == "60"
        assert blocked.headers["X-RateLimit-Limit"] == "3"
        assert blocked.headers["X-RateLimit-Remaining"] == "0"
        assert blocked.headers["X-RateLimit-Window"] == "60"
        for name, value in SECURITY_HEADERS.items():
            assert blocked.headers[name] == value

        non_document = client.get("/health")
        assert non_document.status_code == 200
        assert "X-RateLimit-Limit" not in non_document.headers
        assert non_document.json()["status"] == "ok"
    finally:
        document_limiter.reset()
        document_limiter.configure(original_limit, original_window)
