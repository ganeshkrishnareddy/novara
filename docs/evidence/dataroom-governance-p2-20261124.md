# Clean-room Papermark data-room governance — evidence (T-111, 2026-11-24)

Rows closed: PM-050, PM-057, PM-058, PM-059, PM-060, PM-061, PM-062, PM-064,
PM-065, PM-066 (10 rows).

## Source basis

Documented/public behaviour from the Papermark data-room model descriptions and
the acceptance criteria in the feature catalogue. No upstream Papermark source,
commercial EE edition, hosted instance or external service was copied or
contacted. Every algorithm and route is a clean-room implementation derived only
from the published behaviour and the row acceptance criteria.

## Implementation

New module `apps/api/novara_core/modules/dataroom_governance.py`, registered in
`novara_core/modules/__init__.py`. Eleven additive workspace-scoped `drg_*`
tables were created by Alembic revision `a7b8c9d0e1f2` (down revision
`e6f7a8b9c1d2`, single head): `drg_room_settings`, `drg_room_events`,
`drg_room_folders`, `drg_room_item_orders`, `drg_viewer_groups`,
`drg_group_rules`, `drg_group_item_permissions`, `drg_link_item_permissions`,
`drg_link_groups`, `drg_room_invitations`, `drg_access_decisions`. No existing
table was altered.

Per row, with `external_calls: false` and `external_delivery: false` throughout:

- **PM-050** — a data room exposes permissioned documents, visitor/link counts,
  links and an append-only audit event stream, end to end.
- **PM-057** — nested room folders can be created, listed and deleted with
  parent validation.
- **PM-058** — an integer ordering field for room items persists across reads.
- **PM-059** — a viewer group is scoped to one room and can be bound to a link.
- **PM-060** — email and domain membership rules admit exactly the intended
  viewers.
- **PM-061** — per-item group view/download permissions are enforced on read.
- **PM-062** — updating a link's permission set immediately changes visibility.
- **PM-064** — room entitlement checks deny another room's document.
- **PM-065** — invitation acceptance grants only the invited room.
- **PM-066** — a frozen room rejects attach/detach/move operations.

Every route calls `verify_workspace` and the appropriate `require()` capability
(`DOCUMENT_READ`, `DOCUMENT_WRITE` or `DOCUMENT_ADMIN`); room scoping, group
rules, token/email matching, admin-only freeze and recorded access decisions
fail closed. Events `dataroom_governance.room_created` and
`dataroom_governance.room_event` are published on NOVARA's shared event spine.
Existing document, link and visitor records are reused by reference only.

## Constraints held

All work is local: no commits, pushes, tags, deployments, publishes, upstream
source copies or real external sends. The separate agents/worktrees in the
original conversation were not merged here.

## Verification

| Check | Result |
|---|---|
| Targeted named suite | `apps/api/tests/test_dataroom_governance_p2.py` — **10 passed** |
| Full regression | `docs/evidence/t111-fullsuite-20261124.txt` — **843 passed, 2 warnings in 545.79s**, exit 0 (`docs/evidence/t111-fullsuite-exit.txt`) |
| Alembic head | single head `a7b8c9d0e1f2`; fresh-DB `alembic upgrade head` exit 0 |
| `alembic check` | `No new upgrade operations detected`, exit 0, on a fresh DB in the project virtual environment |

The baseline before this cluster was 833 passed; the delta of 10 is exactly the
new named acceptance tests. No production behaviour was changed outside the
additive data-room tables and module.
