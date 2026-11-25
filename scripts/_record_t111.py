"""One-off record update for T-111 (Papermark data-room governance cluster)."""
from pathlib import Path

ROOT = Path(r"D:\NOVARA\docs")

# 1. Master task board: append the T-111 row after T-110.
p = ROOT / "MASTER_TASK_BOARD.md"
text = p.read_text(encoding="utf-8")
assert "| T-111 |" not in text
lines = text.splitlines(keepends=True)
idx = next(i for i, line in enumerate(lines) if line.startswith("| T-110 |"))
t111 = (
    "| T-111 | Stage 3: P2/P3 clean-room Papermark data-room governance "
    "(PM-050/057/058/059/060/061/062/064/065/066) | MausBot | DONE | T-110 | "
    "`modules/dataroom_governance.py` (11 additive `drg_*` tables: room settings, "
    "append-only events, nested folders, item ordering, viewer groups/rules, "
    "per-item and per-link permissions, link/group bindings, invitations, access "
    "decisions), `modules/__init__.py`, "
    "`migrations/versions/a7b8c9d0e1f2_dataroom_governance.py`, "
    "`tests/test_dataroom_governance_p2.py`, evidence + spec, all seven "
    "FEATURE_PARITY deliverables | 10 named acceptance tests pass; "
    "single Alembic head `a7b8c9d0e1f2`; fresh-DB `upgrade head` exit 0; "
    "no dedicated SPA surface claimed because acceptance criteria are "
    "API/server-level; 10 licensing-restricted rows closed clean-room; "
    "deliverables regenerated (629 VERIFIED_COMPLETE, 187 LICENSING_RESTRICTED, "
    "377 NOT_IMPLEMENTED; complete-like 699/1,488 = 46.98%); clean full suite "
    "`docs/evidence/t111-fullsuite-20261124.txt` EXIT=0, 843 passed, "
    "2 warnings in 545.79s (0:09:05). Note: `alembic check` still reports the "
    "pre-existing `experiments.baseline/target` DOUBLE-vs-Float drift from older "
    "experiment code; no `drg_*` diff | - |\n"
)
lines.insert(idx + 1, t111)
p.write_text("".join(lines), encoding="utf-8")
print("updated MASTER_TASK_BOARD.md")

# 2. Test results: append the T-111 section.
p = ROOT / "TEST_RESULTS.md"
text = p.read_text(encoding="utf-8")
assert "## T-111 -" not in text
text = text.rstrip("\n") + "\n\n" + """## T-111 - Clean-room Papermark data-room governance (2026-11-24)
- Targeted: `test_dataroom_governance_p2.py` -> **10 passed** (one named
  acceptance test for each of PM-050/057/058/059/060/061/062/064/065/066).
- Ten clean-room Papermark rows closed: permissioned rooms with documents,
  visitors, links and append-only audit events; nested folders; persisted item
  ordering; room-scoped viewer groups bindable to links; email/domain rules;
  per-item group view/download permissions; immediate link permission changes;
  room entitlement checks that deny another room's document; invitations that
  grant only the invited room; and frozen rooms that reject mutation.
- All mutations are workspace-scoped, permission-gated and audited on NOVARA's
  local event spine; no Papermark EE source, hosted instance, outbound HTTP,
  external delivery or real email send is used. `socket.socket.connect` is
  patched to fail for non-loopback addresses in every acceptance test.
- Frontend: no dedicated SPA view is claimed; the acceptance criteria are
  API/server-level.
- Other checks: single Alembic head `a7b8c9d0e1f2`; fresh-DB
  `alembic upgrade head` exit 0. `alembic check` still reports the pre-existing
  `experiments.baseline`/`experiments.target` DOUBLE-vs-Float drift from older
  experiment code; none of the eleven `drg_*` tables produce a diff.
- Evidence: `docs/evidence/dataroom-governance-p2-20261124.md`; spec
  `scripts/specs/dataroom-governance-p2-20261124.json`.
- Matrix: 10 rows moved from LICENSING_RESTRICTED to VERIFIED_COMPLETE;
  deliverables regenerated (629 VERIFIED_COMPLETE, 187 LICENSING_RESTRICTED,
  377 NOT_IMPLEMENTED; complete-like 699/1,488 = 46.98%).
- Full suite: `docs/evidence/t111-fullsuite-20261124.txt` EXIT=0, **843 passed,
  2 warnings in 545.79s (0:09:05)**. Baseline before this cluster was 833
  passed; the delta is exactly the ten new named tests.
"""
p.write_text(text, encoding="utf-8")
print("updated TEST_RESULTS.md")

