import sys, json
sys.path.insert(0, r'D:\NOVARA\artifacts\final_qa_2026-11-24\_tools')
from cdp_driver import CDP

c = CDP()
for route in ['#/contacts', '#/leads', '#/campaigns', '#/inbox', '#/tasks', '#/insights', '#/dashboard']:
    c.hash(route, 0.9)
    btns = c.js("JSON.stringify([...document.querySelectorAll('.main-wrap button')].map(b=>b.innerText.trim()).filter(Boolean).slice(0,45))")
    print(route, btns)
c.close()
