"""Named acceptance test for CW-108 (support outbound webhooks).

The delivery is a real HTTP request to a loopback receiver; no mock counts as
delivery. The receiver fails the first two attempts so retry evidence is real,
and the subscription URL goes through the shared allow-list validator.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sqlalchemy import select

from novara_core.modules.email_campaigns import (
    BROADCAST_SENT,
    WEBHOOK_DELIVERED,
    WebhookDelivery,
    deliver_webhook,
    webhook_signature,
)
from novara_core.models import Event

from .conftest import auth, bootstrap

API = "/api/v1"


def _event_types(db_session, wid: str) -> set[str]:
    return set(
        db_session.execute(
            select(Event.event_type).where(Event.workspace_id == wid)
        ).scalars().all()
    )


def test_cw108_signed_webhook_retries_and_is_allow_listed(client, db_session):
    """A local event yields one signed callback with durable retry evidence."""
    tokens = bootstrap(client, "CW108", "cw108-owner@example.com")
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    email_base = f"{API}/workspaces/{wid}/email"

    # Host allow-list is enforced at configuration time: link-local and
    # arbitrary external destinations are rejected before any request is made.
    rejected = client.post(
        email_base + "/webhooks",
        headers=headers,
        json={
            "name": "blocked", "url": "http://169.254.169.254/latest/meta-data",
            "secret": "a-long-webhook-signing-secret", "event_types": [BROADCAST_SENT],
        },
    )
    assert rejected.status_code == 422, rejected.text

    received: list[dict] = []

    class RetryReceiver(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            received.append({
                "body": body,
                "signature": self.headers.get("X-NOVARA-Signature"),
                "delivery_id": self.headers.get("X-NOVARA-Delivery"),
                "event": self.headers.get("X-NOVARA-Event"),
            })
            if len(received) < 3:
                self.send_response(503)
            else:
                self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), RetryReceiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        secret = "a-long-webhook-signing-secret-for-cw108"
        created = client.post(
            email_base + "/webhooks",
            headers=headers,
            json={
                "name": "support-events",
                "url": f"http://127.0.0.1:{port}/hook",
                "secret": secret,
                "event_types": [BROADCAST_SENT],
            },
        )
        assert created.status_code == 201, created.text
        assert "secret" not in created.json() and "secret" not in created.text
        subscription_id = created.json()["id"]

        result = deliver_webhook(
            db_session,
            workspace_id=wid,
            subscription_id=subscription_id,
            event_type=BROADCAST_SENT,
            payload={"ticket_id": "ticket-cw108", "event": "ticket.resolved"},
        )
        assert result["status"] == "delivered", result
        assert result["attempts"] == 3
        assert len(received) == 3
        assert len({row["delivery_id"] for row in received}) == 1
        assert result["delivery_id"] == received[0]["delivery_id"]
        assert all(row["event"] == BROADCAST_SENT for row in received)

        body = json.loads(received[-1]["body"])
        assert body["delivery_id"] == result["delivery_id"]
        assert body["event"] == BROADCAST_SENT
        assert body["workspace_id"] == wid
        assert body["payload"]["ticket_id"] == "ticket-cw108"
        expected = webhook_signature(secret, received[-1]["delivery_id"], received[-1]["body"])
        assert all(row["signature"] == expected for row in received)
        tampered = expected[:-1] + ("0" if expected[-1] != "0" else "1")
        assert tampered != expected

        logs = db_session.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.workspace_id == wid,
                WebhookDelivery.subscription_id == subscription_id,
            ).order_by(WebhookDelivery.attempt)
        ).scalars().all()
        assert [log.status for log in logs] == ["failed", "failed", "delivered"]
        assert [log.status_code for log in logs] == [503, 503, 200]
        assert all(log.signature_prefix == expected[:16] for log in logs)

        api_logs = client.get(
            email_base + f"/webhooks/{subscription_id}/deliveries", headers=headers
        )
        assert api_logs.status_code == 200, api_logs.text
        assert [row["attempt"] for row in api_logs.json()] == [1, 2, 3]
        assert WEBHOOK_DELIVERED in _event_types(db_session, wid)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
