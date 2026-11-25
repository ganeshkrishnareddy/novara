from __future__ import annotations

import pytest

from novara_core.main import app
from novara_core.models import Company, Contact, Lead, Note, OutreachDraft, Task, new_id, now
from novara_core.modules import search

from .conftest import auth, bootstrap

PREFIX = "/api/v1/workspaces/{workspace_id}/search"


def _ensure_routes() -> None:
    already = any(
        (getattr(route, "path", "") or "").startswith(PREFIX)
        or getattr(route, "original_router", None) is search.router
        for route in app.routes
    )
    if not already:
        app.include_router(search.router)
    for route in app.routes:
        if getattr(route, "original_router", None) is search.router and not hasattr(route, "path"):
            route.path = PREFIX


@pytest.fixture(autouse=True)
def _module_router() -> None:
    _ensure_routes()


def _seed(client, db_session, workspace_id: str | None = None) -> tuple[str, dict]:
    tokens = bootstrap(client) if workspace_id is None else None
    wid = workspace_id or tokens["workspace_id"]
    headers = auth(tokens["access_token"]) if tokens else {}
    contact = Contact(
        id=new_id(), workspace_id=wid, email="alice@example.com",
        full_name="Alice Alpha", company_name="Acme Corp",
    )
    company = Company(id=new_id(), workspace_id=wid, name="Acme Corp", industry="Software")
    lead = Lead(
        id=new_id(), workspace_id=wid, contact_id=contact.id,
        source="webinar", status="qualified",
    )
    task = Task(id=new_id(), workspace_id=wid, title="Call Acme", description="Follow up")
    note = Note(
        id=new_id(), workspace_id=wid, contact_id=contact.id,
        author_id="author-1", body="Discussed pricing options",
    )
    draft = OutreachDraft(
        id=new_id(), workspace_id=wid, contact_id=contact.id,
        subject="Acme follow-up", body="Hello Alice", status="draft",
    )
    db_session.add_all([contact, company, lead, task, note, draft])
    db_session.commit()
    return wid, headers


def test_search_across_all_shared_types(client, db_session):
    wid, headers = _seed(client, db_session)
    response = client.get(
        f"/api/v1/workspaces/{wid}/search", headers=headers, params={"q": "acme"}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == len(payload["results"])
    assert set(payload["counts"]) == set(search.SEARCH_TYPES)
    by_type: dict[str, list[dict]] = {}
    for item in payload["results"]:
        by_type.setdefault(item["type"], []).append(item)
        assert item["id"]
        assert item["title"]
        assert item["url_hint"].startswith("/")

    assert "contact" in by_type       # company_name
    assert "company" in by_type       # name
    assert "task" in by_type          # title
    assert "outreach_draft" in by_type  # subject

    assert payload["counts"]["contact"] >= 1
    assert payload["counts"]["company"] >= 1
    assert payload["counts"]["task"] >= 1
    assert payload["counts"]["outreach_draft"] >= 1
    assert payload["counts"]["lead"] == 0
    assert payload["counts"]["note"] == 0


def test_search_matches_joined_lead_and_note_records(client, db_session):
    wid, headers = _seed(client, db_session)
    response = client.get(
        f"/api/v1/workspaces/{wid}/search", headers=headers, params={"q": "alice"}
    )
    assert response.status_code == 200, response.text
    types = {item["type"] for item in response.json()["results"]}
    assert {"contact", "lead", "note", "outreach_draft"}.issubset(types)
    lead = next(item for item in response.json()["results"] if item["type"] == "lead")
    assert "qualified" in lead["subtitle"]
    note = next(item for item in response.json()["results"] if item["type"] == "note")
    assert note["url_hint"].endswith("/notes")


def test_limit_and_invalid_queries(client, db_session):
    wid, headers = _seed(client, db_session)
    url = f"/api/v1/workspaces/{wid}/search"
    limited = client.get(url, headers=headers, params={"q": "acme", "limit": 2})
    assert limited.status_code == 200, limited.text
    assert len(limited.json()["results"]) == 2
    assert limited.json()["total"] == 2
    assert sum(limited.json()["counts"].values()) == 2

    assert client.get(url, headers=headers, params={"q": ""}).status_code == 422
    assert client.get(url, headers=headers, params={"q": "   "}).status_code == 422
    assert client.get(url, headers=headers, params={"q": "acme", "limit": 0}).status_code == 422
    assert client.get(url, headers=headers).status_code == 422


def test_literal_wildcards_are_not_expanded(client, db_session):
    wid, headers = _seed(client, db_session)
    url = f"/api/v1/workspaces/{wid}/search"
    assert client.get(url, headers=headers, params={"q": "%"}).json()["total"] == 0
    assert client.get(url, headers=headers, params={"q": "_"}).json()["total"] == 0


def test_search_never_exposes_other_workspace(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    other = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Other"}
    )
    assert other.status_code == 200, other.text
    other_wid, other_headers = other.json()["workspace_id"], auth(other.json()["access_token"])

    _seed(client, db_session, wid)
    db_session.add(
        Contact(
            id=new_id(), workspace_id=other_wid,
            email="secret@other.example", full_name="Secret Other",
        )
    )
    db_session.commit()

    url = f"/api/v1/workspaces/{wid}/search"
    own = client.get(url, headers=headers, params={"q": "secret"})
    assert own.status_code == 200, own.text
    assert own.json()["total"] == 0

    foreign = client.get(
        f"/api/v1/workspaces/{other_wid}/search", headers=headers, params={"q": "alice"}
    )
    assert foreign.status_code == 403
    allowed = client.get(
        f"/api/v1/workspaces/{other_wid}/search", headers=other_headers, params={"q": "secret"}
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["total"] == 1
    assert allowed.json()["results"][0]["title"] == "Secret Other"
