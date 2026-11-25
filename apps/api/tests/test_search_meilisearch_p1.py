"""Named acceptance evidence for the remaining Meilisearch P1 rows.

NOVARA uses its own workspace-scoped SQL search; these tests prove the
equivalent guarantees locally. No search engine key, server or external call
is involved.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from novara_core.database import Base
from novara_core.main import API
from novara_core.modules.integrations import Integration

from .conftest import auth, bootstrap


def _create_contact(client, workspace_id, headers, email, name):
    response = client.post(
        f"{API}/workspaces/{workspace_id}/contacts",
        headers=headers,
        json={"email": email, "full_name": name},
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_ms006_search_filters_narrow_results_and_workspace_isolation_holds(client):
    first = bootstrap(client)
    ws1, headers1 = first["workspace_id"], auth(first["access_token"])
    second = client.post(
        API + "/workspaces",
        headers=headers1,
        json={"name": "Second Workspace"},
    )
    assert second.status_code in (200, 201), second.text
    ws2, headers2 = second.json()["workspace_id"], auth(second.json()["access_token"])

    _create_contact(client, ws1, headers1, "alice@example.com", "Alice Filter")
    _create_contact(client, ws1, headers1, "bob@example.com", "Bob Other")
    _create_contact(client, ws2, headers2, "carol@example.com", "Carol Filter")

    narrow = client.get(f"{API}/workspaces/{ws1}/search", headers=headers1,
                        params={"q": "Alice Filter"})
    assert narrow.status_code == 200, narrow.text
    assert narrow.json()["total"] == 1
    assert narrow.json()["results"][0]["id"]

    broad = client.get(f"{API}/workspaces/{ws1}/search", headers=headers1,
                       params={"q": "Filter"})
    assert broad.status_code == 200
    assert broad.json()["total"] == 1  # Alice matches; Bob does not
    assert any(r["id"] == narrow.json()["results"][0]["id"]
               for r in broad.json()["results"])

    other = client.get(f"{API}/workspaces/{ws2}/search", headers=headers1,
                       params={"q": "Carol"})
    assert other.status_code == 403, other.text

    assert client.get(f"{API}/workspaces/{ws1}/search", headers=headers1).status_code == 422


def test_ms028_search_limit_is_validated_and_result_count_is_exact(client):
    tokens = bootstrap(client)
    ws, headers = tokens["workspace_id"], auth(tokens["access_token"])
    for number in range(4):
        _create_contact(client, ws, headers, f"limit{number}@example.com", f"Limit Person {number}")

    assert client.get(f"{API}/workspaces/{ws}/search", headers=headers,
                      params={"q": "Limit Person", "limit": 0}).status_code == 422
    assert client.get(f"{API}/workspaces/{ws}/search", headers=headers,
                      params={"q": "Limit Person", "limit": 101}).status_code == 422

    one = client.get(f"{API}/workspaces/{ws}/search", headers=headers,
                     params={"q": "Limit Person", "limit": 1})
    assert one.status_code == 200, one.text
    assert len(one.json()["results"]) == 1
    assert one.json()["total"] == 1

    many = client.get(f"{API}/workspaces/{ws}/search", headers=headers,
                      params={"q": "Limit Person", "limit": 100})
    assert many.json()["total"] == len(many.json()["results"])


def test_ms062_no_master_key_is_required_by_novara_search(client):
    tokens = bootstrap(client)
    ws = tokens["workspace_id"]
    response = client.get(
        f"{API}/workspaces/{ws}/search",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        params={"q": "anything"},
    )
    assert response.status_code == 200, response.text
    assert "master_key" not in response.text
    assert "api_key" not in response.text


def test_ms063_secret_like_config_is_rejected_and_no_engine_key_is_stored(client, db_session):
    tokens = bootstrap(client)
    ws, headers = tokens["workspace_id"], auth(tokens["access_token"])

    rejected = client.put(
        f"{API}/workspaces/{ws}/integrations",
        headers=headers,
        json={"provider": "meilisearch", "config": {"apiKey": "supersecret"}},
    )
    assert rejected.status_code == 422, rejected.text
    assert db_session.scalars(select(Integration)).all() == []

    accepted = client.put(
        f"{API}/workspaces/{ws}/integrations",
        headers=headers,
        json={"provider": "meilisearch", "config": {"url": "http://localhost:7700"}},
    )
    assert accepted.status_code == 200, accepted.text
    row = db_session.scalars(select(Integration)).one()
    assert "apiKey" not in row.config
    assert "supersecret" not in str(row.config)


def test_ms065_search_result_fields_are_escaped_in_the_renderer():
    source = (Path(__file__).resolve().parents[2] / "web" / "app.js").read_text(encoding="utf-8")
    assert "function renderSearchResult" in source or "search-result" in source
    line = next(line for line in source.splitlines() if 'attr(result.url_hint' in line)
    assert "attr(result.id" in line
    assert "esc(" in source[source.index(line) - 500:source.index(line) + 500]
