import json
import sys
sys.path.insert(0, r"D:\NOVARA\artifacts\final_qa_2026-11-24\_tools")
from schema_payload import SPEC, resolve

for name in sys.argv[1:]:
    s = resolve(SPEC["components"]["schemas"][name])
    print("=" * 20, name, "required:", s.get("required"))
    for k, v in s.get("properties", {}).items():
        v = resolve(v)
        print(f"  {k}: {v.get('type')} enum={v.get('enum')} items={json.dumps(v.get('items'))[:220]} ref={v.get('$ref')}")
        if "anyOf" in v:
            print("     anyOf", json.dumps(v["anyOf"])[:260])
