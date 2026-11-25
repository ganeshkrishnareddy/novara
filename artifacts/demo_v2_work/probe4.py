import sys
sys.path.insert(0, r'D:\NOVARA\artifacts\final_qa_2026-11-24\_tools')
from cdp_driver import CDP

c = CDP()
c.hash('#/feedback-intelligence', 1.5)
print('SEG_API', c.js(r"""(async()=>{try{const r=await fetch('/api/v1/workspaces/me/feedback-intelligence/segments');return JSON.stringify({status:r.status,body:(await r.text()).slice(0,600)});}catch(e){return String(e)}})()"""))
print('FULLTEXT_HAS', c.js("JSON.stringify({n:(document.querySelector('.main-wrap')?.innerText||'').length,seg:(document.querySelector('.main-wrap')?.innerText||'').includes('Northstar')})"))
print('TAIL', (c.js("document.querySelector('.main-wrap')?.innerText||''") or '')[-1200:].replace('\n', ' | '))
c.close()
