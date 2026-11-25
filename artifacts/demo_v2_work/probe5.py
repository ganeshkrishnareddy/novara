import sys, json
sys.path.insert(0, r'D:\NOVARA\artifacts\demo_v2_work')
sys.path.insert(0, r'D:\NOVARA\artifacts\final_qa_2026-11-24\_tools')
from cdp_driver import CDP

c = CDP()
c.js("window.__qaSet=(n,v)=>{const e=document.querySelector('#modal-root [name='+n+']');if(!e)return false;e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return true;}")
c.hash('#/feedback-intelligence', 1.3)
print('BEFORE', c.js("(document.querySelector('.main-wrap')?.innerText||'').match(/\\d+ audience segments/)?.[0]"))
c.js("(()=>{const b=[...document.querySelectorAll('.main-wrap button')].find(x=>/new segment/i.test(x.innerText));b.click();})()")
for n, v in [('key', 'northstar-debug-1'), ('name', 'Northstar Debug One'),
             ('rules_json', '[{"field":"company","op":"eq","value":"Northstar Studio"}]')]:
    expr = "window.__qaSet(%s,%s)" % (json.dumps(n), json.dumps(v))
    print('SET', n, c.js(expr))
print('VALUES', c.js("JSON.stringify([...document.querySelectorAll('#modal-root input,#modal-root textarea')].map(e=>[e.name,e.value]))"))
c.js("(()=>{const b=[...document.querySelectorAll('#modal-root button')].find(x=>/create segment/i.test(x.innerText));if(b)b.click();})()")
import time; time.sleep(2)
print('MODAL', (c.js("document.querySelector('#modal-root')?.innerText||''") or '')[:500].replace('\n', ' | '))
print('TOAST', (c.js("document.querySelector('.toast')?.innerText||document.body.innerText.match(/[^\\n]*segment[^\\n]*/gi)?.slice(-3).join(' | ')||''") or '')[:500])
print('AFTER', c.js("(document.querySelector('.main-wrap')?.innerText||'').match(/\\d+ audience segments/)?.[0]"))
c.close()
