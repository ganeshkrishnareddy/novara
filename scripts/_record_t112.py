"""One-off record update for T-112 (Chatwoot help-centre governance cluster)."""
from pathlib import Path

ROOT = Path(r"D:\NOVARA\docs")

# 1. Master task board: append the T-112 row after T-111.
p = ROOT / "MASTER_TASK_BOARD.md"
text = p.read_text(encoding="utf-8")
assert "| T-112 |" not in text
lines = text.splitlines(keepends=True)
idx = next(i for i, line in enumerate(lines) if line.startswith("| T-111 |"))
t112 = (
    "| T-112 | Stage 3: P2/P3 clean-room Chatwoot help-centre governance "
    "(CW-066/067/087/088/089/090/091/092) | MausBot | DONE | T-111 | "
    "`modules/help_centre_governance.py` (10 additive `hcg_*` tables: portal branding/categories, "
    "article metadata and immutable revisions, local view/search events, page visibility, widget "
    "surfaces, advisory content gaps, authorized-document FAQ index), `modules/__init__.py`, "
    "two internal-page guards in `modules/support.py`, "
    "`migrations/versions/b7c8d9e0f1a2_help_centre_governance.py`, "
    "`tests/test_chatwoot_help_centre_p2.py`, evidence + spec, all seven FEATURE_PARITY deliverables | "
    "8 named acceptance tests pass; single Alembic head `b7c8d9e0f1a2`; fresh-DB `upgrade head` and "
    "`alembic check` exit 0 in the project virtual environment; no dedicated SPA surface claimed "
    "because acceptance criteria are API/server-level; 6 not-implemented and 2 licensing-restricted "
    "rows closed clean-room; deliverables regenerated (637 VERIFIED_COMPLETE, 185 LICENSING_RESTRICTED, "
    "369 NOT_IMPLEMENTED; complete-like 707/1,488 = 47.51%); clean full suite "
    "`docs/evidence/t112-fullsuite-20261124.txt` EXIT=0, 851 passed, 2 warnings in 548.08s (0:09:08) | - |\n"
)
lines.insert(idx + 1, t112)
p.write_text("".join(lines), encoding="utf-8")
print("updated MASTER_TASK_BOARD.md")

# 2. Test results: append the T-112 section.
p = ROOT / "TEST_RESULTS.md"
text = p.read_text(encoding="utf-8")
assert "## T-112 -" not in text
text = text.rstrip("\n") + "\n\n" + """## T-112 - Clean-room Chatwoot help-centre governance (2026-11-24)
- Targeted: `test_chatwoot_help_centre_p2.py` -> **8 passed** (one named
  acceptance test for each of CW-066/067/087/088/089/090/091/092).
- Eight clean-room Chatwoot rows closed: advisory content gaps derived only from
  stored local searches; authorized-document FAQ indexing with retained
  citations; rich-text article metadata, validated embeds and immutable
  revisions; independent portals with separate branding/categories/articles;
  real local view/search event counts; a widget that opens published articles
  without creating a ticket; private pages invisible on every unauthenticated
  surface; and API article CRUD with the same permissions as the staff UI.
- All mutations are workspace-scoped, permission-gated and audited on NOVARA's
  local event spine; no Chatwoot/Captain source, hosted instance, LLM/embedding
  service, outbound HTTP, email or external delivery is used.
  `socket.socket.connect` is patched to fail for non-loopback addresses in every
  acceptance test.
- Frontend: no dedicated SPA view is claimed; the acceptance criteria are
  API/server-level.
- Other checks: single Alembic head `b7c8d9e0f1a2`; fresh-DB
  `alembic upgrade head` exit 0 and `alembic check` reported "No new upgrade
  operations detected" (exit 0) in the project virtual environment. Two
  pre-existing public help routes in `support.py` gained a lazy internal-page
  guard so private articles cannot leak through them.
- Evidence: `docs/evidence/help-centre-governance-p2-20261124.md`; spec
  `docs/research/specs/help-centre-governance-p2-20261124.json`.
- Matrix: 8 rows closed (6 from NOT_IMPLEMENTED, 2 from LICENSING_RESTRICTED);
  deliverables regenerated (637 VERIFIED_COMPLETE, 185 LICENSING_RESTRICTED,
  369 NOT_IMPLEMENTED; complete-like 707/1,488 = 47.51%).
- Full suite: `docs/evidence/t112-fullsuite-20261124.txt` EXIT=0, **851 passed,
  2 warnings in 548.08s (0:09:08)**. Baseline before this cluster was 843
  passed; the delta is exactly the eight new named tests. The first attempt hit
  a pre-existing order-dependent flake in `test_mt033_scoring_rules_apply_with_history`
  (passes in isolation); that discarded result was superseded by the clean run.
"""
p.write_text(text, encoding="utf-8")
print("updated TEST_RESULTS.md")

