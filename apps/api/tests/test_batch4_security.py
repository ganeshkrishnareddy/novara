"""Batch 4 adversarial/security smoke tests."""

from __future__ import annotations


def _bootstrap(client, email="o@example.com"):
    from tests.conftest import bootstrap, auth

    tokens = bootstrap(client, email=email)
    return tokens["access_token"], auth(tokens["access_token"]), tokens["workspace_id"]


def test_cross_workspace_isolation(client):
    from tests.conftest import bootstrap, auth

    t1 = bootstrap(client, workspace_name="W1", email="a@example.com")
    h1 = auth(t1["access_token"])
    w1 = t1["workspace_id"]

    # create a second workspace under same user
    r = client.post("/api/v1/workspaces", headers=h1, json={"name": "W2"})
    assert r.status_code == 200
    w2 = r.json()["workspace_id"]
    h2 = auth(r.json()["access_token"])

    # create contact in w1
    c = client.post(f"/api/v1/workspaces/{w1}/contacts", json={"email": "x@y.com"}, headers=h1).json()

    # w2 cannot read w1 contact
    g = client.get(f"/api/v1/workspaces/{w1}/contacts/{c['id']}", headers=h2)
    assert g.status_code in (401, 403, 404)

    # w2 cannot create in w1
    cr = client.post(f"/api/v1/workspaces/{w1}/contacts", json={"email": "z@y.com"}, headers=h2)
    assert cr.status_code in (401, 403, 404)


def test_presigned_token_tampering(client):
    token, headers, ws = _bootstrap(client)
    files = {"file": ("n.txt", b"hi", "text/plain")}
    up = client.post(f"/api/v1/workspaces/{ws}/storage/files", files=files, headers=headers)
    fid = up.json()["id"]
    pd = client.post(f"/api/v1/workspaces/{ws}/storage/files/{fid}/presign-download", headers=headers)
    tok = pd.json()["download_token"]
    # tamper
    bad = tok[:-4] + "AAAA"
    r = client.get(f"/api/v1/workspaces/{ws}/storage/presigned-download?token={bad}")
    assert r.status_code in (400, 403, 410, 404)


def test_internal_notes_not_in_messages(client):
    token, headers, ws = _bootstrap(client)
    t = client.post(f"/api/v1/workspaces/{ws}/tickets", json={"subject": "s", "body": "b"}, headers=headers).json()
    tid = t["id"]
    client.post(f"/api/v1/workspaces/{ws}/tickets/{tid}/notes", json={"body": "secret internal"}, headers=headers)
    # messages endpoint should not include internal note
    msgs = client.get(f"/api/v1/workspaces/{ws}/tickets/{tid}/messages", headers=headers)
    assert msgs.status_code == 200
    for m in msgs.json():
        assert "secret internal" not in m.get("body", "")
    # internal notes endpoint has it
    notes = client.get(f"/api/v1/workspaces/{ws}/tickets/{tid}/notes", headers=headers)
    assert any("secret internal" in n["body"] for n in notes.json())


def test_unsubscribe_token_invalid(client):
    token, headers, ws = _bootstrap(client)
    r = client.post(f"/api/v1/workspaces/{ws}/email/unsubscribe", json={"token": "garbage"})
    assert r.status_code in (400, 403, 404, 422)


def test_dependency_self_cycle_rejected(client):
    token, headers, ws = _bootstrap(client)
    proj = client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "P"}, headers=headers).json()
    pid = proj["id"]
    item = client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/items", json={"title": "I"}, headers=headers).json()
    iid = item["id"]
    r = client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/items/{iid}/dependencies",
        json={"depends_on_id": iid},
        headers=headers,
    )
    assert r.status_code == 422


def test_flag_prerequisite_enforcement(client):
    token, headers, ws = _bootstrap(client)
    # prerequisite flag disabled
    client.post(f"/api/v1/workspaces/{ws}/flags", json={"key": "prereq", "enabled": False}, headers=headers)
    client.post(
        f"/api/v1/workspaces/{ws}/flags",
        json={"key": "main", "enabled": True, "rollout_percent": 100, "prerequisites": ["prereq"]},
        headers=headers,
    )
    ev = client.post(f"/api/v1/workspaces/{ws}/flags/main/evaluate", json={"user_key": "u", "attributes": {}}, headers=headers)
    assert ev.status_code == 200
    assert ev.json()["enabled"] is False
    assert ev.json()["reason"] == "prerequisite_failed"