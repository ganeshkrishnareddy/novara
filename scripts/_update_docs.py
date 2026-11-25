"""Append the current honest accounting to the handover and blocker register."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

handover = ROOT / "docs" / "PRODUCT_HANDOVER.md"
with handover.open("a", encoding="utf-8") as fh:
    fh.write("""

## 8. Live status at the last checkpoint (2026-11-23)

The regenerated matrix currently records **141 VERIFIED_COMPLETE** rows,
62 compatible replacements, 773 not implemented, 125 partially implemented,
236 licence-restricted, 135 external-dependency-blocked, 15 implemented but
unverified and 1 backend-only. The P0 set is fully disposed: 111 rows with
0 partial/unimplemented. Stage 2 has closed 57 P1 rows with 46 named
acceptance tests (feature flags, projects, documents) and wired their UI.

Three further P1 batches (Chatwoot support tests, Novu notifications, Mautic
marketing) were running at this checkpoint. **Their rows are not counted until
their named tests are received and pass**; no row is closed on endpoint
existence alone.

Two consolidated Alembic revisions now bring a fresh schema and an existing
dev database to the same head: `c1b2a3d4e5f6` (69 module tables) and
`6a2a87b2856b` (15 pre-existing tables with column drift). The round-trip check
passes with data preserved. The earlier check script was corrected to set
`NOVARA_DATABASE_URL`; it had silently pointed at the persistent dev database
and left a temporary table plus two synthetic rows, which were removed before
the database was stamped to head.
""")

blockers = ROOT / "docs" / "BLOCKERS.md"
with blockers.open("a", encoding="utf-8") as fh:
    fh.write("""
| B-13 | 236 catalogue rows are LICENSING_RESTRICTED and 135 are EXTERNAL_DEPENDENCY_BLOCKED | These 371 rows cannot become VERIFIED_COMPLETE in a clean-room local build without lawful clean-room replacements or owner-supplied credentials and infrastructure. They remain honestly dispositioned in the matrix and licensing register rather than being silently dropped or marked complete | Owner / legal / environment | Open |
""")

print("handover and blockers updated")
