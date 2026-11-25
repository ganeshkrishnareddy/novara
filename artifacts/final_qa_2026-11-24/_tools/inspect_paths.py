import json, sys
p = r"D:\NOVARA\artifacts\final_qa_2026-11-24\evidence\openapi.json"
j = json.load(open(p, encoding="utf-8"))
for path in j["paths"]:
    if any(k in path.lower() for k in ["contacts", "leads", "companies", "tasks"]):
        for method, op in j["paths"][path].items():
            if method not in ("post", "patch", "get"):
                continue
            rb = op.get("requestBody")
            if method == "post" and rb:
                content = rb.get("content", {}).get("application/json", {})
                ref = content.get("schema", {}).get("$ref")
                print(method.upper(), path, "->", ref)
