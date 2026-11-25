"""Named acceptance test for CW-048 (multi-inbox routing).

The support module already owns the inbox table, membership and queue scoping;
this test proves the real API behaviour rather than relying on a route listing.
No external mailbox or provider is involved.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.main import API
from novara_core.models import Event
from novara_core.modules import support

from .conftest import auth, bootstrap


def _base(wid: str) -> str:
    return f"{API}/workspaces/{wid}/tickets"


def _signup_member(client, wid, owner_headers, email, role="support"):
    invite = client.post(
        f"{API}/workspaces/{wid}/invitations", headers=owner_headers,
        json={"email": email, "role": role},
    )
    assert invite.status_code == 200, invite.text
    registered = client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Password123!", "display_name": email.split("@")[0]},
    )
    assert registered.status_code == 200, registered.text
    accepted = client.post(
        f"{API}/invitations/accept",
        headers=auth(registered.json()["access_token"]),
        json={"token": invite.json()["invite_token"]},
    )
    assert accepted.status_code == 200, accepted.text
    token = accepted.json()["access_token"]
    me = client.get(f"{API}/auth/me", headers=auth(token))
    return auth(token), me.json()["user"]["id"]


def test_cw048_inbox_scoped_queues_and_agent_membership(client, db_session):
    """Tickets are scoped to an inbox and only permitted agents see its queue."""
    tokens = bootstrap(client, "CW048", "cw048-owner@example.com")
    wid, owner = tokens["workspace_id"], auth(tokens["access_token"])
    base = _base(wid)

    sales = client.post(
        base + "/inboxes", headers=owner,
        json={"name": "Sales desk", "channel": "web_form", "slug": "sales-desk"},
    )
    assert sales.status_code == 201, sales.text
    billing = client.post(
        base + "/inboxes", headers=owner,
        json={"name": "Billing desk", "channel": "email", "slug": "billing-desk"},
    )
    assert billing.status_code == 201, billing.text
    sales_id, billing_id = sales.json()["id"], billing.json()["id"]
    assert sales.json()["channel"] == "web_form"
    assert billing.json()["channel"] == "email"

    sales_headers, sales_user = _signup_member(
        client, wid, owner, "cw048-sales@example.com"
    )
    billing_headers, billing_user = _signup_member(
        client, wid, owner, "cw048-billing@example.com"
    )
    added = client.post(
        base + f"/inboxes/{sales_id}/agents", headers=owner,
        json={"user_id": sales_user},
    )
    assert added.status_code == 201, added.text
    added = client.post(
        base + f"/inboxes/{billing_id}/agents", headers=owner,
        json={"user_id": billing_user},
    )
    assert added.status_code == 201, added.text

    sales_ticket = client.post(
        base, headers=owner,
        json={"subject": "Sales question", "body": "Pricing", "inbox_id": sales_id},
    )
    assert sales_ticket.status_code == 201, sales_ticket.text
    billing_ticket = client.post(
        base, headers=owner,
        json={"subject": "Invoice question", "body": "Receipt", "inbox_id": billing_id},
    )
    assert billing_ticket.status_code == 201, billing_ticket.text
    sales_ticket_id, billing_ticket_id = sales_ticket.json()["id"], billing_ticket.json()["id"]

    # A support agent sees only the inboxes and queues they belong to.
    assert [row["id"] for row in client.get(base + "/inboxes", headers=sales_headers).json()] == [sales_id]
    assert client.get(base + f"/inboxes/{billing_id}/tickets", headers=sales_headers).status_code == 403
    assert client.get(base + f"?inbox_id={billing_id}", headers=sales_headers).status_code == 403
    visible = client.get(base, headers=sales_headers).json()
    assert [row["id"] for row in visible] == [sales_ticket_id]
    assert [row["id"] for row in client.get(base + f"/inboxes/{sales_id}/tickets", headers=sales_headers).json()] == [sales_ticket_id]

    # The other agent is the exact mirror image.
    assert [row["id"] for row in client.get(base + "/inboxes", headers=billing_headers).json()] == [billing_id]
    assert [row["id"] for row in client.get(base, headers=billing_headers).json()] == [billing_ticket_id]
    assert client.get(base + f"/inboxes/{sales_id}/tickets", headers=billing_headers).status_code == 403

    # Workspace oversight remains explicit for owner/admin.
    all_ids = {row["id"] for row in client.get(base, headers=owner).json()}
    assert {sales_ticket_id, billing_ticket_id} <= all_ids
    assert len(client.get(base + "/inboxes", headers=owner).json()) == 2

    events = set(
        db_session.execute(
            select(Event.event_type).where(Event.workspace_id == wid)
        ).scalars().all()
    )
    assert support.INBOX_CREATED in events
    assert support.INBOX_AGENT_ADDED in events
