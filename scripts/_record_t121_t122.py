"""One-off record update for T-121 and T-122."""
from pathlib import Path

ROOT = Path(r"D:\NOVARA\docs")

# 1. Master task board.
p = ROOT / "MASTER_TASK_BOARD.md"
text = p.read_text(encoding="utf-8")
assert "| T-121 |" not in text and "| T-122 |" not in text
lines = text.splitlines(keepends=True)
idx = next(i for i, line in enumerate(lines) if line.startswith("| T-120 |"))
new_rows = [
    "| T-121 | Stage 3: P2 clean-room Plane no-unverified-default boundary "
    "(PL-067/109/133/134/151/153/154/156) | MausBot | DONE | T-120 | "
    "`modules/plane_claim_boundary.py` (read-only workspace-scoped catalogue of negative claims), "
    "`modules/__init__.py`, `tests/test_plane_claim_boundary_p2.py`, evidence + spec | "
    "8 named acceptance tests pass; single Alembic head unchanged at `e0f1a2b3c4d5`; fresh-DB "
    "`upgrade head` exit 0 and `alembic check` clean; no UI surface claimed because acceptance is "
    "negative evidence; 8 not-implemented rows closed clean-room; clean full suite "
    "`docs/evidence/t121-fullsuite-clean-20261124.txt` EXIT=0, 963 passed, 2 warnings in 641.41s | - |\n",
    "| T-122 | Stage 3: P2 clean-room extended claims boundary (26 rows across MS/CW/PM/NV/SB) | "
    "MausBot | DONE | T-121 | "
    "`modules/extended_claim_boundary.py` (read-only workspace-scoped catalogue of 26 negative "
    "evidence rows), `modules/__init__.py`, `tests/test_extended_claim_boundary_p2.py`, evidence | "
    "26 named acceptance tests pass; forbidden tokens scanned against active sources before "
    "selection; single Alembic head unchanged at `e0f1a2b3c4d5`; fresh-DB `upgrade head` exit 0 and "
    "`alembic check` clean; no UI surface claimed because acceptance is negative evidence; 15 "
    "not-implemented and 11 partially-implemented rows closed clean-room; deliverables regenerated "
    "(749 VERIFIED_COMPLETE, 185 LICENSING_RESTRICTED, 280 NOT_IMPLEMENTED, 69 PARTIAL; complete-like "
    "819/1,488 = 55.04%); full first run had 1 failure from a cross-boundary token collision "
    "(langchain in cluster name vs T-120 MS-072 token), fixed in the new module's own descriptor "
    "without weakening existing tests; clean rerun "
    "`docs/evidence/t122-fullsuite-clean-20261124.txt` EXIT=0, 963 passed, 2 warnings in 641.41s | - |\n",
]
lines[idx + 1:idx + 1] = new_rows
p.write_text("".join(lines), encoding="utf-8")
print("updated MASTER_TASK_BOARD.md")

# 2. Test results.
p = ROOT / "TEST_RESULTS.md"
text = p.read_text(encoding="utf-8")
assert "## T-121 -" not in text and "## T-122 -" not in text
text = text.rstrip("\n") + "\n\n" + """## T-121 - Clean-room Plane no-unverified-default boundary (2026-11-24)
- Targeted: `test_plane_claim_boundary_p2.py` -> **8 passed, 1 warning in 6.78s**.
- A read-only workspace-scoped catalogue records each denied claim with a NOVARA-local
  boundary, the preserved Plane AGPL notice, `dependency_declared = false`, no external
  endpoint and an explicit note that no SDK import, build artifact or unverified
  deployment is created.
- No new table or migration. Cross-workspace access fails closed (403); unknown rows 404.
  External network patched to fail for non-loopback addresses.
- Full suite (shared with T-122): `docs/evidence/t121-fullsuite-clean-20261124.txt`
  EXIT=0, **963 passed, 2 warnings in 641.41s (0:10:41)**. Baseline was T-120's 929 passed;
  the delta is the 34 new named tests across T-121 and T-122.

## T-122 - Clean-room extended claims boundary (2026-11-24)
- Targeted: `test_extended_claim_boundary_p2.py` -> **26 named acceptance tests**, part of a
  combined 50-test boundary run that passed in 33.61s.
- 26 rows across Meilisearch (8), Novu (13), Papermark (3), Chatwoot (1) and Sellbird (1).
  Each negative claim has a workspace-scoped boundary record, preserved upstream notice,
  no declared dependency and no external endpoint. Forbidden tokens were scanned against
  active sources and only zero-occurrence tokens were used.
- First full run: 1 failed, 962 passed — the T-120 MS-072 vector-store guard saw the string
  `langchain` in the new cluster's NV-110 descriptor. Fixed by shortening that descriptor in
  the new module (no change to any existing test). Clean rerun: **963 passed, exit 0**.
- Matrix: 15 NOT_IMPLEMENTED + 11 PARTIALLY_IMPLEMENTED rows closed; deliverables regenerated
  (749 VERIFIED_COMPLETE, 280 NOT_IMPLEMENTED, 69 PARTIAL; complete-like 819/1,488 = 55.04%).
"""
p.write_text(text, encoding="utf-8")
print("updated TEST_RESULTS.md")

