from pathlib import Path

p = Path("docs/NOVARA_AUTONOMOUS_EXECUTION.md")
text = """
### T-065 (in progress at this checkpoint)

- Four non-overlapping P1 batches are running in parallel: Chatwoot support
  named tests; Novu notifications (22 rows); Mautic marketing (21 rows);
  Sellbird safety gates (8 rows). Rows are claimed only after their named
  tests pass locally. File boundaries are disjoint so no agent overwrites
  another agent's work.
- Coordinator-owned work while those run:
  - `middleware.py` now emits `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
    `X-RateLimit-Window` and `Retry-After` on auth-endpoint responses, closing
    the missing half of PL-049.
  - New test files `test_plane_platform_p1.py` (PL-033/041/044/049/055/057/
    077/105/147/148) and `test_search_meilisearch_p1.py` (MS-006/028/062/
    063/065) were written but are NOT yet claimed: a concurrent edit in
    `crm_intelligence.py` temporarily breaks the shared import path, so the
    owning agent was asked to repair it before these tests are run.
  - Support UI evidence recorded in `docs/evidence/support-p1-ui-20261123.md`.
- Blocker B-13 added: 236 licence-restricted and 135 externally blocked rows
  cannot be closed in a clean-room local build; they stay honestly
  dispositioned instead of being silently dropped or marked complete.
"""
with p.open("a", encoding="utf-8") as fh:
    fh.write(text)
print("appended")
