import json
import sys
sys.path.insert(0, r"D:\NOVARA\artifacts\final_qa_2026-11-24\_tools")
from cdp_driver import CDP

c = CDP()
expr = r"""
(async () => {
  const f = document.querySelector('input[type=email]');
  const p = document.querySelector('input[type=password]');
  if (f && p) {
    f.value = 'qa.owner@novara.invalid';
    p.value = 'QaSynthetic!2026';
    f.dispatchEvent(new Event('input', {bubbles:true}));
    p.dispatchEvent(new Event('input', {bubbles:true}));
    const b = [...document.querySelectorAll('button')].find(x => /sign in/i.test(x.textContent));
    if (b) b.click();
  }
  await new Promise(r => setTimeout(r, 1500));
  const routes = [...document.querySelectorAll('a[href^="#/"]')].map(a => a.getAttribute('href'));
  return JSON.stringify({url: location.href, routes: [...new Set(routes)], heading: document.querySelector('.main-wrap h1')?.textContent || ''});
})()
"""
data = json.loads(c.js(expr))
print(json.dumps(data, indent=2))
with open(r"D:\NOVARA\artifacts\final_qa_2026-11-24\evidence\ui_routes.json", "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)

for route in ["#/contacts", "#/leads", "#/campaigns", "#/inbox", "#/projects", "#/advanced-experiments", "#/agents", "#/documents"]:
    c.hash(route, 1.0)
    probe = r"""
    JSON.stringify({
      route: location.hash,
      h1: document.querySelector('.main-wrap h1')?.textContent || '',
      buttons: [...document.querySelectorAll('.main-wrap button')].map(b => b.textContent.trim().replace(/\s+/g,' ').slice(0,60)).filter(Boolean).slice(0,25),
      inputs: [...document.querySelectorAll('.main-wrap input,.main-wrap textarea,.main-wrap select')].map(i => ({tag:i.tagName,type:i.type||'',placeholder:i.placeholder||'',name:i.name||''})).slice(0,25),
      chars: (document.querySelector('.main-wrap')?.innerText||'').length
    })
    """
    print(route, c.js(probe))
c.close()
