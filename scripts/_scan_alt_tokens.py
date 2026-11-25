from pathlib import Path
root = Path(r"D:\NOVARA")
parts = []
for m in [root / "apps/api/pyproject.toml", root / "Dockerfile", root / "docker-compose.yml"]:
    if m.is_file():
        parts += [l.strip().lower() for l in m.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip() and not l.strip().startswith("#")]
skip = {p.name for p in (root / "apps/api/novara_core/modules").glob("*boundary*.py")}
for s in (root / "apps/api/novara_core/modules").rglob("*.py"):
    if s.name in skip:
        continue
    parts.append(s.read_text(encoding="utf-8", errors="replace").lower())
for s in [root / "apps/web/index.html", root / "apps/web/app.js"]:
    if s.is_file():
        parts.append(s.read_text(encoding="utf-8", errors="replace").lower())
text = "\n".join(parts)
for t in ["opt-in postgresql access", "postgresql access", "email channel adapter", "email verification provider", "email verification", "default connector", "provider-verified", "fake delivery", "delivered true"]:
    print(("PRESENT" if t in text else "absent "), t, text.count(t))
