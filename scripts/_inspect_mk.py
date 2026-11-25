from pathlib import Path
import json
p = Path(r"D:\NOVARA\apps\api\novara_core\skills\vendor\marketingskills")
print("exists", p.exists())
if p.exists():
    print("versions", [x.name for x in p.iterdir()])
    base = p / "2.14.25"
    skills = sorted(base.glob("skills/*/SKILL.md"))
    print("skill count", len(skills))
    print([x.parent.name for x in skills])
    mf = base / "manifest.json"
    if mf.is_file():
        m = json.loads(mf.read_text(encoding="utf-8"))
        print("manifest keys", list(m)[:10] if isinstance(m, dict) else type(m))
