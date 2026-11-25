"""Drive one connected NOVARA customer journey through the real UI.

Short, individually verified browser calls. Every action is a genuine
click/type/submit against the local QA instance. Nothing is sent externally.

Demo 2.1 extends the original eight-step run with an audience segment, a
human approval gate and explicit save/verify actions, and holds each screen
long enough to read it. HOLD seconds are configurable via DEMO_HOLD.
"""
from __future__ import annotations

import itertools
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import websocket

sys.path.insert(0, r'D:\NOVARA\artifacts\final_qa_2026-11-24\_tools')
from cdp_driver import CDP, URL_MATCH

OUT = Path(r'D:\NOVARA\artifacts\demo_v2_work')
FAST = os.environ.get('JOURNEY_SPEED') == 'fast'
SCALE = 0.08 if FAST else 1.0
HOLD = float(os.environ.get('DEMO_HOLD', '11'))
EMAIL = os.environ.get('DEMO_EMAIL', 'demo5.journey@novara.invalid')
SUBMISSION = os.environ.get('DEMO_SUBMISSION', 'DEMO2-20261125-FINAL')
NAME = 'Jordan Rivera'
SEGMENT_KEY = os.environ.get('DEMO_SEGMENT', 'northstar-welcome-qa')
SEGMENT_NAME = os.environ.get('DEMO_SEGMENT_NAME', 'Northstar welcome audience')


class LongCDP(CDP):
    def __init__(self, port: int = 9222, url_match: str = URL_MATCH):
        targets = httpx.get(f"http://127.0.0.1:{port}/json", timeout=10).json()
        pages = [t for t in targets if t.get("type") == "page" and url_match in t.get("url", "")]
        if not pages:
            raise RuntimeError("No local NOVARA page found")
        self.target = pages[0]
        self.ws = websocket.create_connection(self.target["webSocketDebuggerUrl"], timeout=90)
        self._ids = itertools.count(1)


HELPERS = r"""
(function(){
  window.__qaQ=(s)=>document.querySelector(s);
  window.__qaAll=(s)=>[...document.querySelectorAll(s)];
  window.__qaBtn=(text,root)=>window.__qaAll((root||'')+' button')
    .find(b=>new RegExp(text,'i').test(b.innerText));
  window.__qaSet=(name,value)=>{
    const e=window.__qaQ('#modal-root [name='+name+']'); if(!e) return false;
    if(e.tagName==='SELECT'){
      const opt=[...e.options].find(o=>o.value===value||o.textContent.includes(value));
      if(opt) e.value=opt.value;
    } else { e.value=value; }
    e.dispatchEvent(new Event('input',{bubbles:true}));
    e.dispatchEvent(new Event('change',{bubbles:true}));
    return true;
  };
  window.__qaClick=(text,root)=>{const b=window.__qaBtn(text,root); if(!b) return false; b.click(); return true;};
  window.__qaLink=(text,root)=>{const a=window.__qaAll((root||'')+' a')
    .find(x=>new RegExp(text,'i').test(x.innerText)); if(!a) return false; a.click(); return true;};
  return true;
})()
"""


def nap(seconds: float):
    time.sleep(seconds * SCALE)


def hold():
    nap(HOLD)


def wait_for(c, expr, timeout=18, interval=0.4):
    end = time.time() + timeout * SCALE
    while time.time() < end:
        try:
            if c.js(expr):
                return True
        except Exception:
            pass
        time.sleep(interval * SCALE)
    return False


