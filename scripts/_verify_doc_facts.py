from pathlib import Path
root = Path(r"D:\NOVARA")
checks = {
    "phpstan config": ["phpstan.neon", "phpstan.neon.dist"],
    "codecov config": ["codecov.yml", ".codecov.yml", "codecov.yaml"],
    "DDEV config": [".ddev/config.yaml", ".ddev/config.yml"],
    "composer": ["composer.json", "composer.lock"],
    "transifex": [".tx/config", "tx.yaml"],
    "README": ["README.md", "docs/README.md"],
    "deployment docs": ["DEPLOYMENT.md", "docs/DEPLOYMENT.md", "docs/deployment.md"],
    "third-party notices": ["THIRD_PARTY_NOTICES.md"],
}
for label, paths in checks.items():
    found = [str(p) for p in paths if (root / p).exists()]
    print(label, "->", found or "none")
for name in ["pytest.ini", "pyproject.toml", "Makefile"]:
    p = root / name
    print(name, "exists", p.exists())
print("web package", (root / "apps/web/package.json").exists())
print("module registry in docs", sum(1 for p in (root / "docs").rglob("*.md") if "module registry" in p.read_text(encoding="utf-8", errors="replace").lower()))
