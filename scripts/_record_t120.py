"""One-off record update for T-120 (Meilisearch no-unverified-claim boundary)."""
from pathlib import Path

ROOT = Path(r"D:\NOVARA\docs")

# 1. Master task board: append the T-120 row after T-118.
p = ROOT / "MASTER_TASK_BOARD.md"
text = p.read_text(encoding="utf-8")
assert "| T-120 |" not in text
lines = text.splitlines(keepends=True)
idx = next(i for i, line in enumerate(lines) if line.startswith("| T-118 |"))
t120 = (
    "| T-120 | Stage 3: P2 clean-room Meilisearch no-unverified-claim boundary "
    "(MS-052/054/060/066/068/069/070/071/072/073/079/081/082/094/100/102) | MausBot | DONE | T-118 | "
    "`modules/meilisearch_claim_boundary.py` (read-only workspace-scoped catalogue of negative claims: "
    "NOVARA-local boundary, preserved MIT notice, no declared dependency or external endpoint), "
    "`modules/__init__.py`, `tests/test_meilisearch_claim_boundary_p2.py`, evidence + spec, "
    "all seven FEATURE_PARITY deliverables | "
    "16 named acceptance tests pass (1 warning in 11.53s); single Alembic head unchanged at "
    "`e0f1a2b3c4d5`; fresh-DB `upgrade head` exit 0 and `alembic check` clean; no new schema, SDK, "
    "vendored crate or external call; no UI surface claimed because acceptance is negative evidence; "
    "16 not-implemented rows closed clean-room; deliverables regenerated (715 VERIFIED_COMPLETE, "
    "185 LICENSING_RESTRICTED, 303 NOT_IMPLEMENTED; complete-like 785/1,488 = 52.76%); clean full "
    "suite `docs/evidence/t120-fullsuite-clean-20261124.txt` EXIT=0, 929 passed, 2 warnings in 699.28s (0:11:39) | - |\n"
)
lines.insert(idx + 1, t120)
p.write_text("".join(lines), encoding="utf-8")
print("updated MASTER_TASK_BOARD.md")

# 2. Test results: append the T-120 section.
p = ROOT / "TEST_RESULTS.md"
text = p.read_text(encoding="utf-8")
assert "## T-120 -" not in text
text = text.rstrip("\n") + "\n\n" + """## T-120 - Clean-room Meilisearch no-unverified-claim boundary (2026-11-24)
- Targeted: `test_meilisearch_claim_boundary_p2.py` -> **16 passed, 1 warning in 11.53s**
  (one named acceptance test for each of MS-052, MS-054, MS-060, MS-066, MS-068,
  MS-069, MS-070, MS-071, MS-072, MS-073, MS-079, MS-081, MS-082, MS-094,
  MS-100 and MS-102).
- A read-only workspace-scoped catalogue records each negative claim with its
  NOVARA-local boundary, the preserved Meilisearch MIT notice,
  `dependency_declared = false`, no external endpoint and an explicit note that
  no SDK import, vendored crate, external endpoint or unverified search result
  is created by the boundary.
- No new table or migration. `socket.socket.connect` is patched to fail for
  non-loopback addresses in every acceptance test. No UI surface is claimed;
  acceptance is negative evidence about unverified capabilities.
- Other checks: unchanged single Alembic head `e0f1a2b3c4d5`; fresh-DB
  `alembic upgrade head` exit 0 and `alembic check` = "No new upgrade operations
  detected" (exit 0) in the project virtual environment.
- Evidence: `docs/evidence/meilisearch-claim-boundary-p2-20261124.md`; spec
  `docs/research/specs/meilisearch-claim-boundary-p2-20261124.json`.
- Matrix: 16 not-implemented rows closed; deliverables regenerated (715
  VERIFIED_COMPLETE, 185 LICENSING_RESTRICTED, 303 NOT_IMPLEMENTED;
  complete-like 785/1,488 = 52.76%).
- Full suite: `docs/evidence/t120-fullsuite-clean-20261124.txt` EXIT=0, **929
  passed, 2 warnings in 699.28s (0:11:39)**. Baseline before this cluster was
  T-118's 913 passed; the delta is exactly the sixteen new named tests. An
  earlier partial evidence file from an interrupted run was superseded by this
  clean run.
"""
p.write_text(text, encoding="utf-8")
print("updated TEST_RESULTS.md")

