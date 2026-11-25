import sys
sys.path.insert(0, r'D:\NOVARA\artifacts\final_qa_2026-11-24\_tools')
from cdp_driver import CDP

c = CDP()

def modal_fields(route, action):
    c.hash(route, 1.2)
    ok = c.js("(()=>{const b=[...document.querySelectorAll('.main-wrap button')].find(x=>new RegExp(%r,'i').test(x.innerText)); if(!b)return false; b.click(); return true;})()" % action)
    fields = c.js("JSON.stringify([...document.querySelectorAll('#modal-root input,#modal-root textarea,#modal-root select')].map(e=>({name:e.name,type:e.type,value:e.value})))")
    title = c.js("document.querySelector('#modal-root')?.innerText.slice(0,220)||''")
    print(route, action, 'opened=', ok, '\n TITLE', (title or '').replace('\n', ' | '), '\n FIELDS', fields)
    c.js("(()=>{const b=[...document.querySelectorAll('#modal-root button')].find(x=>/cancel/i.test(x.innerText));if(b)b.click();})()")

modal_fields('#/feedback-intelligence', 'new segment')
modal_fields('#/contacts/610e706f-7ffb-4ae0-bb08-1af687fdabf5', 'new note')
c.hash('#/tasks', 1.2)
print('TASK_ROWS', c.js("JSON.stringify([...document.querySelectorAll('.main-wrap tr')].filter(t=>/Jordan|Northstar|demo4/i.test(t.innerText)).map(t=>t.innerText.slice(0,180).replace(/\\s+/g,' ')))"))
c.close()
