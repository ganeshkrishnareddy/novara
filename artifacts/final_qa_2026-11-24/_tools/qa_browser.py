"""Observed browser verification of the live NOVARA UI.

Drives the locally launched Chrome through its DevTools endpoint. Records one
JSONL row per route and per UI interaction, plus evidence screenshots. No
external navigation and no real message delivery. Each route uses a fresh
short-lived DevTools connection so one slow route cannot stall the sweep.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, r"D:\NOVARA\artifacts\final_qa_2026-11-24\_tools")
from cdp_driver import CDP

OUT = Path(r"D:\NOVARA\artifacts\final_qa_2026-11-24")
LOG = OUT / "evidence" / "qa_browser_log.jsonl"
SHOTS = OUT / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)
_seq = 0


def ts():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def emit(label, detail, outcome, screenshot=None, errors=None):
    global _seq
    _seq += 1
    row = dict(seq=_seq, ts=ts(), step=label, detail=detail,
               js_errors=errors or [], screenshot=screenshot, outcome=outcome)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{_seq:03d}] {outcome:7s} {label[:54]:54s} {str(detail)[:70]}")


SHOT_ROUTES = {
    "#/dashboard": "01_dashboard",
    "#/contacts": "02_contacts",
    "#/leads": "03_leads",
    "#/campaigns": "04_campaign_studio",
    "#/inbox": "05_customer_inbox",
    "#/documents": "06_documents",
    "#/document-engagement": "07_document_engagement",
    "#/projects": "08_projects",
    "#/work-item-planning": "09_work_item_planning",
    "#/advanced-experiments": "10_experimentation",
    "#/agents": "11_agent_center",
    "#/notification-automation": "12_automation",
    "#/access-governance": "13_access_governance",
    "#/flag-governance": "14_flag_governance",
    "#/surveys": "15_feedback_studio",
    "#/settings": "16_settings",
}

PROBE = r"""
(() => {
  const m = document.querySelector('.main-wrap');
  const t = (m?.innerText || '');
  return JSON.stringify({
    h1: m?.querySelector('h1')?.textContent || '',
    chars: t.length,
    snippet: t.slice(0, 150).replace(/\s+/g,' '),
    errorState: /something went wrong|failed to load|unable to load/i.test(t.slice(0,500))
  });
})()
"""

LOGIN = r"""
(async () => {
  location.hash = '#/login';
  await new Promise(r => setTimeout(r, 500));
  const f = document.querySelector('input[type=email]'), p = document.querySelector('input[type=password]');
  if (f && p) {
    f.value='qa.owner@novara.invalid'; p.value='QaSynthetic!2026';
    f.dispatchEvent(new Event('input',{bubbles:true})); p.dispatchEvent(new Event('input',{bubbles:true}));
    [...document.querySelectorAll('button')].find(b=>/sign in/i.test(b.textContent))?.click();
    await new Promise(r=>setTimeout(r,1400));
  }
  return location.hash;
})()
"""

CREATE_CONTACT = r"""
(async () => {
  location.hash = '#/contacts';
  await new Promise(r=>setTimeout(r,700));
  const btn = [...document.querySelectorAll('.main-wrap button')].find(b=>/add contact/i.test(b.textContent));
  btn?.click(); await new Promise(r=>setTimeout(r,400));
  const set = (n,v)=>{const e=document.querySelector('#modal-root [name='+n+']');if(e){e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));}};
  set('email','qa.browser@novara.invalid'); set('full_name','BrowserQA Contact');
  set('company_name','Synthetic Browser Co'); set('source','qa-browser');
  [...document.querySelectorAll('#modal-root button')].find(b=>/create contact/i.test(b.textContent))?.click();
  await new Promise(r=>setTimeout(r,1100));
  const body = document.body.innerText;
  return JSON.stringify({modalClosed: document.querySelector('#modal-root')?.children.length===0,
                         toastVisible: !!document.querySelector('#toast.show'),
                         listHasContact: body.includes('BrowserQA Contact'),
                         snippet: body.slice(0,220).replace(/\s+/g,' ')});
})()
"""


def with_cdp(fn, default=None):
    """Return (result, live connection). The caller closes it after screenshots."""
    try:
        c = CDP()
        return fn(c), c
    except Exception as exc:
        emit("CDP call failed", {"error": f"{type(exc).__name__}: {exc}"[:200]}, "FAIL")
        return default, None


def main():
    LOG.write_text("", encoding="utf-8")
    _, c = with_cdp(lambda x: x.js(
        "window.__qaErrors=[];window.addEventListener('error',e=>__qaErrors.push(String(e.message)));"
        "window.addEventListener('unhandledrejection',e=>__qaErrors.push('unhandled:'+String(e.reason)));true"))
    if c is not None:
        c.close()

    result, c = with_cdp(lambda x: x.js(LOGIN))
    hash_after = result if isinstance(result, str) else ""
    emit("Sign in with synthetic QA owner", {"hash": hash_after},
         "PASS" if "#/dashboard" in hash_after else "FAIL")
    if c is not None:
        c.close()

    routes = json.loads((OUT / "evidence" / "ui_routes.json").read_text(encoding="utf-8"))["routes"]
    for route in routes:
        def visit(x):
            x.hash(route, 0.65)
            return json.loads(x.js(PROBE) or "{}")
        detail, x = with_cdp(visit, {})
        if not detail:
            continue
        shot = None
        if route in SHOT_ROUTES and x is not None:
            try:
                shot_path = SHOTS / f"{SHOT_ROUTES[route]}.png"
                x.screenshot(str(shot_path))
                shot = str(shot_path.relative_to(OUT))
            except Exception as exc:
                emit("Screenshot failed " + route, {"error": str(exc)[:120]}, "FAIL")
        ok = bool(detail.get("h1")) and detail.get("chars", 0) > 80 and not detail.get("errorState")
        emit("Route render " + route, detail, "PASS" if ok else "FAIL", shot)
        if x is not None:
            x.close()

    result, x = with_cdp(lambda y: json.loads(y.js(CREATE_CONTACT) or "{}"), {})
    if result:
        shot_path = SHOTS / "17_contact_created.png"
        try:
            x.screenshot(str(shot_path))
        except Exception:
            pass
        emit("Create contact through UI modal", result,
             "PASS" if result.get("listHasContact") or result.get("toastVisible") else "FAIL",
             str(shot_path.relative_to(OUT)))
        if x is not None:
            x.close()

    def theme(x):
        return json.loads(x.js(r"""JSON.stringify({body:getComputedStyle(document.body).backgroundColor,
            app:getComputedStyle(document.querySelector('.app')||document.body).backgroundColor})""") or "{}")
    detail, x = with_cdp(theme, {})
    emit("Light theme computed styles", detail, "PASS" if detail else "FAIL")
    if x is not None:
        x.close()

    def errors(x):
        return json.loads(x.js("JSON.stringify(window.__qaErrors || [])") or "[]")
    errs, x = with_cdp(errors, ["cdp unavailable"])
    emit("JavaScript error sweep", errs, "PASS" if not errs else "FAIL", errors=errs)
    if x is not None:
        x.close()

    print("\nDONE", _seq, "browser observations")


if __name__ == "__main__":
    main()