# 3. Autonomous execution record: header, counts, baseline, new section.
p = ROOT / "NOVARA_AUTONOMOUS_EXECUTION.md"
text = p.read_text(encoding="utf-8")
assert "### T-120 -" not in text
text = text.replace(
    "Last updated: 2026-11-24 (Asia/Calcutta) — Stage 3 (P2/P3) in progress; T-118 verified with clean full suite of record, T-117 verified, T-116 verified, T-115 verified, T-114 verified, T-113 verified, T-112 verified, T-111 verified, T-108 clean full suite superseded by T-110 and then T-111/T-112/T-113/T-114/T-115/T-116/T-117/T-118",
    "Last updated: 2026-11-24 (Asia/Calcutta) — Stage 3 (P2/P3) in progress; T-120 verified with clean full suite of record, T-118 verified, T-117 verified, T-116 verified, T-115 verified, T-114 verified, T-113 verified, T-112 verified, T-111 verified, T-108 clean full suite superseded by T-110 and then T-111/T-112/T-113/T-114/T-115/T-116/T-117/T-118/T-120",
)
text = text.replace("| Complete-like (verified + compatible replacements) | 769 / 1,488 = 51.68% |",
                    "| Complete-like (verified + compatible replacements) | 785 / 1,488 = 52.76% |")
text = text.replace("| VERIFIED_COMPLETE | 699 |", "| VERIFIED_COMPLETE | 715 |")
text = text.replace("| NOT_IMPLEMENTED | 319 |", "| NOT_IMPLEMENTED | 303 |")
text = text.replace("769 complete-like; the 295 -> 292 step was a deliberate honesty downgrade, not a code regression).",
                    "769 -> 785 complete-like; the 295 -> 292 step was a deliberate honesty downgrade, not a code regression).")
old_baseline = """- Last completed full suite in the project virtual environment: **913 passed,
  2 warnings in 708.99s (0:11:48), exit 0** (`docs/evidence/t118-fullsuite-20261124.txt`,
  `docs/evidence/t118-fullsuite-exit.txt`). T-118 ran that suite after adding
  nine named tests; the baseline was T-117's 904 passed."""
new_baseline = """- Last completed full suite in the project virtual environment: **929 passed,
  2 warnings in 699.28s (0:11:39), exit 0** (`docs/evidence/t120-fullsuite-clean-20261124.txt`,
  `docs/evidence/t120-fullsuite-clean-exit.txt`). T-120 ran that suite after adding
  sixteen named tests; the baseline was T-118's 913 passed."""
assert old_baseline in text
text = text.replace(old_baseline, new_baseline)
text = text.rstrip("\n") + "\n\n" + """### T-120 - Clean-room Meilisearch no-unverified-claim boundary and matrix closure (2026-11-24)

- Added `apps/api/novara_core/modules/meilisearch_claim_boundary.py` and
  `apps/api/tests/test_meilisearch_claim_boundary_p2.py`, closing sixteen
  not-implemented rows: MS-052, MS-054, MS-060, MS-066, MS-068, MS-069,
  MS-070, MS-071, MS-072, MS-073, MS-079, MS-081, MS-082, MS-094, MS-100 and
  MS-102. The read-only, workspace-scoped catalogue records each denied claim
  with a NOVARA-local boundary, the preserved Meilisearch MIT notice, no
  declared dependency and no external endpoint.
- Verification: **16 named tests pass**; single Alembic head unchanged at
  `e0f1a2b3c4d5`; fresh-DB `alembic upgrade head` exit 0 and `alembic check` =
  "No new upgrade operations detected" (exit 0) in the project virtual
  environment. No dedicated SPA surface is claimed because the acceptance
  criteria are negative evidence about unverified search capabilities.
- Full suite: **929 passed, 2 warnings in 699.28s (0:11:39), exit 0**
  (`docs/evidence/t120-fullsuite-clean-20261124.txt`,
  `docs/evidence/t120-fullsuite-clean-exit.txt`). Baseline was T-118's 913
  passed; the delta is exactly the sixteen new named tests. This supersedes the
  earlier interrupted partial evidence file as the clean full suite of record.
- Matrix after regeneration: **715 VERIFIED_COMPLETE**, 185
  LICENSING_RESTRICTED, 303 NOT_IMPLEMENTED, 80 PARTIALLY_IMPLEMENTED, 135
  EXTERNAL_DEPENDENCY_BLOCKED, 70 compatible replacements; complete-like
  **785/1,488 = 52.76%**. All seven FEATURE_PARITY deliverables were
  regenerated from the live matrix.
- Matrix recovery: running the stale SOURCES-based `build_master_data.py`
  overwrote the live matrix during this cycle; it was restored exactly to the
  recorded T-118 totals from the pre-T-109 baseline plus the recorded closure
  specs and scripts, then T-120 was applied. `generate_deliverables.py` reads
  the CSV and does not modify it.
- Honest limits: no Meilisearch SDK, vendored crate, external endpoint or
  unverified search result was introduced. `socket.socket.connect` was patched
  to fail for non-loopback addresses in every acceptance test. No commit,
  push, tag, deployment or publish was made.
"""
p.write_text(text, encoding="utf-8")
print("updated NOVARA_AUTONOMOUS_EXECUTION.md")
