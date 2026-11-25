from pathlib import Path

root = Path(__file__).resolve().parent.parent

# Task board row
tb = root / "docs" / "MASTER_TASK_BOARD.md"
text = tb.read_text(encoding="utf-8")
row = (
    "| T-062 | Stage 2: P1 analytics experiments UI (GB-110..GB-116) | MausBot | DONE | "
    "T-061 | `modules/analytics.py`, `apps/web/app.js`, "
    "`tests/test_analytics_experiments_p1.py`, `tests/test_ui_wiring.py`, "
    "`docs/evidence/analytics-experiments-p1-20261123.md` | "
    "2 named acceptance tests + 1 UI wiring guard; browser walkthrough; "
    "full suite 247 passed; 7 P1 rows VERIFIED_COMPLETE | \u2014 |\n"
)
marker = "Rows will only move to DONE with linked evidence."
if "T-062 " not in text:
    text = text.replace(marker, row + "\n" + marker)
    tb.write_text(text, encoding="utf-8")

# Execution record updates
ex = root / "docs" / "NOVARA_AUTONOMOUS_EXECUTION.md"
text = ex.read_text(encoding="utf-8")
text = text.replace(
    "Last updated: 2026-11-22 (Asia/Calcutta) — Cycle 4 (P0 Work Items) complete",
    "Last updated: 2026-11-23 (Asia/Calcutta) — Stage 2 (P1) in progress; T-062 complete",
)
text = text.replace(
    "| Current stage | Stage 0 complete; Stage 1 (close P0) in progress |",
    "| Current stage | Stage 1 (P0) COMPLETE; Stage 2 (close P1) in progress |",
)
text = text.replace(
    "| P0 | 111 rows: 66 verified, 4 partial, 32 replacement, 9 restricted |",
    "| P0 | 111 rows: 70 verified, 32 replacement, 9 restricted, 0 partial — EXITED |",
)
text = text.replace(
    "- Full suite in the project virtual environment: **239 passed, 1 warning in 80.10s**.",
    "- Full suite in the project virtual environment: **247 passed, 1 warning in ~89s**.",
)
active_old = (
    "- Stage 2 (T-062 onward): begin the P1 implementation cycle in dependency order,\n"
    "  tests first and evidence-gated. Start with the 218 P1 rows from the priority\n"
    "  backlog in `docs/FEATURE_PARITY/COMPLETION_DASHBOARD.md`."
)
active_new = (
    "- Stage 2 (T-062 onward): P1 cycle in dependency order, tests first and\n"
    "  evidence-gated. T-062 closed GB-110..GB-116 (analytics experiments UI).\n"
    "  Remaining P1 gaps are grouped by source module for large-batch closure."
)
text = text.replace(active_old, active_new)
if "T-062:" not in text:
    text = text.replace(
        "## Active tasks",
        "- T-062: closed P1 analytics experiments cluster (GB-110..GB-116). Added an\n"
        "  Experiments table and five wired controls to the Insights view, backed by\n"
        "  the real analytics API. Fixed decimal input validation found in the browser\n"
        "  walkthrough. Evidence: `docs/evidence/analytics-experiments-p1-20261123.md`.\n\n"
        "## Active tasks",
    )
ex.write_text(text, encoding="utf-8")
print("bookkeeping updated")
