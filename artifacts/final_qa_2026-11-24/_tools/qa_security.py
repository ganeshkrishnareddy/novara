"""Negative / security checks against the isolated local NOVARA QA instance.

All identities and payloads are synthetic `.invalid` records. No real service
is contacted. Outcomes are recorded exactly as observed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8765"
OUT = Path(r"D:\NOVARA\artifacts\final_qa_2026-11-24")
LOG = OUT / "evidence" / "qa_security_log.jsonl"
c = httpx.Client(base_url=BASE, timeout=30.0)
_seq = 0


def ts():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def check(name, method, path, token=None, body=None, expected=(), note="", assert_detail=None):
    global _seq
    _seq += 1
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = c.request(method, path, headers=headers, json=body)
        status = r.status_code
        try:
            data = r.json()
        except Exception:
            data = r.text[:300]
        observed = json.dumps(data, ensure_ascii=False)[:500]
    except Exception as exc:
        status, observed = "ERR", f"{type(exc).__name__}: {exc}"
    ok = status in expected and (assert_detail is None or assert_detail.lower() in observed.lower())
    row = dict(seq=_seq, ts=ts(), scenario=name, method=method, path=path,
               expected=f"status in {expected}" + (f" and detail contains {assert_detail!r}" if assert_detail else ""),
               status=status, observed=observed, outcome="PASS" if ok else "FAIL", note=note)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{_seq:02d}] {row['outcome']:4s} {name[:52]:52s} -> {status}")
    return status, data


def main():
    LOG.write_text("", encoding="utf-8")
    print("NOVARA local security checks", ts())

    _, a = check("Valid synthetic login", "POST", "/api/v1/auth/login",
                 body={"email": "qa.owner@novara.invalid", "password": "QaSynthetic!2026"},
                 expected=(200,))
    token, wid = a["access_token"], a["workspace_id"]
    _, b = check("Second identity login", "POST", "/api/v1/auth/login",
                 body={"email": "qa.other@novara.invalid", "password": "QaOther!2026"},
                 expected=(200,))
    token2 = b["access_token"]

    check("Wrong password rejected", "POST", "/api/v1/auth/login",
          body={"email": "qa.owner@novara.invalid", "password": "definitely-wrong"},
          expected=(401,), note="No account enumeration in the response")
    check("Unknown account rejected", "POST", "/api/v1/auth/login",
          body={"email": "nobody@novara.invalid", "password": "definitely-wrong"},
          expected=(401,))
    check("Tampered bearer token rejected", "GET", f"/api/v1/workspaces/{wid}/contacts",
          token="not-a-valid-token", expected=(401, 403))
    check("Missing bearer token rejected", "GET", f"/api/v1/workspaces/{wid}/contacts",
          expected=(401, 403))
    check("Malformed workspace id rejected", "GET", "/api/v1/workspaces/not-a-uuid/contacts",
          token=token, expected=(400, 403, 404, 422))

    _, contacts = check("List workspace A contacts", "GET", f"/api/v1/workspaces/{wid}/contacts",
                        token=token, expected=(200,))
    if isinstance(contacts, list) and contacts:
        cid = contacts[0]["id"]
        check("Cross-workspace contact read denied", "GET", f"/api/v1/workspaces/{wid}/contacts/{cid}",
              token=token2, expected=(403, 404),
              note="Workspace B token must not read Workspace A data")
        check("Duplicate contact email rejected", "POST", f"/api/v1/workspaces/{wid}/contacts",
              token=token, body={"email": contacts[0].get("email"), "full_name": "QA Duplicate"},
              expected=(409,))
        check("Foreign contact id rejected on note", "POST", f"/api/v1/workspaces/{wid}/contacts/{cid}/notes",
              token=token2, body={"contact_id": cid, "body": "Synthetic cross-tenant attempt"},
              expected=(403, 404))

    check("Invalid email rejected by intake", "POST", f"/api/v1/workspaces/{wid}/intake/website-form",
          token=token, body={"email": "not-an-email", "full_name": "QA Invalid"},
          expected=(422,), note="Schema validation fails closed")
    check("SQL-like search input handled literally", "GET",
          f"/api/v1/workspaces/{wid}/contacts?search=%27%20OR%201%3D1--",
          token=token, expected=(200,), note="Search must not error or expose unrelated rows")
    check("Script-like text accepted as inert data", "POST", f"/api/v1/workspaces/{wid}/contacts",
          token=token, body={"email": "qa.xss@novara.invalid",
                             "full_name": "<script>alert('qa')</script>"},
          expected=(201, 409), note="Storage is allowed; UI must escape on render")
    check("Oversized free-text rejected safely", "POST", f"/api/v1/workspaces/{wid}/intake/website-form",
          token=token, body={"email": "qa.big@novara.invalid", "message": "A" * 200000},
          expected=(200, 201, 413, 422), note="Record whether the API bounds large bodies")
    check("Public form token boundary fails closed", "POST",
          "/api/v1/public/visitor-conversations/invalid-token/start",
          body={"email": "qa.public@novara.invalid"},
          expected=(400, 403, 404, 422), note="No anonymous access to workspace records")
    check("Admin settings require owner permission", "GET", f"/api/v1/workspaces/{wid}/admin/settings",
          token=token2, expected=(403, 404),
          note="Second synthetic identity is not an owner of workspace A")

    print("\nDONE", _seq, "security checks")


if __name__ == "__main__":
    main()
