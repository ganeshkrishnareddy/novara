"""End-to-end runtime smoke test for a real NOVARA server.

Starts the actual ASGI app under uvicorn on a free local port with a throwaway
SQLite database, then drives it over HTTP exactly as the browser client would:
health, static client, API catalogue, first-run bootstrap, auth, and a full
CRM journey (contact -> lead -> task -> event timeline).

No external services, emails, or network calls beyond localhost are used.
No response bodies are logged: auth responses carry bearer tokens and secrets
must never appear in test output.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{label}: FAILED {detail}")
    print(f"  PASS {label}" + (f" ({detail})" if detail else ""))


def main() -> int:
    tmp_db = Path(tempfile.gettempdir()) / f"novara_runtime_smoke_{os.getpid()}.sqlite3"
    log = Path(tempfile.gettempdir()) / f"novara_runtime_smoke_{os.getpid()}.log"
    for path in (tmp_db, log):
        if path.exists():
            path.unlink()

    env = os.environ.copy()
    env["NOVARA_DB_PATH"] = str(tmp_db)
    port = _free_port()
    base = f"http://127.0.0.1:{port}"

    cmd = [
        sys.executable, "-m", "uvicorn", "novara_core.main:app",
        "--host", "127.0.0.1", "--port", str(port), "--no-access-log",
    ]
    with log.open("w", encoding="utf-8") as logfile:
        proc = subprocess.Popen(
            cmd, cwd=str(API_DIR), env=env,
            stdout=logfile, stderr=subprocess.STDOUT,
        )
        try:
            client = httpx.Client(base_url=base, timeout=10.0)
            healthy = False
            for _ in range(80):
                try:
                    probe = client.get("/health")
                    if probe.status_code == 200 and probe.json().get("status") == "ok":
                        healthy = True
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
            _check("server becomes healthy", healthy, f"GET /health on port {port}")

            print("\n[1] Static single-page client")
            index = client.get("/")
            _check("index.html served", index.status_code == 200 and "app.js" in index.text,
                   f"HTTP {index.status_code}")
            js = client.get("/app.js")
            _check("app.js served", js.status_code == 200 and len(js.content) > 1000,
                   f"{len(js.content)} bytes")
            css = client.get("/styles.css")
            _check("styles.css served", css.status_code == 200 and len(css.content) > 500,
                   f"{len(css.content)} bytes")

            print("\n[2] API catalogue")
            spec = client.get("/openapi.json").json()
            paths = spec.get("paths", {})
            _check("openapi has endpoints", len(paths) >= 40, f"{len(paths)} paths")
            for expected in (
                "/health", "/api/v1/auth/login",
                "/api/v1/workspaces/{workspace_id}/contacts",
                "/api/v1/workspaces/{workspace_id}/documents",
            ):
                _check(f"route {expected}", expected in paths)

            print("\n[3] First-run bootstrap and auth")
            boot = client.post("/api/v1/setup/bootstrap", json={
                "email": "owner@novara.local",
                "display_name": "Smoke Owner",
                "password": "Str0ng!Passw0rd",
                "workspace_name": "Smoke Workspace",
            })
            _check("bootstrap 200", boot.status_code == 200, f"HTTP {boot.status_code}")
            token = boot.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            me = client.get("/api/v1/auth/me", headers=headers)
            _check("authenticated /me", me.status_code == 200, f"HTTP {me.status_code}")
            ws = me.json()["workspace_id"]
            _check("owner role", me.json().get("role") == "owner")

            print("\n[4] Full CRM journey over HTTP")
            contact = client.post(f"/api/v1/workspaces/{ws}/contacts", headers=headers, json={
                "full_name": "Ada Lovelace",
                "email": "ada@example.com",
                "company_name": "Analytical Engines",
            })
            _check("create contact", contact.status_code == 201, f"HTTP {contact.status_code}")
            cid = contact.json()["id"]

            lead = client.post(f"/api/v1/workspaces/{ws}/leads", headers=headers, json={
                "contact_id": cid, "status": "new", "source": "website", "priority": "high",
            })
            _check("create lead", lead.status_code == 201, f"HTTP {lead.status_code}")
            lid = lead.json()["id"]
            _check("qualify lead", client.post(
                f"/api/v1/workspaces/{ws}/leads/{lid}/qualify", headers=headers).status_code == 200)
            _check("convert lead", client.post(
                f"/api/v1/workspaces/{ws}/leads/{lid}/convert", headers=headers).status_code == 200)

            task = client.post(f"/api/v1/workspaces/{ws}/tasks", headers=headers, json={
                "title": "Follow up with Ada", "contact_id": cid, "priority": "high",
            })
            _check("create task", task.status_code == 201, f"HTTP {task.status_code}")

            listed = client.get(f"/api/v1/workspaces/{ws}/contacts", headers=headers)
            _check("list contacts", listed.status_code == 200 and len(listed.json()) == 1,
                   f"{len(listed.json())} row(s)")

            events = client.get(f"/api/v1/workspaces/{ws}/events", headers=headers)
            _check("event timeline populated", events.status_code == 200 and len(events.json()) >= 4,
                   f"{len(events.json())} events")

            timeline = client.get(f"/api/v1/workspaces/{ws}/contacts/{cid}/timeline", headers=headers)
            _check("contact timeline populated", timeline.status_code == 200 and len(timeline.json()) >= 1,
                   f"{len(timeline.json())} events")

            print("\n[5] Notification center (P0)")
            intake = client.post(f"/api/v1/workspaces/{ws}/intake/website-form", headers=headers, json={
                "submission_id": "smoke-notification-001",
                "email": "visitor@example.com",
                "full_name": "Web Visitor",
            })
            _check("website intake creates a real notification", intake.status_code == 201,
                   f"HTTP {intake.status_code}")
            counts = client.get(f"/api/v1/workspaces/{ws}/notifications/counts", headers=headers)
            _check("notification counts", counts.status_code == 200 and counts.json()["unread"] >= 1,
                   f"HTTP {counts.status_code}")
            settings = client.get(f"/api/v1/workspaces/{ws}/notification-settings", headers=headers)
            _check("workspace notification settings", settings.status_code == 200 and settings.json()["timezone"] == "UTC",
                   f"HTTP {settings.status_code}")
            updated = client.put(f"/api/v1/workspaces/{ws}/notification-settings", headers=headers,
                                 json={"digest_enabled": True, "timezone": "Asia/Kolkata"})
            _check("settings persist", updated.status_code == 200 and updated.json()["digest_enabled"] is True,
                   f"HTTP {updated.status_code}")
            read_all = client.post(f"/api/v1/workspaces/{ws}/notifications/read-all", headers=headers)
            _check("bulk mark read", read_all.status_code == 200 and read_all.json()["unread"] == 0,
                   f"HTTP {read_all.status_code}")
            _check("real-time stream route registered",
                   f"/api/v1/workspaces/{{workspace_id}}/notifications/stream" in paths)

            print("\n[6] Customer inbox (P0)")
            identified = client.post(f"/api/v1/workspaces/{ws}/tickets/identify", headers=headers,
                                     json={"email": "support-visitor@example.com", "full_name": "Support Visitor"})
            _check("pre-chat identity reuses CRM contact", identified.status_code == 201,
                   f"HTTP {identified.status_code}")
            ticket = client.post(f"/api/v1/workspaces/{ws}/tickets", headers=headers, json={
                "subject": "Smoke support request", "body": "Question about onboarding",
                "contact_id": identified.json()["contact_id"],
                "origin_channel": "web_form", "conversation_type": "question",
                "priority": "urgent",
            })
            _check("conversation created with origin metadata",
                   ticket.status_code == 201 and ticket.json()["origin_channel"] == "web_form",
                   f"HTTP {ticket.status_code}")
            tid = ticket.json()["id"]
            reply = client.post(f"/api/v1/workspaces/{ws}/tickets/{tid}/messages", headers=headers,
                                json={"body": "Local reply only", "direction": "outbound", "channel": "local"})
            _check("reply stored with direction and channel",
                   reply.status_code == 201 and reply.json()["direction"] == "outbound",
                   f"HTTP {reply.status_code}")
            queue = client.get(f"/api/v1/workspaces/{ws}/tickets/counts", headers=headers)
            _check("queue counts reflect the ticket", queue.status_code == 200 and queue.json()["urgent"] == 1,
                   f"HTTP {queue.status_code}")
            assignees = client.get(f"/api/v1/workspaces/{ws}/tickets/assignees", headers=headers)
            _check("assignee list available to agents", assignees.status_code == 200 and len(assignees.json()) >= 1,
                   f"HTTP {assignees.status_code}")
            _check("inbox stream route registered",
                   f"/api/v1/workspaces/{{workspace_id}}/tickets/stream" in paths)

            print("\n[7] Work items and delivery states (P0)")
            states = client.post(f"/api/v1/workspaces/{ws}/projects/states", headers=headers,
                                 json={"name": "Smoke Review", "group": "in_progress", "position": 1})
            _check("configurable state created", states.status_code == 201,
                   f"HTTP {states.status_code}")
            done_state = client.post(f"/api/v1/workspaces/{ws}/projects/states", headers=headers,
                                     json={"name": "Smoke Done", "group": "done", "position": 2})
            _check("configurable done state created", done_state.status_code == 201,
                   f"HTTP {done_state.status_code}")
            project = client.post(f"/api/v1/workspaces/{ws}/projects", headers=headers,
                                  json={"name": "Smoke Delivery", "due_at": "2027-05-01T00:00:00Z"})
            _check("project created with due date",
                   project.status_code == 201 and project.json()["due_at"] is not None,
                   f"HTTP {project.status_code}")
            pid = project.json()["id"]
            item = client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/items", headers=headers,
                               json={"title": "Smoke work item", "status": "Smoke Review",
                                     "due_at": "2027-06-01T00:00:00Z"})
            _check("work item uses configured state",
                   item.status_code == 201 and item.json()["state_group"] == "in_progress",
                   f"HTTP {item.status_code}")
            item_id = item.json()["id"]
            updated_item = client.patch(
                f"/api/v1/workspaces/{ws}/projects/{pid}/items/{item_id}", headers=headers,
                json={"status": "Smoke Done"},
            )
            _check("work item completion tracks state group",
                   updated_item.status_code == 200 and updated_item.json()["completed_at"] is not None,
                   f"HTTP {updated_item.status_code}")
            progress = client.get(f"/api/v1/workspaces/{ws}/projects/{pid}/progress", headers=headers)
            _check("progress reflects the completed item",
                   progress.status_code == 200 and progress.json()["completion_percent"] == 100.0,
                   f"HTTP {progress.status_code}")
            search_result = client.get(f"/api/v1/workspaces/{ws}/search", headers=headers,
                                       params={"q": "Smoke work item"})
            payload = search_result.json() if search_result.status_code == 200 else {}
            _check("search returns typed work item",
                   search_result.status_code == 200 and any(
                       row["type"] == "project_item" and row["id"] == item_id
                       for row in payload.get("results", [])),
                   f"HTTP {search_result.status_code}")

            print("\n[8] Documents and tracked engagement (P0)")
            room = client.post(f"/api/v1/workspaces/{ws}/documents/rooms", headers=headers,
                               json={"name": "Smoke collateral"})
            _check("document room created", room.status_code == 201, f"HTTP {room.status_code}")
            document = client.post(f"/api/v1/workspaces/{ws}/documents", headers=headers, json={
                "title": "Smoke proposal", "doc_type": "pdf",
                "storage_path": "metadata://local/smoke-proposal.pdf",
                "room_id": room.json()["id"],
            })
            _check("document record created", document.status_code == 201,
                   f"HTTP {document.status_code}")
            did = document.json()["id"]
            link = client.post(f"/api/v1/workspaces/{ws}/documents/{did}/links", headers=headers,
                               json={"max_views": 1, "view_only": True, "download_allowed": False})
            _check("share link with policy created", link.status_code == 201,
                   f"HTTP {link.status_code}")
            dtoken = link.json()["token"]
            resolved = client.get(f"/api/v1/workspaces/{ws}/documents/links/resolve/{dtoken}",
                                  headers=headers)
            _check("share link resolves", resolved.status_code == 200,
                   f"HTTP {resolved.status_code}")
            dvisit = client.post(
                f"/api/v1/workspaces/{ws}/documents/links/resolve/{dtoken}/visits",
                headers=headers, json={"visitor_email": "doc-viewer@example.com"})
            _check("document view recorded with CRM identity",
                   dvisit.status_code == 201 and dvisit.json().get("contact_id"),
                   f"HTTP {dvisit.status_code}")
            doc_cid = dvisit.json()["contact_id"]
            doc_notices = client.get(f"/api/v1/workspaces/{ws}/notifications",
                                     headers=headers, params={"category": "document_view"})
            _check("document view created a real notification",
                    doc_notices.status_code == 200 and len(doc_notices.json()) == 1,
                    f"HTTP {doc_notices.status_code}")
            doc_timeline = client.get(f"/api/v1/workspaces/{ws}/contacts/{doc_cid}/timeline",
                                      headers=headers)
            _check("view reached the customer timeline",
                    doc_timeline.status_code == 200 and any(
                        row["event_type"] == "document.viewed" for row in doc_timeline.json()),
                    f"HTTP {doc_timeline.status_code}")
            denied = client.post(
                f"/api/v1/workspaces/{ws}/documents/links/resolve/{dtoken}"
                f"/visits/{dvisit.json()['id']}/download",
                headers=headers, json={})
            _check("download policy enforced", denied.status_code == 403,
                   f"HTTP {denied.status_code}")
            limited = client.post(
                f"/api/v1/workspaces/{ws}/documents/links/resolve/{dtoken}/visits",
                headers=headers, json={})
            _check("view cap enforced", limited.status_code == 429,
                   f"HTTP {limited.status_code}")

            print("\n[9] Customer profile and membership lifecycle (P0)")
            profile_contact = client.post(f"/api/v1/workspaces/{ws}/contacts", headers=headers, json={
                "full_name": "Profile Visitor", "email": "profile@example.com",
            })
            _check("profile contact created", profile_contact.status_code == 201,
                   f"HTTP {profile_contact.status_code}")
            pcid = profile_contact.json()["id"]
            prof_ticket = client.post(f"/api/v1/workspaces/{ws}/tickets", headers=headers, json={
                "subject": "Smoke profile conversation", "body": "Linked to one identity",
                "contact_id": pcid, "origin_channel": "web_form",
                "conversation_type": "question",
            })
            _check("ticket linked to exactly one contact",
                   prof_ticket.status_code == 201 and prof_ticket.json()["contact_id"] == pcid,
                   f"HTTP {prof_ticket.status_code}")
            linked = client.get(f"/api/v1/workspaces/{ws}/tickets", headers=headers,
                                params={"contact_id": pcid})
            _check("contact profile lists only linked conversations",
                    linked.status_code == 200 and [row["id"] for row in linked.json()] ==
                    [prof_ticket.json()["id"]],
                    f"HTTP {linked.status_code}")
            members = client.get(f"/api/v1/workspaces/{ws}/members", headers=headers)
            _check("membership list available", members.status_code == 200 and len(members.json()) >= 1,
                    f"HTTP {members.status_code}")
            owner_row = next(row for row in members.json() if row["role"] == "owner")
            last_owner = client.patch(
                f"/api/v1/workspaces/{ws}/members/{owner_row['user_id']}",
                headers=headers, json={"status": "suspended"})
            _check("last active owner cannot be suspended", last_owner.status_code == 409,
                   f"HTTP {last_owner.status_code}")

            print("\n[10] Feedback Studio lifecycle (P0)")
            survey = client.post(f"/api/v1/workspaces/{ws}/surveys", headers=headers,
                                 json={"name": "Smoke feedback", "description": "Local only"})
            _check("survey created in draft", survey.status_code == 201 and
                   survey.json()["status"] == "draft", f"HTTP {survey.status_code}")
            sid = survey.json()["id"]
            closed = client.patch(f"/api/v1/workspaces/{ws}/surveys/{sid}",
                                  headers=headers, json={"status": "closed"})
            _check("survey closed", closed.status_code == 200 and
                   closed.json()["status"] == "closed", f"HTTP {closed.status_code}")
            blocked_response = client.post(
                f"/api/v1/workspaces/{ws}/surveys/{sid}/responses",
                headers=headers, json={"score": 9})
            _check("closed survey refuses responses", blocked_response.status_code == 409,
                   f"HTTP {blocked_response.status_code}")
            client.patch(f"/api/v1/workspaces/{ws}/surveys/{sid}",
                         headers=headers, json={"status": "active"})
            recorded = client.post(f"/api/v1/workspaces/{ws}/surveys/{sid}/responses",
                                   headers=headers, json={"score": 8, "comment": "Local note"})
            _check("response recorded after reopening", recorded.status_code == 201,
                   f"HTTP {recorded.status_code}")

            print("\n[11] Consent tokens and external identity (P0)")
            ci_contact = client.post(f"/api/v1/workspaces/{ws}/contacts", headers=headers, json={
                "full_name": "Consent Visitor", "email": "consent-smoke@example.com",
            })
            _check("consent contact created", ci_contact.status_code == 201,
                   f"HTTP {ci_contact.status_code}")
            ccid = ci_contact.json()["id"]
            linked = client.patch(f"/api/v1/workspaces/{ws}/contacts/{ccid}", headers=headers, json={
                "external_id": "smoke-external-1", "external_source": "mautic",
            })
            _check("external identity preserved", linked.status_code == 200 and
                   linked.json()["external_id"] == "smoke-external-1" and
                   linked.json()["id"] == ccid, f"HTTP {linked.status_code}")
            ci_links = client.get(f"/api/v1/workspaces/{ws}/email/consent-links", headers=headers,
                                  params={"contact_id": ccid})
            _check("signed consent links generated", ci_links.status_code == 200 and
                   len(ci_links.json()["links"]) == 4, f"HTTP {ci_links.status_code}")
            unsub = client.post(f"/api/v1/workspaces/{ws}/email/unsubscribe", json={
                "token": ci_links.json()["links"]["unsubscribe"]["token"],
            })
            _check("unsubscribe accepted", unsub.status_code == 200, f"HTTP {unsub.status_code}")
            dnc = client.post(f"/api/v1/workspaces/{ws}/email/dnc", json={
                "token": ci_links.json()["links"]["dnc"]["token"],
            })
            _check("global DNC accepted", dnc.status_code == 200, f"HTTP {dnc.status_code}")
            refreshed = client.get(f"/api/v1/workspaces/{ws}/contacts/{ccid}", headers=headers)
            _check("DNC reflected on contact", refreshed.status_code == 200 and
                   refreshed.json()["do_not_contact"] is True, f"HTTP {refreshed.status_code}")
            resub = client.post(f"/api/v1/workspaces/{ws}/email/resubscribe", json={
                "token": ci_links.json()["links"]["resubscribe"]["token"],
            })
            _check("resubscribe reversed DNC", resub.status_code == 200, f"HTTP {resub.status_code}")

            print("\n[12] Project membership and project-level roles (P0)")
            proj = client.post(f"/api/v1/workspaces/{ws}/projects", headers=headers, json={
                "name": "Smoke release", "restricted": True,
            })
            _check("restricted project created", proj.status_code == 201 and
                   proj.json()["restricted"] is True, f"HTTP {proj.status_code}")
            pid = proj.json()["id"]
            pbase = f"/api/v1/workspaces/{ws}/projects/{pid}"
            initial = client.get(f"{pbase}/members", headers=headers)
            _check("creator is project lead", initial.status_code == 200 and
                   len(initial.json()) == 1 and initial.json()[0]["role"] == "lead",
                   f"HTTP {initial.status_code}")

            invite = client.post(f"/api/v1/workspaces/{ws}/invitations", headers=headers,
                                 json={"email": "pl-smoke@example.com", "role": "sales_rep"})
            _check("member invited", invite.status_code == 200, f"HTTP {invite.status_code}")
            registered = client.post("/api/v1/auth/register", json={
                "email": "pl-smoke@example.com", "password": "Str0ng!Passw0rd",
                "display_name": "PL Smoke",
            })
            _check("member registered", registered.status_code == 200,
                   f"HTTP {registered.status_code}")
            joined = client.post("/api/v1/invitations/accept",
                                 headers={"Authorization": f"Bearer {registered.json()['access_token']}"},
                                 json={"token": invite.json()["invite_token"]})
            _check("invitation accepted", joined.status_code == 200, f"HTTP {joined.status_code}")
            member_headers = {"Authorization": f"Bearer {joined.json()['access_token']}"}
            member_id = client.get("/api/v1/auth/me", headers=member_headers).json()["user"]["id"]
            valid_states = [s["name"] for s in client.get(
                f"/api/v1/workspaces/{ws}/projects/states", headers=headers).json() if s["is_active"]]
            valid_status = valid_states[0] if valid_states else "todo"

            _check("project members hidden before grant",
                   client.get(f"{pbase}/members", headers=member_headers).status_code == 403)
            added = client.post(f"{pbase}/members", headers=headers,
                                json={"user_id": member_id, "role": "viewer"})
            _check("viewer added to project", added.status_code == 201, f"HTTP {added.status_code}")
            _check("viewer can read project", client.get(pbase, headers=member_headers).status_code == 200)
            _check("viewer cannot write items", client.post(
                f"{pbase}/items", headers=member_headers,
                json={"title": "Blocked", "status": valid_status}).status_code == 403)
            _check("viewer cannot delete project",
                   client.delete(pbase, headers=member_headers).status_code == 403)

            promoted = client.patch(f"{pbase}/members/{member_id}", headers=headers,
                                    json={"role": "member"})
            _check("viewer promoted to member", promoted.status_code == 200,
                   f"HTTP {promoted.status_code}")
            member_item = client.post(
                f"{pbase}/items", headers=member_headers,
                json={"title": "Allowed", "status": valid_status})
            _check("member can write items", member_item.status_code == 201,
                   f"HTTP {member_item.status_code}")
            removed = client.delete(f"{pbase}/members/{member_id}", headers=headers)
            _check("member removed", removed.status_code == 200, f"HTTP {removed.status_code}")
            _check("project hidden after removal",
                   client.get(pbase, headers=member_headers).status_code == 403)

            print("\n[13] Marketing journey, scheduling and lifecycle analytics (P0)")
            from datetime import datetime, timedelta, timezone

            camp = client.post(f"/api/v1/workspaces/{ws}/campaigns", headers=headers, json={
                "name": "Smoke journey", "channel": "email", "status": "draft",
            })
            _check("campaign created", camp.status_code == 201, f"HTTP {camp.status_code}")
            camp_id = camp.json()["id"]
            cbase = f"/api/v1/workspaces/{ws}/campaigns/{camp_id}"

            start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            end = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            scheduled = client.post(f"{cbase}/schedule", headers=headers,
                                    json={"start_at": start, "end_at": end})
            _check("campaign scheduled", scheduled.status_code == 200 and
                   scheduled.json()["start_at"] is not None, f"HTTP {scheduled.status_code}")
            due = client.post(f"/api/v1/workspaces/{ws}/campaigns/due", headers=headers)
            _check("due campaign activated locally", due.status_code == 200 and
                   any(row["id"] == camp_id for row in due.json()), f"HTTP {due.status_code}")

            step = client.post(f"{cbase}/journey-steps", headers=headers, json={
                "position": 1, "channel": "email", "action": "email.sent", "label": "Record send",
            })
            _check("journey step added", step.status_code == 201, f"HTTP {step.status_code}")

            journey_contact = client.post(f"/api/v1/workspaces/{ws}/contacts", headers=headers, json={
                "full_name": "Journey Smoke", "email": "journey-smoke@example.com",
            })
            _check("journey contact created", journey_contact.status_code == 201,
                   f"HTTP {journey_contact.status_code}")
            jc_id = journey_contact.json()["id"]
            enrolled = client.post(f"{cbase}/enrollments", headers=headers,
                                   json={"contact_id": jc_id})
            _check("contact enrolled", enrolled.status_code == 201 and
                   enrolled.json()["status"] == "active", f"HTTP {enrolled.status_code}")
            run = client.post(f"{cbase}/run", headers=headers)
            _check("journey advanced one local step", run.status_code == 200 and
                   run.json()["advanced"] == 1 and run.json()["completed"] == 1,
                   f"HTTP {run.status_code}")
            _check("engagement recorded", client.post(f"{cbase}/engagement", headers=headers,
                   json={"contact_id": jc_id, "kind": "opened"}).status_code == 201)

            for kind in ("form.submitted", "page.visited", "webhook.received"):
                intake = client.post(f"/api/v1/workspaces/{ws}/campaigns/analytics/lifecycle",
                                     headers=headers, json={"kind": kind, "source": "smoke"})
                _check(f"lifecycle {kind} recorded", intake.status_code == 201,
                       f"HTTP {intake.status_code}")
            analytics = client.get(f"/api/v1/workspaces/{ws}/campaigns/analytics/lifecycle",
                                   headers=headers)
            _check("lifecycle analytics queryable", analytics.status_code == 200 and
                   len(analytics.json()) >= 6, f"HTTP {analytics.status_code}")

            print("\n[14] Workspace admin, native API contexts and OpenAPI auth (P0)")
            admb = f"/api/v1/workspaces/{ws}/admin"
            saved = client.patch(f"{admb}/settings", headers=headers, json={
                "name": "Smoke Admin", "settings": {"timezone": "Asia/Calcutta", "currency": "INR"},
            })
            _check("workspace settings saved", saved.status_code == 200 and
                   saved.json()["settings"]["currency"] == "INR", f"HTTP {saved.status_code}")
            summary = client.get(f"{admb}/summary", headers=headers)
            _check("admin summary is live", summary.status_code == 200 and
                   summary.json()["name"] == "Smoke Admin", f"HTTP {summary.status_code}")

            second = client.post("/api/v1/workspaces", headers=headers, json={"name": "Smoke Other"})
            _check("second workspace created", second.status_code == 200, f"HTTP {second.status_code}")
            other_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
            _check("cross-workspace settings denied",
                   client.get(f"{admb}/settings", headers=other_headers).status_code == 403)

            client.put(f"/api/v1/workspaces/{ws}/integrations", headers=headers, json={
                "provider": "plane", "config": {"base_url": "https://plane.example/api/"},
            })
            plane = client.post(f"/api/v1/workspaces/{ws}/adapters/plane/invoke", headers=headers,
                                json={"operation": "getlist",
                                      "request": {"context": "projects", "entity": "work-items"}})
            _check("Plane adapter recorded locally", plane.status_code == 200 and
                   plane.json()["status"] == "recorded" and
                   plane.json()["response"]["delivered"] is False, f"HTTP {plane.status_code}")

            apib = f"/api/v1/workspaces/{ws}/api"
            form = client.post(f"{apib}/forms", headers=headers,
                               json={"name": "Smoke form", "fields": [{"name": "email"}]})
            _check("form created", form.status_code == 201, f"HTTP {form.status_code}")
            form_id = form.json()["id"]
            _check("form getList", any(r["id"] == form_id for r in
                   client.get(f"{apib}/forms", headers=headers).json()))
            _check("form edited", client.patch(f"{apib}/forms/{form_id}", headers=headers,
                   json={"status": "published"}).json()["status"] == "published")
            _check("form validation", client.post(f"{apib}/forms", headers=headers,
                   json={"name": "Bad", "status": "live"}).status_code == 422)
            _check("form deleted", client.delete(f"{apib}/forms/{form_id}",
                   headers=headers).status_code == 200)
            page = client.post(f"{apib}/pages", headers=headers,
                               json={"title": "Smoke page", "slug": "smoke-page"})
            _check("page created", page.status_code == 201, f"HTTP {page.status_code}")
            _check("page deleted", client.delete(
                f"{apib}/pages/{page.json()['id']}", headers=headers).status_code == 200)

            spec2 = client.get("/openapi.json").json()
            _check("bearer auth documented", spec2["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer")
            notif_path = f"/api/v1/workspaces/{{workspace_id}}/notifications"
            _check("notification routes documented with auth",
                   spec2["paths"][notif_path]["get"]["security"] == [{"BearerAuth": []}])
            _check("notification runtime auth", client.get(
                f"/api/v1/workspaces/{ws}/notifications").status_code == 401)

            print("\n[15] Analytics experiments and aggregates (P1)")
            anab = f"/api/v1/workspaces/{ws}/analytics"
            created = client.post(anab, headers=headers, json={
                "name": "Smoke experiment", "metric_name": "activation_rate",
                "hypothesis": "Shorter subject line", "baseline": 0.28, "target": 0.35,
            })
            _check("experiment created", created.status_code == 201, f"HTTP {created.status_code}")
            exp_id = created.json()["id"]
            _check("experiment listed", any(r["id"] == exp_id for r in
                   client.get(anab, headers=headers).json()))
            _check("experiment edited", client.patch(f"{anab}/{exp_id}", headers=headers,
                   json={"target": 0.5}).json()["target"] == 0.5)
            _check("experiment status changed", client.post(f"{anab}/{exp_id}/status",
                   headers=headers, json={"status": "running"}).json()["status"] == "running")
            _check("status validation", client.post(f"{anab}/{exp_id}/status",
                   headers=headers, json={"status": "launched"}).status_code == 422)
            result = client.post(f"{anab}/{exp_id}/results", headers=headers,
                                 json={"variant": "control", "impressions": 200, "conversions": 24})
            _check("experiment result recorded", result.status_code == 200 and
                   result.json()["impressions"] == 200, f"HTTP {result.status_code}")
            _check("invalid result rejected", client.post(f"{anab}/{exp_id}/results",
                   headers=headers, json={"variant": "bad", "impressions": 5,
                                          "conversions": 9}).status_code == 422)
            _check("results listed", len(client.get(f"{anab}/{exp_id}/results",
                   headers=headers).json()) == 1)
            _check("funnel from real rows", set(client.get(f"{anab}/funnel",
                   headers=headers).json()) == {"contacts", "leads", "converted_leads", "tasks"})
            vol = client.get(f"{anab}/events/volume", headers=headers).json()
            _check("event volume includes experiment events",
                   any("experiment." in r["event_type"] for r in vol))
            _check("experiment deleted", client.delete(f"{anab}/{exp_id}",
                   headers=headers).status_code == 200)

            print("\nRUNTIME SMOKE: PASS — real uvicorn server served the client and completed the journey.")
            return 0
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
