"""Cycle 1 smoke tests for newly implemented P0 capabilities."""

from __future__ import annotations

import pytest


def _bootstrap(client):
    from tests.conftest import bootstrap, auth

    tokens = bootstrap(client)
    return tokens["access_token"], auth(tokens["access_token"])


def test_document_sharing_link_lifecycle(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    # create a document
    doc = client.post(
        f"/api/v1/workspaces/{ws}/documents",
        json={"title": "Spec", "storage_path": "local/spec.pdf"},
        headers=headers,
    ).json()
    doc_id = doc["id"]

    # create a password-protected, expiring, view-limited link
    link_resp = client.post(
        f"/api/v1/workspaces/{ws}/documents/{doc_id}/links",
        json={"password": "secret", "expires_in_hours": 24, "max_views": 5, "view_only": True},
        headers=headers,
    )
    assert link_resp.status_code == 201
    link = link_resp.json()
    assert "token" in link

    # list links
    links = client.get(f"/api/v1/workspaces/{ws}/documents/{doc_id}/links", headers=headers)
    assert links.status_code == 200
    assert len(links.json()) == 1

    # resolve link
    resolved = client.get(
        f"/api/v1/workspaces/{ws}/documents/links/resolve/{link['token']}", headers=headers
    )
    assert resolved.status_code == 200
    assert resolved.json()["password_required"] is True

    # unlock
    unlock = client.post(
        f"/api/v1/workspaces/{ws}/documents/links/resolve/{link['token']}/unlock",
        json={"password": "secret"},
        headers=headers,
    )
    assert unlock.status_code == 200
    assert unlock.json()["unlocked"] is True
    wrong = client.post(
        f"/api/v1/workspaces/{ws}/documents/links/resolve/{link['token']}/unlock",
        json={"password": "nope"},
        headers=headers,
    )
    assert wrong.status_code == 403

    # start visit
    visit = client.post(
        f"/api/v1/workspaces/{ws}/documents/links/resolve/{link['token']}/visits",
        json={"visitor_name": "Alice", "visitor_email": "alice@example.com"},
        headers=headers,
    )
    assert visit.status_code == 201
    visit_id = visit.json()["id"]

    # record page view
    pv = client.post(
        f"/api/v1/workspaces/{ws}/documents/links/resolve/{link['token']}/visits/{visit_id}/page-views",
        json={"page_number": 1, "duration_seconds": 30},
        headers=headers,
    )
    assert pv.status_code == 201

    # end visit
    end = client.post(
        f"/api/v1/workspaces/{ws}/documents/links/resolve/{link['token']}/visits/{visit_id}/end",
        params={"duration_seconds": 45},
        headers=headers,
    )
    assert end.status_code == 200

    # identify visitor
    ident = client.post(
        f"/api/v1/workspaces/{ws}/documents/links/resolve/{link['token']}/identify",
        json={"visitor_name": "Alice", "visitor_email": "alice@example.com"},
        headers=headers,
    )
    assert ident.status_code == 200

    # visits list
    visits = client.get(
        f"/api/v1/workspaces/{ws}/documents/links/{link_resp.json()['id']}/visits" if False else
        f"/api/v1/workspaces/{ws}/documents/links/{[l['id'] for l in client.get(f'/api/v1/workspaces/{ws}/documents/{doc_id}/links', headers=headers).json()][0]}/visits",
        headers=headers,
    )
    assert visits.status_code == 200
    assert len(visits.json()) == 1

    # analytics
    analytics = client.get(
        f"/api/v1/workspaces/{ws}/documents/{doc_id}/analytics", headers=headers
    )
    assert analytics.status_code == 200
    assert analytics.json()[0]["page_number"] == 1

    # instant revoke
    link_id = [l["id"] for l in client.get(f"/api/v1/workspaces/{ws}/documents/{doc_id}/links", headers=headers).json()][0]
    revoke = client.post(
        f"/api/v1/workspaces/{ws}/documents/links/{link_id}/instant-revoke", headers=headers
    )
    assert revoke.status_code == 200
    assert revoke.json()["revoked"] is True

    # revoked link cannot be visited
    visit2 = client.post(
        f"/api/v1/workspaces/{ws}/documents/links/resolve/{link['token']}/visits",
        json={},
        headers=headers,
    )
    assert visit2.status_code == 410


def test_support_private_notes_and_search(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    ticket = client.post(
        f"/api/v1/workspaces/{ws}/tickets",
        json={"subject": "Help", "body": "I need support"},
        headers=headers,
    ).json()
    tid = ticket["id"]

    note = client.post(
        f"/api/v1/workspaces/{ws}/tickets/{tid}/notes",
        json={"body": "internal only"},
        headers=headers,
    )
    assert note.status_code == 201

    notes = client.get(f"/api/v1/workspaces/{ws}/tickets/{tid}/notes", headers=headers)
    assert notes.status_code == 200
    assert len(notes.json()) == 1

    # message
    client.post(
        f"/api/v1/workspaces/{ws}/tickets/{tid}/messages",
        json={"body": "public reply"},
        headers=headers,
    )

    # search
    search = client.get(f"/api/v1/workspaces/{ws}/tickets/search?q=Help", headers=headers)
    assert search.status_code == 200
    assert any(t["id"] == tid for t in search.json())


def test_notification_preferences(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    pref = client.post(
        f"/api/v1/workspaces/{ws}/notification-preferences",
        json={"level": "global", "target": "*", "channel": "email", "enabled": False},
        headers=headers,
    )
    assert pref.status_code == 201

    # upsert
    pref2 = client.post(
        f"/api/v1/workspaces/{ws}/notification-preferences",
        json={"level": "global", "target": "*", "channel": "email", "enabled": True},
        headers=headers,
    )
    assert pref2.status_code == 201
    assert pref2.json()["enabled"] is True

    listed = client.get(f"/api/v1/workspaces/{ws}/notification-preferences", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    # invalid channel
    bad = client.post(
        f"/api/v1/workspaces/{ws}/notification-preferences",
        json={"level": "global", "target": "*", "channel": "fax", "enabled": True},
        headers=headers,
    )
    assert bad.status_code == 422


def test_marketing_segments_and_templates(client):
    token, headers = _bootstrap(client)
    ws = client.get("/api/v1/auth/me", headers=headers).json()["workspace_id"]

    seg = client.post(
        f"/api/v1/workspaces/{ws}/campaigns/segments",
        json={"name": "Hot leads", "criteria": {"score": {"gte": 80}}},
        headers=headers,
    )
    assert seg.status_code == 201

    tmpl = client.post(
        f"/api/v1/workspaces/{ws}/campaigns/email-templates",
        json={"name": "Welcome", "subject": "Hi", "body": "Hello {{name}}"},
        headers=headers,
    )
    assert tmpl.status_code == 201

    # campaign with type
    camp = client.post(
        f"/api/v1/workspaces/{ws}/campaigns",
        json={"name": "Spring", "channel": "email", "campaign_type": "broadcast"},
        headers=headers,
    )
    assert camp.status_code == 201
    assert camp.json()["campaign_type"] == "broadcast"

    # duplicate segment
    dup = client.post(
        f"/api/v1/workspaces/{ws}/campaigns/segments",
        json={"name": "Hot leads"},
        headers=headers,
    )
    assert dup.status_code == 409