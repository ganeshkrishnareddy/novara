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

cands = [
    "search rule", "inlinerule", "search-rule", "shard", "replica", "usenetwork", "s3 snapshot",
    "ee entitlement", "enterprise marker", "paid entitlement", "enterprise asset", "unverified certification",
    "paid cloud variable", "proprietary translation", "requires a subscription", "compliance claim",
    "novu-branded", "novu branding", "enterprise packages", "novu cloud account", "managed agent account",
    "cloud-region", "plane entitlement", "business-tier", "enterprise grid", "plane ai credits",
    "plane billing", "dataroom_member", "boxhq", "license activation", "ee source", "entitlement check",
    "white-label", "saml sign-in", "oidc sign-in", "sentry integration", "draw.io", "gitlab integration",
    "network topology", "ee source file", "entitlement marker", "plane ai agent", "novu cloud",
]
for t in cands:
    print(("PRESENT" if t in text else "absent "), t, text.count(t))
