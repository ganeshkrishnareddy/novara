# Clean-room Chatwoot help-centre governance — evidence (T-112, 2026-11-24)

Rows closed: CW-066, CW-067, CW-087, CW-088, CW-089, CW-090, CW-091, CW-092
(8 rows).

## Source basis

Documented/public behaviour from the Chatwoot help-centre model descriptions and
the acceptance criteria in the feature catalogue. No upstream Chatwoot source,
Captain/LLM component, paid tier, hosted instance or external service was copied
or contacted. Every algorithm and route is a clean-room implementation derived
only from the published behaviour and the row acceptance criteria.

## Implementation

New module `apps/api/novara_core/modules/help_centre_governance.py`, registered in
`novara_core/modules/__init__.py`. Ten additive workspace-scoped `hcg_*` tables
were created by Alembic revision `b7c8d9e0f1a2` (down revision `a7b8c9d0e1f2`,
single head): `hcg_portal_branding`, `hcg_categories`, `hcg_article_meta`,
`hcg_article_revisions`, `hcg_article_views`, `hcg_search_events`,
`hcg_page_visibility`, `hcg_widget_surfaces`, `hcg_content_gaps`,
`hcg_faq_index`. Existing `support_help_portals`, `support_help_articles` and
`documents` rows are referenced by id and never altered.

Per row, with `external_calls: false` and `external_delivery: false` throughout:

- **CW-066** — content gaps are advisory and derived only from stored local
  visitor-search events.
- **CW-067** — FAQ indexing accepts only workspace-authorized documents and
  retains a citation for every indexed item.
- **CW-087** — rich-text articles carry validated embeds/metadata and
  create/publish/revise persists immutable, versioned revisions.
- **CW-088** — two portals hold independent branding, categories and articles,
  with cross-portal and cross-workspace reads rejected.
- **CW-089** — article views and visitor searches are real persisted local
  events, aggregated in workspace-scoped reports.
- **CW-090** — a widget surfaces published public articles; opening one never
  creates a support ticket.
- **CW-091** — internal/private pages are invisible on every unauthenticated
  surface, including the pre-existing public help routes.
- **CW-092** — API article CRUD honours the same permission model as the staff
  UI (read-only members can read but not write).

Every route calls `verify_workspace` and the appropriate `require()` capability
(`CONTACT_READ`, `NOTE_WRITE` or `DOCUMENT_WRITE`); portal scoping, internal-page
guards, allowed-host embed validation and cross-workspace references fail closed.
`help_centre_governance.changed` events are published on NOVARA's shared event
spine. Two pre-existing public help routes in `support.py` were extended with a
lazy, import-cycle-safe internal-page guard so private articles cannot leak
through them.

## Constraints held

All work is local: no commits, pushes, tags, deployments, publishes, upstream
source copies or real external sends. No email, webhook, LLM embedding service or
outbound HTTP is used. `socket.socket.connect` is patched to fail for non-loopback
addresses in every acceptance test.

## Verification

| Check | Result |
|---|---|
| Targeted named suite | `apps/api/tests/test_chatwoot_help_centre_p2.py` — **8 passed** |
| Full regression | `docs/evidence/t112-fullsuite-20261124.txt` — **851 passed, 2 warnings in 548.08s**, exit 0 (`docs/evidence/t112-fullsuite-exit.txt`) |
| Alembic head | single head `b7c8d9e0f1a2`; fresh-DB `alembic upgrade head` exit 0 |
| `alembic check` | `No new upgrade operations detected`, exit 0, on a fresh DB in the project virtual environment |

The baseline before this cluster was 843 passed; the delta of 8 is exactly the
new named acceptance tests. The first full-suite attempt hit a pre-existing
order-dependent flake in `test_mt033_scoring_rules_apply_with_history` (history
rows ordered by a random-UUID tie-break when timestamps collide); that test
passes in isolation and the clean run above supersedes the discarded result. No
production behaviour was changed outside the additive help-centre tables, the
two internal-page guards on public help routes, and the new module.
