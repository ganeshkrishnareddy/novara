# Clean-room Papermark share-link presentation and hardening — evidence (T-113, 2026-11-24)

Rows closed: PM-023, PM-035, PM-036, PM-037, PM-043, PM-044, PM-046, PM-071
(8 rows).

## Source basis

Documented/public behaviour from the Papermark share-link model descriptions and
the acceptance criteria in the feature catalogue. No upstream Papermark source,
hosted instance, paid tier or external service was copied or contacted. Every
algorithm and route is a clean-room implementation derived only from the
published behaviour and the row acceptance criteria.

## Implementation

New module `apps/api/novara_core/modules/share_link_presentation.py`, registered
in `novara_core/modules/__init__.py`. Ten additive workspace-scoped `slp_*` tables
were created by Alembic revision `c8d9e0f1a2b3` (down revision `b7c8d9e0f1a2`,
single head): `slp_share_sets`, `slp_share_set_items`, `slp_domains`,
`slp_link_slugs`, `slp_og_metadata`, `slp_password_screens`,
`slp_screenshot_configs`, `slp_screenshot_attempts`, `slp_watermark_profiles`,
`slp_branding_configs`. Existing document, link and data-room rows are referenced
by id and never altered.

Per row, with `external_calls: false` and `external_delivery: false` throughout:

- **PM-023** — a multi-file share set resolves only items currently marked
  visible; hiding an item removes it from the public resolve, revoking the set
  returns 404, and a cross-workspace resolve cannot read another workspace's set.
- **PM-035** — a slug can be attached only to a verified domain; it is unique per
  domain, a conflict returns 409, and revoking the link frees the slug for reuse
  on another link.
- **PM-036** — a domain is marked verified only when the one-time token matches
  exactly; wrong tokens return 403, unknown domains 404, malformed domains 422,
  and token hashes are not exposed after creation.
- **PM-037** — Open Graph metadata is saved unapproved, hidden from the public
  preview until the owner approves it, edited metadata returns to unapproved,
  and all rendered fields are HTML-escaped.
- **PM-043** — a custom password-screen message is returned as escaped text:
  markup cannot inject an image/onerror handler, and disabling the screen hides
  the public route.
- **PM-044** — screenshot configuration states the honest limitation that OS
  capture on mobile cannot be reliably blocked; detectable attempts are logged
  locally, reported as per-channel counts, validated, and scoped to the workspace.
- **PM-046** — every configured watermark variable (`email`, `name`, `ip`,
  `date`, `time`) renders with the saved style, unknown variables are rejected
  with 422, and viewer-supplied text is escaped so it cannot inject markup.
- **PM-071** — room/link branding resolves custom > pinned > default, with
  workspace-scoped custom and pinned configuration routes and a workspace guard
  on the effective-resolution route.

Every workspace route calls `verify_workspace` and the appropriate `require()`
capability (`DOCUMENT_READ` or `DOCUMENT_WRITE`); unverified domains, revoked
links, cross-workspace references and injected text fail closed.
`share_link_presentation.changed` events are published on NOVARA's shared event
spine. All acceptance criteria are API/server-level, so no dedicated SPA surface
or dark-mode UI is claimed.

## Constraints held

All work is local: no commits, pushes, tags, deployments, publishes, upstream
source copies or real external sends. No Papermark hosted instance, paid tier,
outbound HTTP, webhook, email or external delivery is used.
`socket.socket.connect` is patched to fail for non-loopback addresses in every
acceptance test.

## Verification

| Check | Result |
|---|---|
| Targeted named suite | `apps/api/tests/test_share_link_presentation_p2.py` — **8 passed, 1 warning in 6.83s** |
| Full regression | `docs/evidence/t113-fullsuite-20261124.txt` — **859 passed, 2 warnings in 570.82s (0:09:30)**, exit 0 (`docs/evidence/t113-fullsuite-exit.txt`) |
| Alembic head | single head `c8d9e0f1a2b3`; fresh-DB `alembic upgrade head` exit 0 |
| `alembic check` | `No new upgrade operations detected`, exit 0, on a fresh DB in the project virtual environment |

The baseline before this cluster was 851 passed; the delta of 8 is exactly the
new named acceptance tests. An earlier full-suite attempt was interrupted before
it produced an exit result and was discarded; the clean run above is the record.
No production behaviour was changed outside the additive share-link tables and
the new module.
