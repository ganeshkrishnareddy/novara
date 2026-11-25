import sys
sys.path.insert(0, r'D:\NOVARA\artifacts\final_qa_2026-11-24\_tools')
from cdp_driver import CDP

c = CDP()
c.hash('#/leads', 1.5)
print('LEAD_ROWS', c.js("JSON.stringify([...document.querySelectorAll('.main-wrap tr')].filter(t=>/Jordan|demo9/i.test(t.innerText)).map(t=>t.innerText.slice(0,180).replace(/\\s+/g,' ')))"))
print('LEAD_HTML', (c.js("[...document.querySelectorAll('.main-wrap tr')].find(t=>/Jordan/i.test(t.innerText))?.outerHTML||''") or '')[:1200])
c.hash('#/tasks', 1.5)
print('TASK_HTML', (c.js("[...document.querySelectorAll('.main-wrap tr')].find(t=>/Jordan/i.test(t.innerText))?.outerHTML||''") or '')[:1200])
c.close()
