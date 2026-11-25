import json
import sys
sys.path.insert(0, r"D:\NOVARA\artifacts\final_qa_2026-11-24\_tools")
from cdp_driver import CDP

c = CDP()
expr = r"""
(async () => {
  if (location.hash !== '#/contacts') { location.hash = '#/contacts'; await new Promise(r => setTimeout(r, 900)); }
  const btn = [...document.querySelectorAll('.main-wrap button')].find(b => /add contact/i.test(b.textContent));
  if (btn) btn.click();
  await new Promise(r => setTimeout(r, 500));
  const root = document.querySelector('#modal-root');
  return JSON.stringify({
    open: !!root && root.children.length > 0,
    text: (root?.innerText || '').slice(0, 700),
    fields: [...(root?.querySelectorAll('input,textarea,select') || [])].map(i => ({tag:i.tagName,type:i.type,name:i.name,id:i.id,placeholder:i.placeholder}))
  });
})()
"""
print(c.js(expr))
c.close()
