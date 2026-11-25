import sys, json
sys.path.insert(0, r'D:\NOVARA\artifacts\final_qa_2026-11-24\_tools')
from cdp_driver import CDP

CID = '5a9f0312-92dd-4965-9a98-3039c17f5de2'
c = CDP()
c.hash('#/contacts/' + CID, 1.4)
print('CONTACT_TEXT', (c.js("document.querySelector('.main-wrap')?.innerText||''") or '')[:1800].replace('\n', ' | '))
c.hash('#/campaigns', 1.2)
print('CAMPAIGNS', (c.js("document.querySelector('.main-wrap')?.innerText||''") or '')[:1600].replace('\n', ' | '))
c.close()
