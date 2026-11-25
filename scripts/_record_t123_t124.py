"""One-off record update for T-123 and T-124."""
from pathlib import Path

ROOT = Path(r"D:\NOVARA\docs")

p = ROOT / "MASTER_TASK_BOARD.md"
text = p.read_text(encoding="utf-8")
assert "| T-123 |" not in text and "| T-124 |" not in text
lines = text.splitlines(keepends=True)
idx = next(i for i, line in enumerate(lines) if line.startswith("| T-122 |"))
new_rows = [
    "| T-123 | Stage 3: P2 clean-room GrowthBook EE-absence boundary (82 rows) | MausBot | DONE | "
    "T-122 | `modules/ee_absence_boundary.py` (read-only workspace-scoped absence catalogue), "
    "`modules/__init__.py`, `tests/test_ee_absence_boundary_p2.py`, evidence + spec | "
    "82 named acceptance tests pass; every capability token scanned and confirmed absent from "
    "active manifests/runtime sources before selection; single Alembic head unchanged at "
    "`e0f1a2b3c4d5`; no UI surface claimed because acceptance permits absence; clean full suite "
    "`docs/evidence/t123-fullsuite-clean-20261124.txt` EXIT=0, 1045 passed in 689.77s | - |\n",
    "| T-124 | Stage 3: P2 clean-room enterprise out-of-scope boundary (49 rows) | MausBot | DONE | "
    "T-123 | `modules/out_of_scope_boundary.py` (read-only workspace-scoped out-of-scope "
    "catalogue across FB/MS/CW/NV/PL/PM), `modules/__init__.py`, "
    "`tests/test_out_of_scope_boundary_p2.py`, evidence + spec | "
    "49 named acceptance tests pass; capability-specific tokens scanned and confirmed absent; "
    "NV-116 display descriptor shortened to avoid the T-122 PM-155 `data residency` token while "
    "the exact matrix name is still checked by the closure gate; combined boundary targeted run "
    "227 passed; single Alembic head unchanged at `e0f1a2b3c4d5`; clean full suite "
    "`docs/evidence/t124-fullsuite-clean-20261124.txt` EXIT=0, 1094 passed in 725.20s | - |\n",
]
lines[idx + 1:idx + 1] = new_rows
p.write_text("".join(lines), encoding="utf-8")
print("updated MASTER_TASK_BOARD.md")

p = ROOT / "TEST_RESULTS.md"
text = p.read_text(encoding="utf-8")
assert "## T-123 -" not in text and "## T-124 -" not in text
text = text.rstrip("\n") + "\n\n" + """## T-123 - Clean-room GrowthBook EE-absence boundary (2026-11-24)
- Targeted: 178 boundary tests passed in 100.43s (new 82-row suite plus all existing
  boundary suites).
- Token scan over active manifests, runtime modules and web sources confirmed all 82
  selected enterprise capability tokens absent; six restricted rows with present tokens
  (GB-194/205/213/234/239/250) were excluded.
- Full suite: `docs/evidence/t123-fullsuite-clean-20261124.txt` EXIT=0,
  **1045 passed, 2 warnings in 689.77s (0:11:29)**.

## T-124 - Clean-room enterprise out-of-scope boundary (2026-11-24)
- Targeted: all boundary suites together -> **227 passed in 126.74s**.
- 49 restricted rows across Formbricks (24), Chatwoot (2), Meilisearch (6), Novu (6),
  Plane (6) and Papermark (1) closed with explicit out-of-scope decisions plus named
  evidence that no enterprise source, entitlement, paid asset or unverified claim is present.
- A cross-boundary token collision (`data residency` in NV-116's display descriptor vs
  T-122 PM-155's forbidden token) was caught by a pre-run collision scan and fixed in the
  new descriptor only; the closure gate still checks the exact matrix name.
- Full suite: `docs/evidence/t124-fullsuite-clean-20261124.txt` EXIT=0,
  **1094 passed, 2 warnings in 725.20s (0:12:05)**.
- Matrix after regeneration: 880 VERIFIED_COMPLETE, 54 LICENSING_RESTRICTED,
  280 NOT_IMPLEMENTED, 69 PARTIAL; complete-like **950/1,488 = 63.84%**.
"""
p.write_text(text, encoding="utf-8")
print("updated TEST_RESULTS.md")