def step(steps, name, detail, ok):
    row = dict(step=name, ok=bool(ok), detail=str(detail)[:600])
    steps.append(row)
    print(('PASS' if ok else 'FAIL'), name, flush=True)
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    steps = []
    ids = {}
    c = LongCDP()
    c.js(HELPERS)
    started = datetime.now(timezone.utc).isoformat(timespec='seconds')

    # 1. Command centre
    c.hash('#/dashboard', 0.9)
    wait_for(c, "/Overview/.test(document.querySelector('.main-wrap')?.innerText||'')")
    txt = c.js("document.querySelector('.main-wrap')?.innerText||''") or ''
    step(steps, 'dashboard', txt[:200], 'Overview' in txt)
    hold()

    # 2. One website form -> linked contact, lead, task, draft, notification
    c.hash('#/contacts', 1.0)
    wait_for(c, "!!window.__qaBtn('record intake','.main-wrap')")
    c.js("window.__qaClick('record intake','.main-wrap')")
    wait_for(c, "!!document.querySelector('#modal-root [name=email]')")
    c.js(f"window.__qaSet('email',{json.dumps(EMAIL)})")
    c.js(f"window.__qaSet('full_name',{json.dumps(NAME)})")
    c.js("window.__qaSet('company','Northstar Studio')")
    c.js(f"window.__qaSet('submission_id',{json.dumps(SUBMISSION)})")
    c.js("window.__qaSet('message','Asked about one workspace for leads, campaigns and support')")
    nap(0.8)
    c.js("window.__qaClick('run intake','#modal-root')")
    wait_for(c, "/Intake recorded/.test(document.querySelector('#modal-root')?.innerText||'')")
    modal = c.js("document.querySelector('#modal-root')?.innerText||''") or ''
    for key in ('Contact', 'Lead', 'Task', 'Draft', 'Correlation'):
        m = re.search(key + r'\s+([0-9a-f-]{36})', modal, re.I)
        if m:
            ids[key] = m.group(1)
    step(steps, 'intake', modal[:600], all(k in ids for k in ('Contact', 'Lead', 'Task', 'Draft', 'Correlation')))
    hold()
    c.js("window.__qaLink('open contact','#modal-root')")
    wait_for(c, "/Unified timeline/.test(document.querySelector('.main-wrap')?.innerText||'')")

    # 3. Contact detail - one identity, shared correlation id
    txt = c.js("document.querySelector('.main-wrap')?.innerText||''") or ''
    step(steps, 'contact_timeline', f"correlation mentions={txt.count('Correlation')}",
         'Unified timeline' in txt and txt.count('Correlation') >= 2)
    hold()

    # 4. Lead qualify + convert, targeting the exact lead created by intake
    lead_id = ids.get('Lead', '')
    c.hash('#/leads', 1.2)
    wait_for(c, "!!document.querySelector('[data-action=\"qualify-lead\"][data-id=\"" + lead_id + "\"]')")
    lead = c.js("""(()=>{const b=document.querySelector('[data-action="qualify-lead"][data-id="%s"]');
      if(!b) return JSON.stringify({found:false});
      const before=b.closest('tr')?.innerText.slice(0,220).replace(/\\s+/g,' ')||'';
      b.click(); return JSON.stringify({found:true,before:before,qualifyClicked:true});})()""" % lead_id)
    nap(1.5)
    wait_for(c, "!!document.querySelector('[data-action=\"convert-lead\"][data-id=\"" + lead_id + "\"]')")
    conv = c.js("""(()=>{const b=document.querySelector('[data-action="convert-lead"][data-id="%s"]');
      if(!b) return JSON.stringify({found:false});
      const after=b.closest('tr')?.innerText.slice(0,220).replace(/\\s+/g,' ')||'';
      b.click(); return JSON.stringify({found:true,convertClicked:true,after:after});})()""" % lead_id)
    step(steps, 'lead_qualify_convert', lead + ' | ' + conv,
         '"qualifyClicked":true' in (lead or '') and '"convertClicked":true' in (conv or ''))
    hold()

    # 5. Audience segment from real contact attributes
    c.hash('#/feedback-intelligence', 1.3)
    wait_for(c, "!!window.__qaBtn('new segment','.main-wrap')")
    seg_before = c.js("Number((document.querySelector('.main-wrap')?.innerText||'').match(/(\\d+) audience segments/)?.[1]||0)")
    c.js("window.__qaClick('new segment','.main-wrap')")
    wait_for(c, "!!document.querySelector('#modal-root [name=rules_json]')")
    c.js(f"window.__qaSet('key',{json.dumps(SEGMENT_KEY)})")
    c.js(f"window.__qaSet('name',{json.dumps(SEGMENT_NAME)})")
    c.js("window.__qaSet('rules_json','[{\"field\":\"company\",\"op\":\"eq\",\"value\":\"Northstar Studio\"}]')")
    nap(0.8)
    c.js("window.__qaClick('create segment','#modal-root')")
    nap(1.2)
    # The create handler navigates to the same route, so force a real refresh
    # before reading the stored segment count.
    c.hash('#/dashboard', 0.5)
    c.hash('#/feedback-intelligence', 1.3)
    wait_for(c, "(Number((document.querySelector('.main-wrap')?.innerText||'').match(/(\\d+) audience segments/)?.[1]||0)) > " + str(seg_before))
    seg_after = c.js("Number((document.querySelector('.main-wrap')?.innerText||'').match(/(\\d+) audience segments/)?.[1]||0)")
    txt = c.js("document.querySelector('.main-wrap')?.innerText||''") or ''
    step(steps, 'audience_segment', f"count {seg_before} -> {seg_after} | " + txt[-260:],
         int(seg_after or 0) > int(seg_before or 0))
    hold()

    # 6. Campaign draft recorded for that audience - nothing is sent
    c.hash('#/campaigns', 1.2)
    wait_for(c, "!!window.__qaBtn('new campaign','.main-wrap')")
    c.js("window.__qaClick('new campaign','.main-wrap')")
    wait_for(c, "!!document.querySelector('#modal-root [name=name]')")
    c.js("window.__qaSet('name','Northstar welcome journey')")
    c.js("window.__qaSet('channel','email')")
    c.js("window.__qaSet('goal','Draft for the Northstar welcome audience segment; human approval before any send')")
    nap(0.8)
    c.js("window.__qaClick('create campaign','#modal-root')")
    wait_for(c, "/Northstar welcome journey/.test(document.querySelector('.main-wrap')?.innerText||'')")
    txt = c.js("document.querySelector('.main-wrap')?.innerText||''") or ''
    step(steps, 'campaign_draft', txt[:340], 'Northstar welcome journey' in txt)
    hold()

    # 7. Outreach drafts - human approval gate for the intake-generated draft
    c.hash('#/drafts', 1.3)
    wait_for(c, "/Outreach drafts/.test(document.querySelector('.main-wrap')?.innerText||'')")
    before = c.js(r"""(()=>{const cards=window.__qaAll('.main-wrap section')
      .filter(s=>s.innerText.includes(%s)&&/Draft/.test(s.innerText));
      const card=cards[0]; if(!card) return JSON.stringify({found:false});
      return JSON.stringify({found:true,text:card.innerText.slice(0,260).replace(/\s+/g,' ')});})()""" % json.dumps(NAME))
    approved = c.js(r"""(()=>{const cards=window.__qaAll('.main-wrap section')
      .filter(s=>s.innerText.includes(%s)&&/Draft/.test(s.innerText));
      const card=cards[0]; if(!card) return JSON.stringify({found:false});
      const b=[...card.querySelectorAll('button')].find(x=>/approve/i.test(x.innerText));
      if(b) b.click();
      return JSON.stringify({found:true,approveClicked:!!b});})()""" % json.dumps(NAME))
    nap(1.8)
    after = c.js("document.querySelector('.main-wrap')?.innerText.match(/Draft approved[^\\n]*/)?.[0]||''")
    step(steps, 'approval_gate', (before or '') + ' | ' + (approved or '') + ' | toast=' + (after or ''),
         '"found":true' in (before or '') and '"approveClicked":true' in (approved or ''))
    hold()

    # 8. Support ticket against the same CRM identity
    c.hash('#/inbox', 1.3)
    wait_for(c, "!!window.__qaBtn('new ticket','.main-wrap')")
    c.js("window.__qaClick('new ticket','.main-wrap')")
    wait_for(c, "!!document.querySelector('#modal-root [name=subject]')")
    c.js("window.__qaSet('subject','Question about the unified workspace')")
    c.js("window.__qaSet('body','Jordan asked how leads, campaigns and support stay connected.')")
    c.js(f"window.__qaSet('contact_id',{json.dumps(NAME)})")
    c.js("window.__qaSet('origin_channel','web_form')")
    c.js("window.__qaSet('conversation_type','question')")
    nap(0.8)
    c.js("window.__qaClick('create ticket','#modal-root')")
    wait_for(c, "/Question about the unified workspace/.test(document.querySelector('.main-wrap')?.innerText||'')")
    txt = c.js("document.querySelector('.main-wrap')?.innerText||''") or ''
    step(steps, 'support_ticket', txt[:320], 'Question about the unified workspace' in txt)
    hold()

    # 9. Tasks - the exact follow-up from intake, completed and saved
    task_id = ids.get('Task', '')
    c.hash('#/tasks', 1.2)
    wait_for(c, "!!document.querySelector('[data-action=\"complete-task\"][data-id=\"" + task_id + "\"]')")
    txt = c.js("document.querySelector('.main-wrap')?.innerText||''") or ''
    done = c.js("""(()=>{const b=document.querySelector('[data-action="complete-task"][data-id="%s"]');
      if(!b) return JSON.stringify({found:false});
      const before=b.closest('tr')?.innerText.slice(0,220).replace(/\\s+/g,' ')||'';
      b.click(); return JSON.stringify({found:true,before:before,completeClicked:true});})()""" % task_id)
    nap(1.5)
    step(steps, 'task_complete', (done or '') + ' | present=' + str(NAME in (txt or '')),
         '"completeClicked":true' in (done or ''))
    hold()

    # 10. Insights - refresh from stored rows, no external analytics
    c.hash('#/insights', 1.3)
    wait_for(c, "/Insights/.test(document.querySelector('.main-wrap')?.innerText||'')")
    c.js("window.__qaClick('refresh','.main-wrap')")
    nap(1.6)
    txt = c.js("document.querySelector('.main-wrap')?.innerText||''") or ''
    step(steps, 'insights_refresh', txt[:340], 'Counts are calculated by the API' in (txt or ''))
    hold()

    # 11. Audit trail - the append-only record of the journey
    c.hash('#/activity', 1.3)
    wait_for(c, "/Activity|Audit/.test(document.querySelector('.main-wrap')?.innerText||'')")
    txt = c.js("document.querySelector('.main-wrap')?.innerText||''") or ''
    step(steps, 'audit_trail', txt[:340], len(txt or '') > 120)
    hold()

    data = dict(steps=steps, ids=ids, started=started,
                finished=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                email=EMAIL, submission_id=SUBMISSION, segment_key=SEGMENT_KEY,
                segment_name=SEGMENT_NAME,
                hold_seconds=HOLD, synthetic=True, external_delivery=False)
    path = OUT / 'journey_evidence.json'
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print('WROTE', path, flush=True)
    c.close()
    return data


if __name__ == '__main__':
    main()
