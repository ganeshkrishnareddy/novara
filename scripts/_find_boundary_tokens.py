import ast
import sys
from pathlib import Path

TESTS = Path(r"D:\NOVARA\apps\api\tests")
sys.path.insert(0, str(Path(r"D:\NOVARA\apps\api")))

tokens = set()
for name in (
    "test_ee_absence_boundary_p2.py",
    "test_external_dependency_boundary_p2.py",
    "test_out_of_scope_boundary_p2.py",
    "test_plane_claim_boundary_p2.py",
    "test_extended_claim_boundary_p2.py",
    "test_dependency_boundary_p2.py",
):
    tree = ast.parse((TESTS / name).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "FORBIDDEN_TOKENS" in targets:
                try:
                    value = ast.literal_eval(node.value)
                except Exception:
                    continue
                for row_tokens in value.values():
                    tokens.update(str(t).lower() for t in row_tokens)
                print(name, "FORBIDDEN_TOKENS", len(value))
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "FORBIDDEN_TOKENS":
            try:
                value = ast.literal_eval(node.value)
            except Exception:
                continue
            for row_tokens in value.values():
                tokens.update(str(t).lower() for t in row_tokens)
            print(name, "FORBIDDEN_TOKENS (ann)", len(value))

from novara_core.modules.ee_absence_boundary import CLAIM_CATALOG as EE
for spec in EE.values():
    tokens.add(str(spec["token"]).lower())
print("TOTAL TOKENS", len(tokens))
Path(r"D:\NOVARA\scripts\_boundary_tokens.txt").write_text("\n".join(sorted(tokens)), encoding="utf-8")
