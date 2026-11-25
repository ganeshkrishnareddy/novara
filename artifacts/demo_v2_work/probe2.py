import sys
sys.path.insert(0, r'D:\NOVARA\artifacts\final_qa_2026-11-24\_tools')
from cdp_driver import CDP

c = CDP()
for route in ['#/feedback-intelligence', '#/drafts', '#/outreach', '#/agents', '#/sales-engagement', '#/campaigns']:
    c.hash(route, 1.2)
    txt = c.js("document.querySelector('.main-wrap')?.innerText||''") or ''
    btns = c.js("JSON.stringify([...document.querySelectorAll('.main-wrap button')].map(b=>b.innerText.trim()).filter(Boolean).slice(0,30))")
    print('\nROUTE', route, '\nTEXT', txt[:500].replace('\n', ' | '), '\nBTNS', btns)
c.close()
