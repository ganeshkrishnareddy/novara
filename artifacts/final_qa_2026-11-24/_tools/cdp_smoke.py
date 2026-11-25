import json
import sys
sys.path.insert(0, r"D:\NOVARA\artifacts\final_qa_2026-11-24\_tools")
from cdp_driver import CDP

c = CDP()
print("TARGET", c.target["url"])
expr = """
JSON.stringify({
  url: location.href,
  title: document.title,
  app: (document.querySelector('#app')?.innerText || '').slice(0, 220),
  scripts: [...document.scripts].map(s => s.src),
  errored: window.__qaErrors || []
})
"""
print("STATE", c.js(expr))
c.close()
