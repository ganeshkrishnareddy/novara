import httpx
c = httpx.Client(base_url="http://127.0.0.1:8765", timeout=20)
a = c.post("/api/v1/auth/login", json={"email":"qa.owner@novara.invalid","password":"QaSynthetic!2026"}).json()
h = {"Authorization": "Bearer " + a["access_token"]}
wid = a["workspace_id"]
r = c.get(f"/api/v1/workspaces/{wid}/experiment-stats/experiments", headers=h)
print(r.status_code, r.text[:2500])
