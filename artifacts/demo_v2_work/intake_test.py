import sys, json, time
sys.path.insert(0, r'D:\NOVARA\artifacts\final_qa_2026-11-24\_tools')
from cdp_driver import CDP

c = CDP()
c.hash('#/contacts', 1.0)
print('HASH', c.js('location.hash'))
r = c.js(r"""(async()=>{
  const btn=[...document.querySelectorAll('.main-wrap button')].find(b=>/record intake/i.test(b.innerText));
  btn?.click(); await new Promise(r=>setTimeout(r,500));
  const set=(n,v)=>{const e=document.querySelector('#modal-root [name='+n+']');if(e){e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));}return !!e;};
  const found={
    email:set('email','demo.journey@novara.invalid'),
    full_name:set('full_name','Jordan Rivera'),
    company:set('company','Northstar Studio'),
    source:set('source','website_form'),
    submission_id:set('submission_id','DEMO2-20261124-001'),
    message:set('message','Asked about one workspace for leads, campaigns and support')
  };
  [...document.querySelectorAll('#modal-root button')].find(b=>/run intake/i.test(b.innerText))?.click();
  await new Promise(r=>setTimeout(r,1600));
  return JSON.stringify({found:found, modal:(document.querySelector('#modal-root')?.innerText||'').slice(0,1200)});
})()""")
print('RESULT', r)
c.close()