# 3. Autonomous execution record: header, counts, baseline, new section.
p = ROOT / "NOVARA_AUTONOMOUS_EXECUTION.md"
text = p.read_text(encoding="utf-8")
assert "### T-112 -" not in text
text = text.replace(
    "Last updated: 2026-11-24 (Asia/Calcutta) — Stage 3 (P2/P3) in progress; T-111 verified with clean full suite of record, T-110 verified, T-108 clean full suite superseded by T-110 and then T-111",
    "Last updated: 2026-11-24 (Asia/Calcutta) — Stage 3 (P2/P3) in progress; T-112 verified with clean full suite of record, T-111 verified, T-108 clean full suite superseded by T-110 and then T-111/T-112",
)
text = text.replace("| Complete-like (verified + compatible replacements) | 699 / 1,488 = 46.98% |",
                    "| Complete-like (verified + compatible replacements) | 707 / 1,488 = 47.51% |")
text = text.replace("| VERIFIED_COMPLETE | 629 |", "| VERIFIED_COMPLETE | 637 |")
text = text.replace("| NOT_IMPLEMENTED | 377 |", "| NOT_IMPLEMENTED | 369 |")
text = text.replace("| LICENSING_RESTRICTED | 187 |", "| LICENSING_RESTRICTED | 185 |")
text = text.replace("-> 679 -> 689 -> 699 complete-like;", "-> 679 -> 689 -> 699 -> 707 complete-like;")
text = text.replace(
    "- Last completed full suite in the project virtual environment: **843 passed,\n  2 warnings in 545.79s (0:09:05), exit 0** (`docs/evidence/t111-fullsuite-20261124.txt`,\n  `docs/evidence/t111-fullsuite-exit.txt`). T-111 ran that suite after adding ten\n  named tests; the baseline was T-110's 833 passed. T-109 added targeted tests\n  only and did not claim a new full-suite run.",
    "- Last completed full suite in the project virtual environment: **851 passed,\n  2 warnings in 548.08s (0:09:08), exit 0** (`docs/evidence/t112-fullsuite-20261124.txt`,\n  `docs/evidence/t112-fullsuite-exit.txt`). T-112 ran that suite after adding eight\n  named tests; the baseline was T-111's 843 passed. T-109 added targeted tests\n  only and did not claim a new full-suite run.",
)
text = text.rstrip("\n") + "\n\n" + """### T-112 - Clean-room Chatwoot help-centre governance and matrix closure (2026-11-24)

- Integrated `apps/api/novara_core/modules/help_centre_governance.py` with
  Alembic revision `b7c8d9e0f1a2` (down revision `a7b8c9d0e1f2`, single head)
  and `tests/test_chatwoot_help_centre_p2.py`, closing eight rows: CW-066/067
  (licensing-restricted Captain equivalents) and CW-087/088/089/090/091/092
  (not-implemented MIT-core help-centre behaviour). Ten additive `hcg_*` tables
  cover portal branding/categories, validated article metadata and immutable
  revisions, real local view/search events, private-page visibility, widget
  surfaces, advisory content gaps and an authorized-document FAQ index with
  retained citations.
- Verification: **8 named tests pass**; fresh-DB `alembic upgrade head` exit 0,
  `alembic heads` = `b7c8d9e0f1a2`, and `alembic check` = "No new upgrade
  operations detected" (exit 0) in the project virtual environment. No dedicated
  SPA surface is claimed because the acceptance criteria are API/server-level.
  Two pre-existing public help routes in `support.py` received a lazy,
  import-cycle-safe internal-page guard so private articles cannot leak.
- Full suite: **851 passed, 2 warnings in 548.08s (0:09:08), exit 0**
  (`docs/evidence/t112-fullsuite-20261124.txt`,
  `docs/evidence/t112-fullsuite-exit.txt`). Baseline was T-111's 843 passed;
  the delta is exactly the eight new named tests. This supersedes the T-111 run
  as the clean full suite of record. The first attempt hit a pre-existing
  order-dependent flake in `test_mt033_scoring_rules_apply_with_history` (it
  passes in isolation and the audit-trail ordering tie-break uses random UUIDs);
  that result was discarded, not counted.
- Matrix after regeneration: **637 VERIFIED_COMPLETE**, 185
  LICENSING_RESTRICTED, 369 NOT_IMPLEMENTED, 80 PARTIALLY_IMPLEMENTED, 135
  EXTERNAL_DEPENDENCY_BLOCKED, 70 compatible replacements; complete-like
  **707/1,488 = 47.51%**. All seven FEATURE_PARITY deliverables were
  regenerated from the matrix.
- Honest limits: no Chatwoot/Captain source, paid tier, hosted instance, LLM or
  embedding service, outbound HTTP, external delivery or real email send was
  used. `socket.socket.connect` was patched to fail for non-loopback addresses
  in every acceptance test. No commit, push, tag, deployment or publish was made.
"""
p.write_text(text, encoding="utf-8")
print("updated NOVARA_AUTONOMOUS_EXECUTION.md")
