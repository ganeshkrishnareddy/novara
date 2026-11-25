"""Named acceptance tests for the Papermark P1 document-security rows.

PM-040 (secret vault), PM-156 (encrypted file at rest), PM-045 (per-view
watermark) and PM-117 (signed outgoing document webhook) are all exercised
through the real FastAPI app in the in-memory SQLite fixture. Assertions read
persisted rows, real response bytes and real audit events. The webhook test
uses a loopback HTTPServer only; no external provider or real message is sent.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy import select

from novara_core.models import Event
from novara_core.modules import document_security as sec
from novara_core.modules import documents
from novara_core.modules.email_campaigns import WebhookDelivery, webhook_signature

from .conftest import auth, bootstrap


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


# Distinct 32-byte keys so a wrong-key decrypt is detectable.
K1 = hashlib.sha256(b"papermark-test-key-1").digest()
K2 = hashlib.sha256(b"papermark-test-key-2").digest()
K3 = hashlib.sha256(b"papermark-test-key-wrong").digest()
KEYS_K1 = f"k1:{_b64(K1)}:active"
KEYS_K2 = f"k1:{_b64(K1)},k2:{_b64(K2)}:active"


def _setup(client, name: str, email: str) -> tuple[str, dict]:
    tokens = bootstrap(client, name, email)
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid: str) -> str:
    return f"/api/v1/workspaces/{wid}/documents/security"


def _doc(client, wid: str, headers: dict, title: str = "Security doc") -> dict:
    response = client.post(
        f"/api/v1/workspaces/{wid}/documents",
        headers=headers,
        json={"title": title, "doc_type": "pdf", "storage_path": "metadata://security/doc.pdf"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _event_types(db, wid: str) -> set[str]:
    return set(
        db.execute(select(Event.event_type).where(Event.workspace_id == wid)).scalars().all()
    )


def _doc_snapshot(db, document_id: str) -> dict:
    row = db.get(documents.Document, document_id)
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


# ---------------------------------------------------------------------------
# PM-040 — document password encryption key / secret vault
# ---------------------------------------------------------------------------


def test_pm040_secret_vault_hides_plaintext_and_rotates_named_key(client, db_session, monkeypatch):
    """PM-040: no DB/API leak, active-key rotation preserves the secret."""
    monkeypatch.setenv(sec.KEY_ENV, KEYS_K1)
    wid, headers = _setup(client, "Vault", "vault@example.com")
    secret = "UNLOCK-SECRET-9f3a7c1e-DO-NOT-LEAK"

    created = client.post(
        _base(wid) + "/secrets", headers=headers,
        json={"name": "pdf-unlock", "value": secret},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert set(body) == {"id", "name", "key_id"}, body
    assert body["key_id"] == "k1"
    assert secret not in created.text

    row = db_session.get(sec.DocumentSecret, body["id"])
    assert row is not None
    assert secret not in row.ciphertext
    assert "UNLOCK-SECRET" not in row.ciphertext
    assert row.key_id == "k1"
    assert sec.decrypt_secret(row.ciphertext) == secret

    listing = client.get(_base(wid) + "/secrets", headers=headers)
    assert listing.status_code == 200, listing.text
    assert [entry["id"] for entry in listing.json()] == [body["id"]]
    assert secret not in listing.text
    assert all("ciphertext" not in entry and "value" not in entry for entry in listing.json())

    # Promote k2 to active while keeping k1 readable, then rotate every row.
    monkeypatch.setenv(sec.KEY_ENV, KEYS_K2)
    rotated = client.post(_base(wid) + "/secrets/rotate", headers=headers)
    assert rotated.status_code == 200, rotated.text
    assert rotated.json() == {"rotated": 1, "key_id": "k2"}

    db_session.refresh(row)
    assert row.key_id == "k2"
    assert row.rotated_at is not None
    assert secret not in row.ciphertext
    assert sec.decrypt_secret(row.ciphertext) == secret

    # Same key id, different key bytes: authentication must fail closed.
    monkeypatch.setenv(sec.KEY_ENV, f"k2:{_b64(K3)}:active")
    with pytest.raises(ValueError):
        sec.decrypt_secret(row.ciphertext)

    assert {sec.DOCUMENT_SECRET_STORED, sec.DOCUMENT_SECRET_ROTATED} <= _event_types(db_session, wid)


# ---------------------------------------------------------------------------
# PM-156 — encryption at rest plus verified transport/security headers
# ---------------------------------------------------------------------------


def test_pm156_encrypted_file_bytes_at_rest_and_transport_headers(client, db_session):
    """PM-156: only ciphertext is stored; download restores bytes with headers."""
    wid, headers = _setup(client, "AtRest", "atrest@example.com")
    document = _doc(client, wid, headers)
    plaintext = b"%PDF-1.7\nCONFIDENTIAL-BYTES-KEEP-OUT-OF-DB\n%%EOF\n"

    uploaded = client.post(
        _base(wid) + "/encrypted-files",
        headers=headers,
        files={"file": ("secret.pdf", plaintext, "application/pdf")},
        data={"document_id": document["id"], "name": "secret.pdf"},
    )
    assert uploaded.status_code == 201, uploaded.text
    metadata = uploaded.json()
    assert "ciphertext" not in metadata and plaintext.decode() not in uploaded.text

    row = db_session.get(sec.EncryptedDocumentBlob, metadata["id"])
    assert row is not None
    assert b"CONFIDENTIAL-BYTES" not in row.ciphertext.encode("ascii")
    assert plaintext not in row.ciphertext.encode("ascii")
    assert row.plaintext_checksum_sha256 == hashlib.sha256(plaintext).hexdigest()
    assert row.size_bytes == len(plaintext)
    assert sec._decrypt_bytes(row.ciphertext) == plaintext

    downloaded = client.get(
        _base(wid) + f"/encrypted-files/{metadata['id']}/download", headers=headers
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == plaintext
    assert downloaded.headers["content-type"].startswith("application/pdf")
    assert 'attachment; filename="secret.pdf"' == downloaded.headers["content-disposition"]
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert downloaded.headers["x-frame-options"] == "DENY"
    assert downloaded.headers["referrer-policy"] == "no-referrer"
    assert "content-security-policy" in downloaded.headers
    assert documents.DOCUMENT_DOWNLOADED in _event_types(db_session, wid)

    # A corrupted checksum must never be treated as a successful download.
    row.plaintext_checksum_sha256 = "0" * 64
    db_session.commit()
    assert client.get(
        _base(wid) + f"/encrypted-files/{metadata['id']}/download", headers=headers
    ).status_code == 500


# ---------------------------------------------------------------------------
# PM-045 — dynamic watermarking attributable to a viewer and view
# ---------------------------------------------------------------------------


def test_pm045_watermark_overlay_is_per_viewer_attributed_and_escaped(client, db_session):
    """PM-045: each view gets its own tiled SVG; the document stays untouched."""
    wid, headers = _setup(client, "Watermarks", "watermark@example.com")
    document = _doc(client, wid, headers)
    before = _doc_snapshot(db_session, document["id"])

    alice = client.post(
        _base(wid) + f"/documents/{document['id']}/watermark-views",
        headers=headers,
        json={"viewer_email": "alice@example.com", "viewer_name": "Alice"},
    )
    bob = client.post(
        _base(wid) + f"/documents/{document['id']}/watermark-views",
        headers=headers,
        json={"viewer_email": "bob@example.com", "viewer_name": "Bob"},
    )
    assert alice.status_code == 201, alice.text
    assert bob.status_code == 201, bob.text
    a, b = alice.json(), bob.json()
    assert a["id"] != b["id"] and a["view_token"] != b["view_token"]
    assert a["viewer_email"] == "alice@example.com"
    assert b["viewer_email"] == "bob@example.com"
    assert a["id"] in a["watermark_text"] and "UTC" in a["watermark_text"]
    assert a["viewer_email"] in a["watermark_text"]

    overlay_a = client.get(_base(wid) + f"/watermark-views/{a['view_token']}/overlay", headers=headers)
    overlay_b = client.get(_base(wid) + f"/watermark-views/{b['view_token']}/overlay", headers=headers)
    assert overlay_a.status_code == 200 and overlay_b.status_code == 200
    assert overlay_a.headers["content-type"].startswith("image/svg+xml")
    assert overlay_a.text.startswith("<svg") and "</svg>" in overlay_a.text
    assert overlay_a.text.count("<text") == 4  # tiled on every page of the overlay
    assert a["viewer_email"] in overlay_a.text and a["id"] in overlay_a.text
    assert b["viewer_email"] not in overlay_a.text and b["id"] not in overlay_a.text
    assert b["viewer_email"] in overlay_b.text and b["id"] in overlay_b.text
    assert a["viewer_email"] not in overlay_b.text
    assert overlay_a.text != overlay_b.text

    # Untrusted viewer text is XML-escaped, never executable markup.
    hostile = client.post(
        _base(wid) + f"/documents/{document['id']}/watermark-views",
        headers=headers,
        json={"viewer_email": "eve@example.com", "viewer_name": "<script>alert(1)</script>"},
    )
    assert hostile.status_code == 201, hostile.text
    hostile_svg = client.get(
        _base(wid) + f"/watermark-views/{hostile.json()['view_token']}/overlay", headers=headers
    ).text
    assert "&lt;script&gt;" in hostile_svg and "<script>" not in hostile_svg

    assert sec.WATERMARK_VIEW_CREATED in _event_types(db_session, wid)
    assert _doc_snapshot(db_session, document["id"]) == before  # no baked-in watermark


# ---------------------------------------------------------------------------
# PM-117 — signed outgoing document webhook to a real loopback subscriber
# ---------------------------------------------------------------------------


def test_pm117_document_shared_webhook_reaches_loopback_subscriber_and_verifies(client, db_session):
    """PM-117: a local subscriber verifies the real HMAC and delivery log."""
    wid, headers = _setup(client, "Webhooks", "webhook@example.com")
    document = _doc(client, wid, headers)
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
            received.append({
                "body": body,
                "signature": self.headers.get("X-NOVARA-Signature"),
                "delivery_id": self.headers.get("X-NOVARA-Delivery"),
                "event": self.headers.get("X-NOVARA-Event"),
            })
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        secret = "a-long-webhook-signing-secret-for-tests"
        created = client.post(
            _base(wid) + "/webhook-subscriptions",
            headers=headers,
            json={
                "name": "document-events",
                "url": f"http://127.0.0.1:{port}/hook",
                "secret": secret,
                "event_types": [sec.DOCUMENT_SHARED],
            },
        )
        assert created.status_code == 201, created.text
        assert "secret" not in created.json() and "secret" not in created.text
        subscription_id = created.json()["id"]

        delivered = client.post(
            _base(wid) + f"/documents/{document['id']}/signed-share-delivery",
            headers=headers,
            json={"subscription_id": subscription_id, "recipient_email": "buyer@example.com"},
        )
        assert delivered.status_code == 200, delivered.text
        result = delivered.json()
        assert result["event"] == sec.DOCUMENT_SHARED
        assert result["status"] == "delivered" and result["attempts"] == 1
        assert len(received) == 1
        request = received[0]
        assert request["event"] == sec.DOCUMENT_SHARED
        assert request["delivery_id"] == result["delivery_id"]

        body = json.loads(request["body"])
        assert body["delivery_id"] == result["delivery_id"]
        assert body["event"] == sec.DOCUMENT_SHARED
        assert body["workspace_id"] == wid
        assert body["payload"]["document_id"] == document["id"]
        assert body["payload"]["recipient_email"] == "buyer@example.com"

        expected = webhook_signature(secret, request["delivery_id"], request["body"])
        assert request["signature"] == expected
        assert hmac.compare_digest(expected, request["signature"])
        tampered = expected[:-1] + ("0" if expected[-1] != "0" else "1")
        assert not hmac.compare_digest(tampered, expected)
        assert webhook_signature(secret + "-wrong", request["delivery_id"], request["body"]) != expected

        logs = db_session.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.workspace_id == wid,
                WebhookDelivery.subscription_id == subscription_id,
            )
        ).scalars().all()
        assert [log.status for log in logs] == ["delivered"]
        assert logs[0].signature_prefix == expected[:16]
        assert sec.DOCUMENT_SHARED in _event_types(db_session, wid)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Cross-cutting guarantees: workspace isolation and strict sanitized inputs
# ---------------------------------------------------------------------------


def test_document_security_rows_are_workspace_isolated(client, db_session, monkeypatch):
    """PM-040/045/156: another workspace cannot read rows or tokens by id."""
    monkeypatch.setenv(sec.KEY_ENV, KEYS_K1)
    wid, headers = _setup(client, "Isolation", "isolation@example.com")
    document = _doc(client, wid, headers)
    secret = client.post(
        _base(wid) + "/secrets", headers=headers, json={"name": "isolation-secret", "value": "s3cr3t"}
    ).json()
    blob = client.post(
        _base(wid) + "/encrypted-files", headers=headers,
        files={"file": ("f.bin", b"isolation bytes", "application/octet-stream")},
        data={"document_id": document["id"]},
    ).json()
    view = client.post(
        _base(wid) + f"/documents/{document['id']}/watermark-views", headers=headers,
        json={"viewer_email": "viewer@example.com"},
    ).json()

    other = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other isolation"})
    assert other.status_code == 200, other.text
    other_wid, other_headers = other.json()["workspace_id"], auth(other.json()["access_token"])

    assert client.get(_base(other_wid) + "/secrets", headers=headers).status_code == 403
    assert client.get(_base(wid) + "/secrets", headers=other_headers).status_code == 403
    assert client.get(_base(other_wid) + "/secrets", headers=other_headers).json() == []
    assert client.get(
        _base(other_wid) + f"/encrypted-files/{blob['id']}/download", headers=other_headers
    ).status_code == 404
    assert client.get(
        _base(wid) + f"/encrypted-files/{blob['id']}/download", headers=other_headers
    ).status_code == 403
    assert client.get(
        _base(other_wid) + f"/watermark-views/{view['view_token']}/overlay", headers=other_headers
    ).status_code == 404
    assert client.get(
        _base(other_wid) + f"/watermark-views/{view['view_token']}/overlay", headers=headers
    ).status_code == 403
    assert secret["id"] and db_session.get(sec.DocumentSecret, secret["id"]).workspace_id == wid


def test_document_security_validators_reject_extra_fields_and_wrong_events(client, db_session, monkeypatch):
    """Sanitized schemas reject extra fields, bad URLs and non-document events."""
    monkeypatch.setenv(sec.KEY_ENV, KEYS_K1)
    wid, headers = _setup(client, "Validation", "validation@example.com")
    document = _doc(client, wid, headers)

    assert client.post(
        _base(wid) + "/secrets", headers=headers,
        json={"name": "bad", "value": "secret", "extra": 1},
    ).status_code == 422
    assert client.post(
        _base(wid) + f"/documents/{document['id']}/watermark-views", headers=headers,
        json={"viewer_email": "v@example.com", "extra": True},
    ).status_code == 422
    assert client.post(
        _base(wid) + "/webhook-subscriptions", headers=headers,
        json={
            "name": "bad-events", "url": "http://127.0.0.1:9/hook",
            "secret": "a-long-signing-secret", "event_types": ["broadcast.sent"],
        },
    ).status_code == 422
    assert client.post(
        _base(wid) + "/webhook-subscriptions", headers=headers,
        json={
            "name": "bad-url", "url": "ftp://127.0.0.1/hook",
            "secret": "a-long-signing-secret", "event_types": [sec.DOCUMENT_SHARED],
        },
    ).status_code == 422

    # A valid subscription with no delivery still audits subscription creation.
    created = client.post(
        _base(wid) + "/webhook-subscriptions", headers=headers,
        json={
            "name": "valid-doc-hook", "url": "http://127.0.0.1:9/hook",
            "secret": "a-long-signing-secret", "event_types": [sec.DOCUMENT_VIEWED],
        },
    )
    assert created.status_code == 201, created.text
    assert "secret" not in created.text
    assert sec.DOCUMENT_WEBHOOK_SUBSCRIPTION_CREATED in _event_types(db_session, wid)
