"""Named acceptance tests for the P0 Mautic consent and identity cluster.

MT-019: signed unsubscribe / resubscribe / global do-not-contact / preference
centre links must update real consent state and be enforced before a recipient
is queued. MT-113: NOVARA's contact id stays authoritative while an external
system's id is preserved with provenance. No external email is ever sent.
"""

from __future__ import annotations

from sqlalchemy import select

from novara_core.events import CONTACT_EXTERNAL_ID_UPDATED
from novara_core.models import Contact, Event
from novara_core.modules import email_campaigns as mail

from .conftest import auth, bootstrap


def _contact(client, wid, headers, email="visitor@example.com", name="Visitor"):
    response = client.post(
        f"/api/v1/workspaces/{wid}/contacts", headers=headers,
        json={"email": email, "full_name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _broadcast(client, wid, headers, name="News"):
    response = client.post(
        f"/api/v1/workspaces/{wid}/email/broadcasts", headers=headers,
        json={"name": name, "subject": "Hello", "body": "Local only"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _links(client, wid, headers, contact_id):
    response = client.get(
        f"/api/v1/workspaces/{wid}/email/consent-links", headers=headers,
        params={"contact_id": contact_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _latest_consent(db_session, wid, contact_id, channel):
    return db_session.execute(
        select(mail.ConsentRecord).where(
            mail.ConsentRecord.workspace_id == wid,
            mail.ConsentRecord.contact_id == contact_id,
            mail.ConsentRecord.channel == channel,
        ).order_by(mail.ConsentRecord.recorded_at.desc())
    ).scalars().first()


# ---------------------------------------------------------------------------
# MT-019 — signed consent links that update consent and are enforced
# ---------------------------------------------------------------------------


def test_unsubscribe_link_updates_consent_and_blocks_future_recipients(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = _contact(client, wid, headers)
    cid = contact["id"]

    links = _links(client, wid, headers, cid)["links"]
    assert set(links) == set(mail.CONSENT_ACTIONS)
    unsub = client.post(
        f"/api/v1/workspaces/{wid}/email/unsubscribe",
        json={"token": links["unsubscribe"]["token"]},
    )
    assert unsub.status_code == 200, unsub.text

    suppression = client.get(
        f"/api/v1/workspaces/{wid}/email/suppression", headers=headers
    ).json()
    assert any(row["email"] == contact["email"] for row in suppression)

    consent = _latest_consent(db_session, wid, cid, "email")
    assert consent is not None and consent.granted is False
    assert consent.source == "unsubscribe"

    prefs = client.get(
        f"/api/v1/workspaces/{wid}/email/preferences",
        params={"token": links["preferences"]["token"]},
    )
    assert prefs.status_code == 200, prefs.text
    assert prefs.json()["channels"]["email"] is False

    # Consent is enforced before a contact is queued, with no second manual step.
    broadcast = _broadcast(client, wid, headers)
    added = client.post(
        f"/api/v1/workspaces/{wid}/email/broadcasts/{broadcast['id']}/recipients",
        headers=headers, json={"contact_ids": [cid]},
    ).json()
    assert added == {"added": 0, "skipped": 1}

    types = [e.event_type for e in db_session.execute(
        select(Event).where(Event.workspace_id == wid)
    ).scalars().all()]
    assert types.count(mail.UNSUBSCRIBE_RECORDED) == 1
    assert types.count(mail.CONSENT_RECORDED) >= 1


def test_resubscribe_and_dnc_links_are_signed_scoped_and_reversible(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = _contact(client, wid, headers)
    cid = contact["id"]
    links = _links(client, wid, headers, cid)["links"]

    # A tampered token and a token for another workspace are both rejected.
    tampered = links["dnc"]["token"][:-1] + ("a" if links["dnc"]["token"][-1] != "a" else "b")
    assert client.post(f"/api/v1/workspaces/{wid}/email/dnc",
                       json={"token": tampered}).status_code == 400
    other = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other"}).json()
    assert client.post(f"/api/v1/workspaces/{other['workspace_id']}/email/dnc",
                       json={"token": links["dnc"]["token"]}).status_code == 403

    dnc = client.post(f"/api/v1/workspaces/{wid}/email/dnc",
                      json={"token": links["dnc"]["token"]})
    assert dnc.status_code == 200 and dnc.json()["do_not_contact"] is True
    refreshed = client.get(f"/api/v1/workspaces/{wid}/contacts/{cid}", headers=headers).json()
    assert refreshed["do_not_contact"] is True
    global_consent = _latest_consent(db_session, wid, cid, "*")
    assert global_consent is not None and global_consent.granted is False

    broadcast = _broadcast(client, wid, headers, "After DNC")
    added = client.post(
        f"/api/v1/workspaces/{wid}/email/broadcasts/{broadcast['id']}/recipients",
        headers=headers, json={"contact_ids": [cid]},
    ).json()
    assert added == {"added": 0, "skipped": 1}

    resub = client.post(f"/api/v1/workspaces/{wid}/email/resubscribe",
                        json={"token": links["resubscribe"]["token"]})
    assert resub.status_code == 200 and resub.json()["resubscribed"] is True
    refreshed = client.get(f"/api/v1/workspaces/{wid}/contacts/{cid}", headers=headers).json()
    assert refreshed["do_not_contact"] is False
    assert _latest_consent(db_session, wid, cid, "email").granted is True
    suppression = client.get(
        f"/api/v1/workspaces/{wid}/email/suppression", headers=headers
    ).json()
    assert all(row["email"] != contact["email"] for row in suppression)

    broadcast = _broadcast(client, wid, headers, "After resubscribe")
    added = client.post(
        f"/api/v1/workspaces/{wid}/email/broadcasts/{broadcast['id']}/recipients",
        headers=headers, json={"contact_ids": [cid]},
    ).json()
    assert added == {"added": 1, "skipped": 0}


def test_preference_centre_updates_only_supported_channels(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = _contact(client, wid, headers)
    token = _links(client, wid, headers, contact["id"])["links"]["preferences"]["token"]

    updated = client.post(
        f"/api/v1/workspaces/{wid}/email/preferences",
        json={"token": token, "channels": {"sms": False}},
    )
    assert updated.status_code == 200, updated.text
    assert _latest_consent(db_session, wid, contact["id"], "sms").granted is False
    assert _latest_consent(db_session, wid, contact["id"], "email") is None

    invalid = client.post(
        f"/api/v1/workspaces/{wid}/email/preferences",
        json={"token": token, "channels": {"carrier_pigeon": False}},
    )
    assert invalid.status_code == 422

    # While global DNC is active the preference centre cannot override it.
    dnc_token = _links(client, wid, headers, contact["id"])["links"]["dnc"]["token"]
    assert client.post(f"/api/v1/workspaces/{wid}/email/dnc",
                       json={"token": dnc_token}).status_code == 200
    blocked = client.post(
        f"/api/v1/workspaces/{wid}/email/preferences",
        json={"token": token, "channels": {"email": True}},
    )
    assert blocked.status_code == 409


def test_dnc_after_unsubscribe_reuses_one_suppression_entry(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = _contact(client, wid, headers)
    links = _links(client, wid, headers, contact["id"])["links"]
    assert client.post(f"/api/v1/workspaces/{wid}/email/unsubscribe",
                       json={"token": links["unsubscribe"]["token"]}).status_code == 200
    assert client.post(f"/api/v1/workspaces/{wid}/email/dnc",
                       json={"token": links["dnc"]["token"]}).status_code == 200
    rows = [row for row in client.get(
        f"/api/v1/workspaces/{wid}/email/suppression", headers=headers
    ).json() if row["email"] == contact["email"]]
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# MT-113 — external identity provenance without a second source of truth
# ---------------------------------------------------------------------------


def test_external_id_is_preserved_without_replacing_novara_identity(client, db_session):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    contact = _contact(client, wid, headers, email="sync@example.com", name="Sync Person")
    cid = contact["id"]

    patched = client.patch(
        f"/api/v1/workspaces/{wid}/contacts/{cid}", headers=headers,
        json={"external_id": "mautic-42", "external_source": "mautic"},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["id"] == cid
    assert body["external_id"] == "mautic-42"
    assert body["external_source"] == "mautic"

    changed = client.patch(
        f"/api/v1/workspaces/{wid}/contacts/{cid}", headers=headers,
        json={"external_id": "mautic-43"},
    )
    assert changed.status_code == 200
    assert changed.json()["external_source"] == "mautic"
    stored = db_session.execute(select(Contact).where(Contact.id == cid)).scalar_one()
    assert stored.external_id == "mautic-43"

    events = db_session.execute(
        select(Event).where(
            Event.workspace_id == wid,
            Event.event_type == CONTACT_EXTERNAL_ID_UPDATED,
        )
    ).scalars().all()
    assert len(events) == 2
    assert events[0].payload["external_id"] == "mautic-42"
    assert events[1].payload["external_id"] == "mautic-43"


def test_external_identity_validation_and_workspace_scoping(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    first = _contact(client, wid, headers, email="one@example.com")
    second = _contact(client, wid, headers, email="two@example.com")

    path = f"/api/v1/workspaces/{wid}/contacts/{first['id']}"
    assert client.patch(path, headers=headers,
                        json={"external_id": "x"}).status_code == 422
    assert client.patch(path, headers=headers,
                        json={"external_source": "mautic"}).status_code == 422
    assert client.patch(path, headers=headers,
                        json={"external_id": "  ", "external_source": "mautic"}).status_code == 422

    assert client.patch(path, headers=headers, json={
        "external_id": "shared", "external_source": "mautic",
    }).status_code == 200
    clash = client.patch(
        f"/api/v1/workspaces/{wid}/contacts/{second['id']}", headers=headers,
        json={"external_id": "shared", "external_source": "mautic"},
    )
    assert clash.status_code == 409

    # The same external id under a different source, or in another workspace,
    # is a different identity and is allowed.
    other_source = client.patch(
        f"/api/v1/workspaces/{wid}/contacts/{second['id']}", headers=headers,
        json={"external_id": "shared", "external_source": "crm_import"},
    )
    assert other_source.status_code == 200
    other_ws = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other"}).json()
    third = _contact(client, other_ws["workspace_id"], auth(other_ws["access_token"]),
                     email="three@example.com")
    other_ws_patch = client.patch(
        f"/api/v1/workspaces/{other_ws['workspace_id']}/contacts/{third['id']}",
        headers=auth(other_ws["access_token"]),
        json={"external_id": "shared", "external_source": "mautic"},
    )
    assert other_ws_patch.status_code == 200

    # Foreign lookups stay inside their own workspace.
    assert client.get(f"/api/v1/workspaces/{other_ws['workspace_id']}/contacts/{first['id']}",
                      headers=auth(other_ws["access_token"])).status_code == 404
    assert client.get(f"/api/v1/workspaces/{wid}/email/consent-links", headers=headers,
                      params={"contact_id": third["id"]}).status_code == 404
