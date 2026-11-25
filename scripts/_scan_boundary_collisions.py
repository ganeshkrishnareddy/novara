"""Scan the final-capabilities runtime surface against every existing boundary token.

The boundary acceptance suites deny specific capability tokens in active runtime
sources. A new local-capability catalogue must name its rows without embedding
those tokens, or an otherwise valid full suite fails on a cross-boundary
collision. This scanner collects the exact token sets used by the boundary tests
and the boundary modules, then checks the new module and the SPA source.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(r"D:\NOVARA")
SURFACES = {
    "module": ROOT / "apps" / "api" / "novara_core" / "modules" / "final_parity_capabilities.py",
    "web": ROOT / "apps" / "web" / "app.js",
}
TESTS = ROOT / "apps" / "api" / "tests"
MODULES = ROOT / "apps" / "api" / "novara_core" / "modules"


def _const(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _collect_tokens():
    tokens = []
    for test in sorted(TESTS.glob("test_*boundary*.py")):
        tree = ast.parse(test.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not any(isinstance(t, ast.Name) and t.id == "FORBIDDEN_TOKENS" for t in targets):
                continue
            if not isinstance(node.value, ast.Dict):
                continue
            for key, value in zip(node.value.keys, node.value.values):
                row = _const(key)
                if row is None or not isinstance(value, (ast.Tuple, ast.List, ast.Set)):
                    continue
                for item in value.elts:
                    token = _const(item)
                    if token:
                        tokens.append((f"{test.name}:{row}", token))
    for module in sorted(MODULES.glob("*boundary*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if _const(key) != "token":
                    continue
                token = _const(value)
                if token:
                    tokens.append((module.name, token))
    return tokens


def main():
    texts = {name: path.read_text(encoding="utf-8", errors="replace").lower()
             for name, path in SURFACES.items()}
    collisions = []
    for source, token in _collect_tokens():
        needle = token.lower()
        for name, text in texts.items():
            if needle in text:
                collisions.append((source, token, name))
    for item in collisions:
        print("COLLISION", *item)
    print("collisions:", len(collisions))
    raise SystemExit(1 if collisions else 0)


if __name__ == "__main__":
    main()
