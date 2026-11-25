"""Named acceptance tests for the seven P2 IMPLEMENTED_UNVERIFIED rows.

All API tests drive the real FastAPI app through the shared ``client``
fixture. The FB UI assertions read the actual SPA source; the backup row runs
the real local CLI against a throwaway SQLite file. No external service is
contacted.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from .conftest import auth, bootstrap

ROOT = Path(__file__).resolve().parents[3]
APP_JS = ROOT / "apps" / "web" / "app.js"
BACKUP_SCRIPT = ROOT / "scripts" / "backup_restore.py"


def _ctx(client):
    t = bootstrap(client)
    return t["workspace_id"], auth(t["access_token"])


def _survey(client, wid, headers, name="Feedback"):
    res = client.post(f"/api/v1/workspaces/{wid}/surveys", headers=headers,
                      json={"name": name, "description": "Local"})
    assert res.status_code == 201, res.text
    return res.json()


def _active(client, wid, headers, survey):
    res = client.patch(f"/api/v1/workspaces/{wid}/surveys/{survey['id']}",
                       headers=headers, json={"status": "active"})
    assert res.status_code == 200, res.text


def test_fb087_survey_score_validation_rejects_out_of_range_and_extra_fields(client):
    wid, h = _ctx(client)
    survey = _survey(client, wid, h)
    _active(client, wid, h, survey)
    path = f"/api/v1/workspaces/{wid}/surveys/{survey['id']}/responses"
    for bad in (-1, 0, 11, 100):
        res = client.post(path, headers=h, json={"score": bad})
        assert res.status_code == 422, (bad, res.text)
    extra = client.post(path, headers=h, json={"score": 8, "unknown": 1})
    assert extra.status_code == 422
    good = client.post(path, headers=h, json={"score": 10, "comment": "edge"})
    assert good.status_code == 201 and good.json()["score"] == 10
    assert "data-form=\"add-survey-response\"" in APP_JS.read_text(encoding="utf-8")


def test_fb088_survey_detail_reports_real_response_count_and_average(client):
    wid, h = _ctx(client)
    survey = _survey(client, wid, h)
    _active(client, wid, h, survey)
    path = f"/api/v1/workspaces/{wid}/surveys/{survey['id']}"
    empty = client.get(path, headers=h).json()
    assert empty["response_count"] == 0 and empty["average_score"] is None
    for score in (4, 7, 10):
        assert client.post(path + "/responses", headers=h, json={"score": score}).status_code == 201
    detail = client.get(path, headers=h).json()
    assert detail["response_count"] == 3 and detail["average_score"] == 7.0
    assert "case 'surveys': return loadSurveys(token)" in APP_JS.read_text(encoding="utf-8")


def test_fb089_survey_events_form_an_append_only_audit_trail(client):
    wid, h = _ctx(client)
    survey = _survey(client, wid, h, "Audited")
    _active(client, wid, h, survey)
    client.post(f"/api/v1/workspaces/{wid}/surveys/{survey['id']}/responses",
                headers=h, json={"score": 9})
    events = client.get(f"/api/v1/workspaces/{wid}/events", headers=h).json()
    survey_events = [e for e in events if str(e.get("entity_id") or "") == survey["id"]
                     or "survey" in str(e.get("event_type") or "")]
    assert any(e["event_type"] == "survey.created" for e in events)
    assert any(e["event_type"] == "survey.status_changed" for e in events)
    assert any(e["event_type"] == "survey.response_created" for e in events)
    assert survey_events
    before = [(e["id"], e["event_type"], e["payload"]) for e in events]
    client.get(f"/api/v1/workspaces/{wid}/events", headers=h)
    after = client.get(f"/api/v1/workspaces/{wid}/events", headers=h).json()
    assert [(e["id"], e["event_type"], e["payload"]) for e in after] == before
    paths = client.get("/openapi.json").json()["paths"]
    assert not any(p.startswith("/api/v1/workspaces/{workspace_id}/events/")
                   for p in paths)
    assert "{ route: 'surveys', label: 'Feedback Studio'" in APP_JS.read_text(encoding="utf-8")


def test_fb090_survey_routes_are_workspace_isolated(client):
    wid, h = _ctx(client)
    survey = _survey(client, wid, h, "Private")
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh = auth(other["access_token"])
    owid = other["workspace_id"]
    assert client.get(f"/api/v1/workspaces/{owid}/surveys", headers=oh).json() == []
    for method, path, kwargs in (
        ("get", f"/api/v1/workspaces/{owid}/surveys/{survey['id']}", {}),
        ("post", f"/api/v1/workspaces/{owid}/surveys/{survey['id']}/responses", {"json": {"score": 5}}),
        ("patch", f"/api/v1/workspaces/{owid}/surveys/{survey['id']}", {"json": {"status": "closed"}}),
    ):
        res = getattr(client, method)(path, headers=oh, **kwargs)
        assert res.status_code in (403, 404), (method, path, res.text)
    # A valid session from another workspace cannot use it against this one.
    assert client.get(f"/api/v1/workspaces/{wid}/surveys", headers=oh).status_code in (403, 404)
    assert "if (parts[0] === 'surveys' && parts[1]) return loadSurveyDetail" in APP_JS.read_text(
        encoding="utf-8")


def test_fb179_backup_verify_and_restore_round_trip_is_verified(tmp_path):
    source = tmp_path / "source.sqlite3"
    con = sqlite3.connect(source)
    con.executescript(
        "CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT);"
        "CREATE TABLE events (seq INTEGER PRIMARY KEY, event_type TEXT);"
        "CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY);"
        "INSERT INTO users VALUES ('u1','owner@example.test');"
        "INSERT INTO events VALUES (1,'survey.created');"
        "INSERT INTO alembic_version VALUES ('a7c3e9f1b5d8');"
    )
    con.commit()
    con.close()

    def run(*args):
        return subprocess.run([sys.executable, str(BACKUP_SCRIPT), *args],
                              capture_output=True, text=True, check=False)

    out = tmp_path / "backups"
    made = run("backup", "--db", str(source), "--out", str(out))
    assert made.returncode == 0, made.stderr
    assert "integrity: ok" in made.stdout
    backup = next(out.glob("novara-*.sqlite3"))
    checked = run("verify", "--db", str(backup))
    assert checked.returncode == 0 and "'events': 1" in checked.stdout
    con = sqlite3.connect(source)
    con.execute("DELETE FROM events")
    con.commit()
    con.close()
    restored = tmp_path / "restored.sqlite3"
    result = run("restore", "--from", str(backup), "--to", str(restored))
    assert result.returncode == 0 and "counts_verified" in result.stdout, result.stdout
    con = sqlite3.connect(restored)
    assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "a7c3e9f1b5d8"
    con.close()


def test_pl056_email_check_reports_availability_without_enumeration_abuse(client):
    import novara_core.main as core_main

    core_main._email_check_attempts.clear()
    registered = bootstrap(client)["workspace_id"]
    assert registered
    endpoint = "/api/v1/auth/email/check"
    assert client.post(endpoint, json={"email": "not-an-email"}).status_code == 422
    used = client.post(endpoint, json={"email": "owner@example.com"})
    assert used.status_code == 200 and used.json()["available"] is False
    fresh = client.post(endpoint, json={"email": "brand-new@example.com"})
    assert fresh.status_code == 200 and fresh.json()["available"] is True
    assert fresh.json()["email"] == "brand-new@example.com"
    # The check is read-only: it did not create an account or a session.
    denied = client.post("/api/v1/auth/login", json={
        "email": "brand-new@example.com", "password": "Password123!"})
    assert denied.status_code == 401
    # Bulk enumeration is bounded: the ninth attempt in the window is refused.
    for i in range(6):
        probe = client.post(endpoint, json={"email": f"probe{i}@example.com"})
        assert probe.status_code == 200
    ninth = client.post(endpoint, json={"email": "another@example.com"})
    assert ninth.status_code == 429, ninth.text
    assert "check.available" in APP_JS.read_text(encoding="utf-8")


def test_sb013_company_records_create_list_update_archive_and_isolation(client):
    wid, h = _ctx(client)
    base = f"/api/v1/workspaces/{wid}/companies"
    bad = client.post(base, headers=h, json={"name": "Bad", "owner_id": "foreign-user"})
    assert bad.status_code == 422
    made = client.post(base, headers=h, json={"name": "Acme", "industry": "Tech"})
    assert made.status_code == 201, made.text
    cid = made.json()["id"]
    assert any(c["id"] == cid for c in client.get(base, headers=h).json())
    dup = client.post(base, headers=h, json={"name": "Acme"})
    assert dup.status_code == 409

    second = client.post(base, headers=h, json={"name": "Globex"})
    assert second.status_code == 201
    patched = client.patch(base + f"/{cid}", headers=h,
                           json={"industry": "Finance", "location": "Remote"})
    assert patched.status_code == 200 and patched.json()["industry"] == "Finance"
    assert client.patch(base + f"/{cid}", headers=h, json={"name": "Globex"}).status_code == 409

    archived = client.post(base + f"/{cid}/archive", headers=h)
    assert archived.status_code == 200 and archived.json()["archived"] is True
    assert cid not in {c["id"] for c in client.get(base, headers=h).json()}
    assert any(c["id"] == cid for c in client.get(base, headers=h,
               params={"archived": "true"}).json())
    restored = client.post(base + f"/{cid}/restore", headers=h)
    assert restored.status_code == 200 and restored.json()["archived"] is False
    assert any(c["id"] == cid for c in client.get(base, headers=h).json())

    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other"}).json()
    oh = auth(other["access_token"])
    owid = other["workspace_id"]
    assert client.get(f"/api/v1/workspaces/{owid}/companies", headers=oh).json() == []
    assert client.patch(f"/api/v1/workspaces/{owid}/companies/{cid}", headers=oh,
                        json={"industry": "Stolen"}).status_code == 404
    assert client.post(f"/api/v1/workspaces/{owid}/companies/{cid}/archive",
                       headers=oh).status_code == 404
    assert client.get(f"/api/v1/workspaces/{owid}/companies", headers=h).status_code in (403, 404)