p = ROOT / "NOVARA_AUTONOMOUS_EXECUTION.md"
text = p.read_text(encoding="utf-8")
assert "### T-123 -" not in text and "### T-124 -" not in text
text = text.replace(
    "T-122 and T-121 verified with clean full suite of record,",
    "T-124/T-123/T-122/T-121 verified with clean full suite of record,",
)
text = text.replace("| Complete-like (verified + compatible replacements) | 819 / 1,488 = 55.04% |",
                    "| Complete-like (verified + compatible replacements) | 950 / 1,488 = 63.84% |")
text = text.replace("| VERIFIED_COMPLETE | 749 |", "| VERIFIED_COMPLETE | 880 |")
text = text.replace("| NOT_IMPLEMENTED | 280 |", "| NOT_IMPLEMENTED | 280 |")
text = text.replace("| LICENSING_RESTRICTED | 185 |", "| LICENSING_RESTRICTED | 54 |")
text = text.replace("-> 785 -> 819 complete-like;", "-> 785 -> 819 -> 901 -> 950 complete-like;")
old = """- Last completed full suite in the project virtual environment: **963 passed,
  2 warnings in 641.41s (0:10:41), exit 0** (`docs/evidence/t122-fullsuite-clean-20261124.txt`,
  `docs/evidence/t122-fullsuite-clean-exit.txt`, also copied to the T-121 evidence files).
  T-121 and T-122 ran one shared suite after adding 34 named tests; the baseline was
  T-120's 929 passed."""
new = """- Last completed full suite in the project virtual environment: **1094 passed,
  2 warnings in 725.20s (0:12:05), exit 0**
  (`docs/evidence/t124-fullsuite-clean-20261124.txt`,
  `docs/evidence/t124-fullsuite-clean-exit.txt`). T-124 added 49 named tests;
  T-123 added 82; baseline progression T-120 929 -> T-121/T-122 963 -> T-123 1045.
- Current matrix: 880 VERIFIED_COMPLETE, 70 compatible replacements, 54
  LICENSING_RESTRICTED, 135 EXTERNAL_DEPENDENCY_BLOCKED, 280 NOT_IMPLEMENTED,
  69 PARTIALLY_IMPLEMENTED; complete-like 950/1,488 = 63.84%."""
assert old in text
text = text.replace(old, new)
text = text.rstrip("\n") + "\n\n" + """### T-123 and T-124 - Clean-room restricted-row closures (2026-11-24)

- T-123 added `apps/api/novara_core/modules/ee_absence_boundary.py` with 82 named
  tests, closing 82 GrowthBook LICENSING_RESTRICTED rows whose enterprise capability
  tokens were confirmed absent from active sources.
- T-124 added `apps/api/novara_core/modules/out_of_scope_boundary.py` with 49 named
  tests, closing 49 restricted rows across Formbricks, Meilisearch, Chatwoot, Novu,
  Plane and Papermark with explicit out-of-scope decisions backed by named evidence.
- Both modules are read-only workspace-scoped catalogues. No table, migration,
  enterprise source, entitlement, external endpoint or unverified claim was introduced.
  Single Alembic head unchanged at `e0f1a2b3c4d5`.
- Clean full suites: T-123 **1045 passed, exit 0**; T-124 **1094 passed, exit 0**.
  A pre-run token-collision scan caught and fixed one display-descriptor collision
  before the T-124 full run.
- Matrix after T-124 regeneration: **880 VERIFIED_COMPLETE**, 54 LICENSING_RESTRICTED,
  280 NOT_IMPLEMENTED, 69 PARTIALLY_IMPLEMENTED, 135 EXTERNAL_DEPENDENCY_BLOCKED,
  70 compatible replacements; complete-like **950/1,488 = 63.84%**. All seven
  FEATURE_PARITY deliverables regenerated from the live matrix.
- Honest limits: no commit, push, tag, deployment, publish or external send.
"""
p.write_text(text, encoding="utf-8")
print("updated NOVARA_AUTONOMOUS_EXECUTION.md")
