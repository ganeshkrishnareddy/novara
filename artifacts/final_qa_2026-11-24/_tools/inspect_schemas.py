import json
p = r"D:\NOVARA\artifacts\final_qa_2026-11-24\evidence\openapi.json"
j = json.load(open(p, encoding="utf-8"))
s = j["components"]["schemas"]
names = [
    "BootstrapRequest", "ContactCreate", "CompanyCreate", "LeadCreate", "TaskCreate",
    "NoteCreate", "WebsiteSubmission", "DraftCreateRequest",
]
for n in names:
    if n not in s:
        print("MISSING", n); continue
    d = s[n]
    print("\n==", n, "required=", d.get("required"))
    for k, v in d.get("properties", {}).items():
        print("   ", k, "->", v.get("type") or v.get("$ref") or v.get("anyOf") or v.get("enum"))
