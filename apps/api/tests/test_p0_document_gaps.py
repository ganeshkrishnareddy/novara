"""Named acceptance tests for the P0 document/storage gap rows.

Every test drives the real FastAPI application through the shared ``client``
fixture (real bootstrap identity, bearer sessions, workspace verification and
permission checks). No route is mocked and no figure is fabricated.
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime, timedelta, timezone

import pytest
from pypdf import PdfWriter
from sqlalchemy import select

from novara_core.modules.document_links import DocumentLink

from .conftest import auth, bootstrap


def _seed(client, wid, headers, title="Proposal", **link_kwargs):
    doc = client.post(
        f"/api/v1/workspaces/{wid}/documents",
        headers=headers,
        json={"title": title, "doc_type": "pdf", "storage_path": "metadata://p/proposal.pdf"},
    )
    assert doc.status_code == 201, doc.text
    document_id = doc.json()["id"]
    link = client.post(
        f"/api/v1/workspaces/{wid}/documents/{document_id}/links",
        headers=headers,
        json=link_kwargs,
    )
    assert link.status_code == 201, link.text
    return document_id, link.json()["id"], link.json()["token"]


def _upload(client, wid, headers, name="notes.txt", data=b"hello world", mime="text/plain"):
    res = client.post(
        f"/api/v1/workspaces/{wid}/storage/files",
        headers=headers,
        files={"file": (name, data, mime)},
    )
    assert res.status_code == 201, res.text
    return res.json()


def _foreign(client, headers):
    res = client.post("/api/v1/workspaces", headers=headers, json={"name": "Foreign"})
    assert res.status_code == 200, res.text
    return res.json()["workspace_id"], auth(res.json()["access_token"])


def test_pm002_presigned_upload_url_is_real_and_tamper_proof(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    pre = client.post(
        f"/api/v1/workspaces/{wid}/storage/presign-upload",
        headers=h,
        params={"filename": "presigned.txt", "content_type": "text/plain"},
    )
    assert pre.status_code == 200, pre.text
    body = pre.json()
    assert body["upload_token"] and "/storage/presigned-upload?token=" in body["upload_url"]
    assert body["expires_at"] > 0

    up = client.put(
        f"/api/v1/workspaces/{wid}/storage/presigned-upload",
        params={"token": body["upload_token"]},
        files={"file": ("presigned.txt", b"signed bytes", "text/plain")},
    )
    assert up.status_code == 201, up.text
    file_id = up.json()["file_id"]
    files = client.get(f"/api/v1/workspaces/{wid}/storage/files", headers=h).json()
    assert any(f["id"] == file_id and f["size_bytes"] == len(b"signed bytes") for f in files)

    bad = client.put(
        f"/api/v1/workspaces/{wid}/storage/presigned-upload",
        params={"token": body["upload_token"][:-4] + "AAAA"},
        files={"file": ("presigned.txt", b"tampered", "text/plain")},
    )
    assert bad.status_code == 403


def test_pm015_blob_storage_round_trips_bytes_and_isolates_workspaces(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    f = _upload(client, wid, h, data=b"round-trip payload")
    assert f["checksum_sha256"] == hashlib.sha256(b"round-trip payload").hexdigest()
    dl = client.get(f"/api/v1/workspaces/{wid}/storage/files/{f['id']}/download", headers=h)
    assert dl.status_code == 200 and dl.content == b"round-trip payload"
    fwid, fh = _foreign(client, h)
    denied = client.get(f"/api/v1/workspaces/{fwid}/storage/files/{f['id']}/download", headers=fh)
    assert denied.status_code in (401, 403, 404)


def test_pm012_pdf_preview_returns_real_extracted_pages(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    f = _upload(client, wid, h, name="doc.pdf", data=buf.getvalue(), mime="application/pdf")
    res = client.get(f"/api/v1/workspaces/{wid}/storage/files/{f['id']}/pdf-preview", headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["pages"] == 1
    assert len(res.json()["content"]) == 1


def test_pm028_shareable_link_resolves_to_document_metadata(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    did, _lid, token = _seed(client, wid, h)
    res = client.get(f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}", headers=h)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["document_id"] == did and data["title"] == "Proposal"
    assert data["view_only"] is True and data["password_required"] is False
    assert data["revoked"] is False and data["expired"] is False


def test_pm029_link_management_list_get_patch_and_revoke(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    did, lid, _token = _seed(client, wid, h)
    links = client.get(f"/api/v1/workspaces/{wid}/documents/{did}/links", headers=h)
    assert links.status_code == 200 and len(links.json()) == 1
    got = client.get(f"/api/v1/workspaces/{wid}/documents/links/{lid}", headers=h)
    assert got.status_code == 200 and got.json()["id"] == lid
    patched = client.patch(
        f"/api/v1/workspaces/{wid}/documents/links/{lid}",
        headers=h,
        json={"max_views": 5, "download_allowed": True},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["max_views"] == 5 and patched.json()["download_allowed"] is True
    revoked = client.post(f"/api/v1/workspaces/{wid}/documents/links/{lid}/revoke", headers=h)
    assert revoked.status_code == 200 and revoked.json()["revoked"] is True
    listed = client.get(f"/api/v1/workspaces/{wid}/documents/{did}/links", headers=h).json()
    assert listed[0]["revoked"] is True


def test_pm030_password_protected_link_unlock_is_enforced(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    _did, _lid, token = _seed(client, wid, h, password="s3cret")
    resolved = client.get(f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}", headers=h)
    assert resolved.json()["password_required"] is True
    wrong = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/unlock",
        headers=h, json={"password": "wrong"},
    )
    assert wrong.status_code == 403
    right = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/unlock",
        headers=h, json={"password": "s3cret"},
    )
    assert right.status_code == 200, right.text
    assert right.json()["unlocked"] is True and right.json()["session_token"]


def test_pm032_link_expiry_is_enforced_at_resolution(db_session, client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    _did, lid, token = _seed(client, wid, h, expires_in_hours=1)
    link = db_session.execute(select(DocumentLink).where(DocumentLink.id == lid)).scalar_one()
    link.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()
    res = client.get(f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}", headers=h)
    assert res.status_code == 410, res.text


def test_pm033_view_only_and_download_policy_is_enforced(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    _did, lid, token = _seed(client, wid, h, view_only=True, download_allowed=False)
    resolved = client.get(f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}", headers=h).json()
    assert resolved["view_only"] is True and resolved["download_allowed"] is False
    visit = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/visits",
        headers=h, json={"visitor_email": "reader@example.com"},
    )
    assert visit.status_code == 201, visit.text
    visit_id = visit.json()["id"]
    denied = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/visits/{visit_id}/download",
        headers=h, json={},
    )
    assert denied.status_code == 403
    client.patch(f"/api/v1/workspaces/{wid}/documents/links/{lid}", headers=h,
                 json={"download_allowed": True})
    allowed = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/visits/{visit_id}/download",
        headers=h, json={},
    )
    assert allowed.status_code == 201, allowed.text


def test_pm039_restricted_session_token_is_scoped_to_its_link(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    _d1, _l1, tok1 = _seed(client, wid, h, password="one")
    _d2, _l2, tok2 = _seed(client, wid, h, title="Second", password="two")
    session = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{tok1}/unlock",
        headers=h, json={"password": "one"},
    ).json()["session_token"]
    sh = {"X-Link-Session": session}
    own = client.get(f"/api/v1/workspaces/{wid}/documents/links/resolve/{tok1}", headers=sh)
    assert own.status_code == 200, own.text
    other = client.get(f"/api/v1/workspaces/{wid}/documents/links/resolve/{tok2}", headers=sh)
    assert other.status_code == 403
    anon = client.get(f"/api/v1/workspaces/{wid}/documents/links/resolve/{tok1}")
    assert anon.status_code == 401


def test_pm042_instant_revocation_kills_live_sessions(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    _did, lid, token = _seed(client, wid, h, password="secret")
    session = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/unlock",
        headers=h, json={"password": "secret"},
    ).json()["session_token"]
    sh = {"X-Link-Session": session}
    assert client.get(f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}",
                      headers=sh).status_code == 200
    revoke = client.post(f"/api/v1/workspaces/{wid}/documents/links/{lid}/instant-revoke", headers=h)
    assert revoke.status_code == 200 and revoke.json()["revoked"] is True
    denied = client.get(f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}", headers=sh)
    assert denied.status_code in (401, 410)


def test_pm072_viewer_and_visit_capture(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    _did, lid, token = _seed(client, wid, h)
    start = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/visits",
        headers=h,
        json={"visitor_name": "Ana", "visitor_email": "ana@example.com",
              "ip_address": "127.0.0.1", "user_agent": "pytest"},
    )
    assert start.status_code == 201, start.text
    visit = start.json()
    assert visit["visitor_name"] == "Ana" and visit["ip_address"] == "127.0.0.1"
    ended = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/visits/{visit['id']}/end",
        headers=h, json={},
    )
    assert ended.status_code == 200, ended.text
    visits = client.get(f"/api/v1/workspaces/{wid}/documents/links/{lid}/visits", headers=h)
    assert visits.status_code == 200 and len(visits.json()) == 1
    assert visits.json()[0]["visitor_email"] == "ana@example.com"


def test_pm074_page_by_page_analytics(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    did, _lid, token = _seed(client, wid, h)
    visit = client.post(
        f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/visits",
        headers=h, json={"visitor_email": "pages@example.com"},
    ).json()
    for page, duration in ((1, 12), (2, 30), (1, 8)):
        res = client.post(
            f"/api/v1/workspaces/{wid}/documents/links/resolve/{token}/visits/{visit['id']}/page-views",
            headers=h, json={"page_number": page, "duration_seconds": duration},
        )
        assert res.status_code == 201, res.text
    pages = client.get(f"/api/v1/workspaces/{wid}/documents/{did}/analytics/pages", headers=h)
    assert pages.status_code == 200, pages.text
    by_page = {p["page_number"]: p for p in pages.json()}
    assert by_page[1]["views"] == 2 and by_page[1]["total_duration_seconds"] == 20
    assert by_page[2]["views"] == 1 and by_page[2]["total_duration_seconds"] == 30
    assert by_page[1]["unique_viewers"] == 1


def test_pm080_verified_visitor_identification_and_consent(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    _did, lid, _token = _seed(client, wid, h)
    base = f"/api/v1/workspaces/{wid}/documents/viewers"
    no_consent = client.post(base, headers=h, json={
        "email": "viewer@example.com", "consent": False, "source_link_id": lid,
    })
    assert no_consent.status_code == 201, no_consent.text
    # A verified visitor without active consent must not be disclosed as identified.
    assert no_consent.json()["identified"] is False and no_consent.json()["email"] is None
    consent = client.post(base, headers=h, json={
        "email": "viewer@example.com", "display_name": "Viewer", "consent": True,
        "source_link_id": lid,
    })
    assert consent.status_code == 201, consent.text
    viewer = consent.json()
    assert viewer["email"] == "viewer@example.com" and viewer["contact_id"]
    revoked = client.patch(base + f"/{viewer['id']}/consent", headers=h, json={"granted": False})
    assert revoked.status_code == 200
    assert revoked.json()["email"] is None and revoked.json()["identified"] is False
    fwid, _fh = _foreign(client, h)
    denied = client.get(f"/api/v1/workspaces/{fwid}/documents/viewers", headers=h)
    assert denied.status_code in (401, 403, 404)


def test_pm125_document_conversion_job_produces_a_result_file(client):
    t = bootstrap(client)
    wid, h = t["workspace_id"], auth(t["access_token"])
    f = _upload(client, wid, h, name="report.txt", data=b"line one\nline two")
    res = client.post(
        f"/api/v1/workspaces/{wid}/storage/conversions",
        headers=h, json={"source_file_id": f["id"], "target_format": "text"},
    )
    assert res.status_code == 201, res.text
    job = res.json()
    assert job["status"] == "completed" and job["result_file_id"]
    fetched = client.get(f"/api/v1/workspaces/{wid}/storage/conversions/{job['id']}", headers=h)
    assert fetched.status_code == 200 and fetched.json()["result_file_id"] == job["result_file_id"]
