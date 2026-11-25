import json
from pathlib import Path
p = Path(r"D:\NOVARA\artifacts\final_qa_2026-11-24\evidence\qa_e2e_log.jsonl")
for line in p.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if r["outcome"] == "FAIL":
        print("\n", r["seq"], r["workflow"], r["method"], r["path"].split("/")[-2:])
        print("  payload:", json.dumps(r["payload"], ensure_ascii=False)[:400])
        print("  observed:", r["observed"][:600])