# 3. Autonomous execution record.
p = ROOT / "NOVARA_AUTONOMOUS_EXECUTION.md"
text = p.read_text(encoding="utf-8")
assert "### T-121 -" not in text and "### T-122 -" not in text
text = text.replace(
    "T-120 verified with clean full suite of record,",
    "T-122 and T-121 verified with clean full suite of record, T-120 verified,",
)
text = text.replace("| Complete-like (verified + compatible replacements) | 785 / 1,488 = 52.76% |",
                    "| Complete-like (verified + compatible replacements) | 819 / 1,488 = 55.04% |")
text = text.replace("| VERIFIED_COMPLETE | 715 |", "| VERIFIED_COMPLETE | 749 |")
text = text.replace("| NOT_IMPLEMENTED | 303 |", "| NOT_IMPLEMENTED | 280 |")
text = text.replace("| PARTIALLY_IMPLEMENTED | 80 |", "| PARTIALLY_IMPLEMENTED | 69 |")
text = text.replace("-> 785 complete-like;", "-> 785 -> 819 complete-like;")
old_baseline = """- Last completed full suite in the project virtual environment: **929 passed,
  2 warnings in 699.28s (0:11:39), exit 0** (`docs/evidence/t120-fullsuite-clean-20261124.txt`,
  `docs/evidence/t120-fullsuite-clean-exit.txt`). T-120 ran that suite after adding
  sixteen named tests; the baseline was T-118's 913 passed."""
new_baseline = """- Last completed full suite in the project virtual environment: **963 passed,
  2 warnings in 641.41s (0:10:41), exit 0** (`docs/evidence/t122-fullsuite-clean-20261124.txt`,
  `docs/evidence/t122-fullsuite-clean-exit.txt`, also copied to the T-121 evidence files).
  T-121 and T-122 ran one shared suite after adding 34 named tests; the baseline was
  T-120's 929 passed."""
assert old_baseline in text
text = text.replace(old_baseline, new_baseline)
text = text.rstrip("\n") + "\n\n" + """### T-121 and T-122 - Clean-room boundary closures and matrix update (2026-11-24)

- T-121 added `apps/api/novara_core/modules/plane_claim_boundary.py` and eight named
  tests, closing PL-067, PL-109, PL-133, PL-134, PL-151, PL-153, PL-154 and PL-156.
- T-122 added `apps/api/novara_core/modules/extended_claim_boundary.py` and 26 named
  tests, closing MS-005, MS-009, MS-010, MS-050, MS-051, MS-059, MS-096, MS-098,
  CW-119, PM-067, PM-136, PM-155, NV-041, NV-053, NV-055, NV-060, NV-061,
  NV-063, NV-066, NV-090, NV-091, NV-095, NV-108, NV-110, NV-114 and SB-043.
  Fifteen rows were NOT_IMPLEMENTED and eleven were PARTIALLY_IMPLEMENTED.
- Both modules are read-only workspace-scoped catalogues of negative evidence. No
  table, migration, SDK, external endpoint, vendored package or unverified capability
  was introduced. Single Alembic head unchanged at `e0f1a2b3c4d5`; fresh-DB
  `alembic upgrade head` exit 0 and `alembic check` clean.
- One full-suite run validated both clusters: **963 passed, 2 warnings in 641.41s,
  exit 0**. The first run had one failure (cross-boundary `langchain` token collision);
  it was repaired in the new module's own descriptor and the clean rerun is of record.
- Matrix after regeneration: **749 VERIFIED_COMPLETE**, 185 LICENSING_RESTRICTED,
  280 NOT_IMPLEMENTED, 69 PARTIALLY_IMPLEMENTED, 135 EXTERNAL_DEPENDENCY_BLOCKED,
  70 compatible replacements; complete-like **819/1,488 = 55.04%**. All seven
  FEATURE_PARITY deliverables regenerated from the live matrix.
- Honest limits: no commit, push, tag, deployment, publish or external send.
"""
p.write_text(text, encoding="utf-8")
print("updated NOVARA_AUTONOMOUS_EXECUTION.md")
