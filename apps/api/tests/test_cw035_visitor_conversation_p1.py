"""Named acceptance test for CW-035 (visitor-started local conversation).

A real visitor token creates a genuine ticket and inbound message in the
configured agent inbox. The channel is fixed by the server; a visitor cannot
declare a decorative one. No external widget, provider or network call is used.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from novara_core.main import API
from novara_core.models import Contact, Event
from novara_core.modules.support import TICKET_CREATED, TICKET_MESSAGE_ADDED
from novara_core.modules.visitor_conversations import (
    VISITOR_CONVERSATION_STARTED,
    VISITOR_MESSAGE_ADDED,
    VISITOR_SITE_CREATED,
    VISITOR_SITE_REVOKED,
)

from .conftest import auth, bootstrap

APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def test_cw035_visitor_conversation_appears_in_agent_inbox(client, db_session):
    tokens = bootstrap(client, "CW035", "cw035-owner@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    tickets = f"{API}/workspaces/{wid}/tickets"

    inbox = client.post(
        tickets + "/inboxes", headers=headers,
        json={"name": "Website desk", "channel": "web_form", "slug": "website-desk"},
    )
    assert inbox.status_code == 201, inbox.text
    inbox_id = inbox.json()["id"]

    site = client.post(
        f"{API}/workspaces/{wid}/visitor-sites", headers=headers,
        json={"name": "Website widget", "inbox_id": inbox_id},
    )
    assert site.status_code == 201, site.text
    issued = site.json()
    assert issued["token"].startswith("vc_")
    assert issued["inbox_id"] == inbox_id
    listing = client.get(f"{API}/workspaces/{wid}/visitor-sites", headers=headers)
    assert listing.status_code == 200, listing.text
    assert all("token" not in row for row in listing.json())

    # A visitor cannot invent a channel: the body schema forbids extra fields.
    bad = client.post(
        f"{API}/public/visitor-conversations/{issued['token']}/start",
        json={"visitor_name": "Ada", "visitor_email": "ada@example.com",
              "message": "Hello", "origin_channel": "whatsapp"},
    )
    assert bad.status_code == 422

    started = client.post(
        f"{API}/public/visitor-conversations/{issued['token']}/start",
        json={"visitor_name": "Ada", "visitor_email": "ada@example.com",
              "message": "What are your plans?"},
    )
    assert started.status_code == 201, started.text
    conversation = started.json()
    cid = conversation["conversation_id"]
    assert conversation["origin_channel"] == "web_form"
    assert conversation["inbox_id"] == inbox_id
    assert conversation["status"] == "open"

    # The agent inbox sees the real conversation by inbox and by channel.
    by_inbox = client.get(tickets + f"/inboxes/{inbox_id}/tickets", headers=headers)
    assert by_inbox.status_code == 200, by_inbox.text
    assert [row["id"] for row in by_inbox.json()] == [cid]
    by_channel = client.get(tickets + "?channel=web_form", headers=headers)
    assert [row["id"] for row in by_channel.json()] == [cid]
    detail = client.get(tickets + f"/{cid}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["ticket"]["origin_channel"] == "web_form"

    messages = client.get(tickets + f"/{cid}/messages", headers=headers)
    assert messages.status_code == 200, messages.text
    assert len(messages.json()) == 1
    first = messages.json()[0]
    assert first["channel"] == "web_form" and first["direction"] == "inbound"
    assert first["body"] == "What are your plans?"

    reply = client.post(
        f"{API}/public/visitor-conversations/{issued['token']}/threads/{cid}/messages",
        json={"message": "I also need pricing."},
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["origin_channel"] == "web_form"
    messages = client.get(tickets + f"/{cid}/messages", headers=headers).json()
    assert [row["body"] for row in messages] == ["What are your plans?", "I also need pricing."]

    # The conversation cannot be reached through another site's token.
    other_site = client.post(
        f"{API}/workspaces/{wid}/visitor-sites", headers=headers,
        json={"name": "Other widget", "inbox_id": inbox_id},
    )
    assert other_site.status_code == 201, other_site.text
    cross = client.post(
        f"{API}/public/visitor-conversations/{other_site.json()['token']}/threads/{cid}/messages",
        json={"message": "cross"},
    )
    assert cross.status_code in (401, 404)

    # Revocation closes the visitor entry point but keeps the real conversation.
    removed = client.delete(
        f"{API}/workspaces/{wid}/visitor-sites/{issued['id']}", headers=headers
    )
    assert removed.status_code == 200, removed.text
    after_revoke = client.post(
        f"{API}/public/visitor-conversations/{issued['token']}/start",
        json={"visitor_name": "Bob", "visitor_email": "bob@example.com", "message": "Hi"},
    )
    assert after_revoke.status_code == 401
    assert client.get(tickets + f"/{cid}/messages", headers=headers).json() == messages

    contact = db_session.execute(
        select(Contact).where(Contact.workspace_id == wid, Contact.email == "ada@example.com")
    ).scalar_one()
    assert contact.source == "visitor_conversation"
    events = set(
        db_session.execute(select(Event.event_type).where(Event.workspace_id == wid))
        .scalars().all()
    )
    assert {VISITOR_SITE_CREATED, VISITOR_SITE_REVOKED, TICKET_CREATED,
            VISITOR_CONVERSATION_STARTED, TICKET_MESSAGE_ADDED,
            VISITOR_MESSAGE_ADDED} <= events

    # The UI renders the stored origin, not a hardcoded channel badge.
    # WhatsApp is now a legitimate local-delivery channel elsewhere in the
    # client, so the regression check is scoped to the two ticket views.
    source = APP_JS.read_text(encoding="utf-8")
    assert source.count("esc(cap(t.origin_channel || 'local'))") == 1
    assert source.count("esc(cap(ticket.origin_channel || 'local'))") == 1
    inbox_view = source[
        source.index("async function loadInbox("):source.index("function supportOpButton(")
    ]
    detail_view = source[
        source.index("async function loadTicketDetail("):source.index("function money(")
    ]
    assert "whatsapp" not in inbox_view.lower()
    assert "whatsapp" not in detail_view.lower()
