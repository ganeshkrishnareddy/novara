import sys
sys.path.insert(0, r'D:\NOVARA\artifacts\final_qa_2026-11-24\_tools')
from cdp_driver import CDP

c = CDP()
c.hash('#/leads', 1.5)
print((c.js("document.querySelector('.main-wrap')?.innerText||''") or '')[:900].replace('\n', ' | '))
print('BTNS', c.js("JSON.stringify([...document.querySelectorAll('.main-wrap button')].map(b=>b.innerText.trim()).filter(Boolean).slice(0,20))"))
print('ROWS', c.js("document.querySelectorAll('.main-wrap tbody tr').length"))
c.close()
