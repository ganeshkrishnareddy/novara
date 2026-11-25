"""Cycle 1 Batch 2 smoke tests."""

from __future__ import annotations


def _bootstrap(client):
    from tests.conftest import bootstrap, auth

    tokens = bootstrap(client)
    return tokens["access_token"], auth(tokens["access_token"])


def test_storage_upload_presign_download(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    # direct upload
    files = {"file": ("note.txt", b"hello world", "text/plain")}
    up = client.post(f"/api/v1/workspaces/{ws}/storage/files", files=files, headers=headers)
    assert up.status_code == 201
    fid = up.json()["id"]
    assert up.json()["checksum_sha256"]

    # download
    dl = client.get(f"/api/v1/workspaces/{ws}/storage/files/{fid}/download", headers=headers)
    assert dl.status_code == 200
    assert dl.content == b"hello world"

    # presigned download
    pd = client.post(f"/api/v1/workspaces/{ws}/storage/files/{fid}/presign-download", headers=headers)
    assert pd.status_code == 200
    tok = pd.json()["download_token"]
    pdl = client.get(f"/api/v1/workspaces/{ws}/storage/presigned-download?token={tok}")
    assert pdl.status_code == 200
    assert pdl.content == b"hello world"

    # presigned upload
    pu = client.post(
        f"/api/v1/workspaces/{ws}/storage/presign-upload",
        params={"filename": "x.txt", "content_type": "text/plain"},
        headers=headers,
    )
    assert pu.status_code == 200
    utok = pu.json()["upload_token"]
    files2 = {"file": ("x.txt", b"presigned bytes", "text/plain")}
    up2 = client.put(
        f"/api/v1/workspaces/{ws}/storage/presigned-upload?token={utok}", files=files2
    )
    assert up2.status_code == 201

    # delete
    de = client.delete(f"/api/v1/workspaces/{ws}/storage/files/{fid}", headers=headers)
    assert de.status_code == 200
    gone = client.get(f"/api/v1/workspaces/{ws}/storage/files/{fid}", headers=headers)
    assert gone.status_code == 404


def test_pdf_info(client, tmp_path):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    # create a minimal PDF
    try:
        from pypdf import PdfWriter
    except Exception:
        import pytest
        pytest.skip("pypdf unavailable")
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    p = tmp_path / "t.pdf"
    with open(p, "wb") as fh:
        writer.write(fh)
    with open(p, "rb") as fh:
        files = {"file": ("t.pdf", fh.read(), "application/pdf")}
    up = client.post(f"/api/v1/workspaces/{ws}/storage/files", files=files, headers=headers)
    assert up.status_code == 201
    fid = up.json()["id"]
    info = client.get(f"/api/v1/workspaces/{ws}/storage/files/{fid}/pdf-info", headers=headers)
    assert info.status_code == 200
    assert info.json()["pages"] == 1


def test_email_broadcast_unsubscribe(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    # contact
    c = client.post(
        f"/api/v1/workspaces/{ws}/contacts",
        json={"email": "a@example.com", "full_name": "A"},
        headers=headers,
    ).json()
    cid = c["id"]

    # broadcast
    b = client.post(
        f"/api/v1/workspaces/{ws}/email/broadcasts",
        json={"name": "News", "subject": "Hi", "body": "Hello"},
        headers=headers,
    )
    assert b.status_code == 201
    bid = b.json()["id"]

    # add recipient
    ar = client.post(
        f"/api/v1/workspaces/{ws}/email/broadcasts/{bid}/recipients",
        json={"contact_ids": [cid]},
        headers=headers,
    )
    assert ar.status_code == 200
    assert ar.json()["added"] == 1

    # queue + dispatch
    q = client.post(f"/api/v1/workspaces/{ws}/email/broadcasts/{bid}/queue", headers=headers)
    assert q.status_code == 200
    d = client.post(f"/api/v1/workspaces/{ws}/email/broadcasts/{bid}/dispatch", headers=headers)
    assert d.status_code == 200
    assert d.json()["sent"] == 1

    # unsubscribe token + unsubscribe
    tok = client.get(
        f"/api/v1/workspaces/{ws}/email/unsubscribe-token",
        params={"email": "a@example.com"},
        headers=headers,
    ).json()["token"]
    un = client.post(f"/api/v1/workspaces/{ws}/email/unsubscribe", json={"token": tok})
    assert un.status_code == 200

    # suppressed now
    sup = client.get(f"/api/v1/workspaces/{ws}/email/suppression", headers=headers)
    assert any(s["email"] == "a@example.com" for s in sup.json())

    # consent record
    cr = client.post(
        f"/api/v1/workspaces/{ws}/email/consent",
        json={"contact_id": cid, "granted": False},
        headers=headers,
    )
    assert cr.status_code == 201

    # manual suppression
    ms = client.post(
        f"/api/v1/workspaces/{ws}/email/suppression",
        params={"email": "b@example.com"},
        headers=headers,
    )
    assert ms.status_code == 201


def test_automation_branches_and_approval(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    auto = client.post(
        f"/api/v1/workspaces/{ws}/automations",
        json={
            "name": "Branchy",
            "trigger_type": "manual",
            "definition": [
                {"id": "c1", "type": "condition", "field": "score", "operator": "gt", "value": 5},
                {"id": "d1", "type": "delay", "seconds": 10},
                {"id": "a1", "type": "approval"},
                {"id": "n1", "type": "notify", "channel": "email"},
            ],
        },
        headers=headers,
    )
    assert auto.status_code == 201

    # dry run with context
    dr = client.post(
        f"/api/v1/workspaces/{ws}/automations/{auto.json()['id']}/dry_run",
        json={"trigger_event": "manual", "context": {"score": 10}},
        headers=headers,
    )
    assert dr.status_code in (200, 201)
    steps = dr.json()["steps"]
    assert steps[0]["result"] == "ok"
    assert steps[1]["delay_seconds"] == 10
    assert steps[2]["result"] == "pending_approval"

    # scheduled automation
    sa = client.post(
        f"/api/v1/workspaces/{ws}/automations",
        json={
            "name": "Sched",
            "trigger_type": "scheduled",
            "schedule": "0 9 * * *",
            "definition": [{"id": "s1", "type": "check", "check": "contact"}],
        },
        headers=headers,
    )
    assert sa.status_code == 201
    assert sa.json()["schedule"] == "0 9 * * *"


def test_projects_comments_milestones(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    proj = client.post(
        f"/api/v1/workspaces/{ws}/projects",
        json={"name": "P1"},
        headers=headers,
    ).json()
    pid = proj["id"]

    # item with tags
    item = client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/items",
        json={"title": "Task", "tags": ["bug", "urgent"]},
        headers=headers,
    )
    assert item.status_code == 201

    # comment
    com = client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/comments",
        json={"body": "looks good"},
        headers=headers,
    )
    assert com.status_code == 201

    # milestone
    ms = client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/milestones",
        json={"name": "v1", "due_at": "2026-12-01T00:00:00Z"},
        headers=headers,
    )
    assert ms.status_code == 201
    mid = ms.json()["id"]
    done = client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/milestones/{mid}/complete",
        headers=headers,
    )
    assert done.status_code == 200
    assert done.json()["completed_at"] is not None


def test_search_post(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    client.post(
        f"/api/v1/workspaces/{ws}/contacts",
        json={"email": "z@example.com", "full_name": "Zed"},
        headers=headers,
    )
    r = client.post(
        f"/api/v1/workspaces/{ws}/search",
        json={"q": "Zed"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["total"] >= 1