# 3. Autonomous execution record: header, current-state counts, baseline, new section.
p = ROOT / "NOVARA_AUTONOMOUS_EXECUTION.md"
text = p.read_text(encoding="utf-8")
assert "### T-111 -" not in text
text = text.replace(
    "Last updated: 2026-11-24 (Asia/Calcutta) — Stage 3 (P2/P3) in progress; T-110 verified with clean full suite of record, T-109 verified, T-108 clean full suite superseded by T-110",
    "Last updated: 2026-11-24 (Asia/Calcutta) — Stage 3 (P2/P3) in progress; T-111 verified with clean full suite of record, T-110 verified, T-108 clean full suite superseded by T-110 and then T-111",
)
text = text.replace("| Complete-like (verified + compatible replacements) | 689 / 1,488 = 46.30% |",
                    "| Complete-like (verified + compatible replacements) | 699 / 1,488 = 46.98% |")
text = text.replace("| VERIFIED_COMPLETE | 619 |", "| VERIFIED_COMPLETE | 629 |")
text = text.replace("| NOT_IMPLEMENTED | 387 |", "| NOT_IMPLEMENTED | 377 |")
text = text.replace("| LICENSING_RESTRICTED | 197 |", "| LICENSING_RESTRICTED | 187 |")
text = text.replace("-> 679 -> 689 complete-like;", "-> 679 -> 689 -> 699 complete-like;")
text = text.replace(
    "- Last completed full suite in the project virtual environment: **833 passed,\n  2 warnings in 520.04s (0:08:40), exit 0** (`docs/evidence/t110-fullsuite-20261124.txt`,\n  `docs/evidence/t110-fullsuite-exit.txt`). T-110 ran that suite after adding ten\n  named tests; the baseline was T-108's 823 passed. T-109 added targeted tests\n  only and did not claim a new full-suite run.",
    "- Last completed full suite in the project virtual environment: **843 passed,\n  2 warnings in 545.79s (0:09:05), exit 0** (`docs/evidence/t111-fullsuite-20261124.txt`,\n  `docs/evidence/t111-fullsuite-exit.txt`). T-111 ran that suite after adding ten\n  named tests; the baseline was T-110's 833 passed. T-109 added targeted tests\n  only and did not claim a new full-suite run.",
)
text = text.rstrip("\n") + "\n\n" + """### T-111 - Clean-room Papermark data-room governance and matrix closure (2026-11-24)

- Integrated `apps/api/novara_core/modules/dataroom_governance.py` with Alembic
  revision `a7b8c9d0e1f2` (down revision `e6f7a8b9c1d2`, single head) and
  `tests/test_dataroom_governance_p2.py`, closing 10 licensing-restricted
  Papermark rows (PM-050/057/058/059/060/061/062/064/065/066). Eleven additive
  `drg_*` tables cover room settings, append-only audit events, nested folders,
  persisted item ordering, room-scoped viewer groups and rules, per-item and
  per-link permissions, link/group bindings, invitations and recorded access
  decisions.
- Verification: **10 named tests pass**; fresh-DB `alembic upgrade head` exit 0
  and `alembic heads` = `a7b8c9d0e1f2`. `alembic check` still reports the
  pre-existing `experiments.baseline`/`experiments.target` DOUBLE-vs-Float drift
  from older experiment code; none of the eleven `drg_*` tables produce a diff.
  No dedicated SPA surface is claimed because the acceptance criteria are
  API/server-level.
- Full suite: **843 passed, 2 warnings in 545.79s (0:09:05), exit 0**
  (`docs/evidence/t111-fullsuite-20261124.txt`,
  `docs/evidence/t111-fullsuite-exit.txt`). Baseline was T-110's 833 passed;
  the delta is exactly the ten new named tests. This supersedes the T-110 run
  as the clean full suite of record. An earlier attempt at this suite was
  interrupted at 51% with no result and was discarded, not counted.
- Matrix after regeneration: **629 VERIFIED_COMPLETE**, 187
  LICENSING_RESTRICTED, 377 NOT_IMPLEMENTED, 80 PARTIALLY_IMPLEMENTED, 135
  EXTERNAL_DEPENDENCY_BLOCKED, 70 compatible replacements; complete-like
  **699/1,488 = 46.98%**. All seven FEATURE_PARITY deliverables were
  regenerated from the matrix.
- Honest limits: no Papermark EE source, hosted instance, outbound HTTP,
  external delivery or real email send was used. `socket.socket.connect` was
  patched to fail for non-loopback addresses in every acceptance test. No
  commit, push, tag, deployment or publish was made.
"""
p.write_text(text, encoding="utf-8")
print("updated NOVARA_AUTONOMOUS_EXECUTION.md")
