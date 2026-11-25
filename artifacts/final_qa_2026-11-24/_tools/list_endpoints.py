import json
from pathlib import Path

spec = json.loads(Path(r"D:\NOVARA\artifacts\final_qa_2026-11-24\evidence\openapi.json").read_text(encoding="utf-8"))
keywords = [
    "campaign", "ticket", "conversation", "document", "room", "experiment",
    "survey", "project", "work-item", "workflow", "agent", "automation",
    "intake", "lead", "outreach", "notification",
]
for kw in keywords:
    print("=" * 12, kw)
    hits = [p for p in spec["paths"] if kw in p.lower()]
    for p in hits[:28]:
        methods = ",".join(m.upper() for m in spec["paths"][p] if m in ("get", "post", "patch", "put", "delete"))
        print(f"  {methods:22s} {p}")
    if len(hits) > 28:
        print(f"  ... {len(hits) - 28} more")
