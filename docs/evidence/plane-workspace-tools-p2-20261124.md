# Clean-room Plane workspace tools — evidence (T-110, 2026-11-24)

Rows closed: PL-089, PL-091, PL-092, PL-093, PL-107, PL-137, PL-138, PL-139,
PL-142, PL-145 (10 rows).

## Source basis

Documented/public behaviour from the Plane docs sitemap and the audit notes held
in the feature catalogue. No upstream Plane source, Django/React package, hosted
Plane instance or external service was copied or contacted. Every algorithm and
route is a clean-room implementation derived only from the acceptance criteria.

## Implementation

New module `apps/api/novara_core/modules/plane_workspace_tools.py`, registered in
`novara_core/modules/__init__.py`. Eleven additive workspace-scoped tables
(`pwt_*`) were created by Alembic revision `e6f7a8b9c1d2` (down revision
`d5e6f7a8b9c0`): `pwt_intake_forms`, `pwt_intake_requests`, `pwt_user_assets`,
`pwt_workspace_assets`, `pwt_stickies`, `pwt_theme_preferences`,
`pwt_customer_links`, `pwt_releases`, `pwt_release_items`, `pwt_votes`,
`pwt_nav_items`. No existing table was altered.

Per row, with `external_calls: false` and `external_delivery: false` throughout:

- **PL-089** — intake form definitions store typed field rules; a token-scoped
  `/api/v1/intake/{token}/submit` route validates required/email/number/boolean
  fields and unknown keys, then creates exactly one intake request per valid
  submission. Invalid submissions create nothing.
- **PL-091** — user asset metadata CRUD is scoped to `owner_id` plus workspace;
  another member's list excludes the row and their patch/delete returns 404.
- **PL-092** — workspace asset metadata CRUD requires `workspace:manage`;
  non-admins get 403 on mutation, and a foreign workspace is denied.
- **PL-093** — sticky CRUD is private to owner plus workspace, with colour,
  formatted flag and note text; other members get an empty list and 404.
- **PL-107** — theme preference upserts per `(workspace, user, scope)` and
  persists across reads; workspace-wide themes require `workspace:manage`.
  NOVARA's light-theme-only governance is enforced in the model (`mode=light`).
- **PL-137** — a small tokenizer and recursive-descent parser convert a filter
  expression into a structured predicate tree (fields whitelisted; comparison
  operators and `CONTAINS` only). No SQL string is ever built. Injection markers
  (`;`, `--`, `/*`, SQL verbs) and malformed predicates return 422. Evaluation
  runs against caller-supplied records in memory.
- **PL-138** — a NOVARA `contacts` row and a `ProjectItem` in the same workspace
  are linked once; `contact:read` is preserved alongside `contact:write`, a
  read-only member is denied 403, and cross-workspace ids return 404.
- **PL-139** — releases persist with a planned status and link work items
  idempotently; a list read returns every linked item id (no data loss).
- **PL-142** — one vote/reaction per `(workspace, item, user)` toggles off on a
  repeat of the same value and switches on a different value; counts are derived
  from persisted rows.
- **PL-145** — navigation items carry visibility and allowed roles. The SPA list
  omits hidden/disallowed items, and the server-side direct-URL guard
  `/nav/target/{key}` returns 404 when hidden and 403 when the role is not
  allowed. Owner role always passes.

Every mutation publishes a `workspace_tools.*` event to NOVARA's shared event
spine; errors are 401/403/404/409/422 with no credential or secret in the body.

## Verification (from `D:\NOVARA`)

- Targeted acceptance suite `apps/api/tests/test_plane_workspace_tools_p2.py`:
  **10 passed, 1 warning in 9.97s** (one named test per row).
- Full API suite: **833 passed, 2 warnings in 520.04s (0:08:40), exit 0**
  (`docs/evidence/t110-fullsuite-20261124.txt`, exit code in
  `docs/evidence/t110-fullsuite-exit.txt`). Baseline before this cluster was
  823 passed; the delta is exactly the ten new named tests.
- `node --check apps/web/app.js`: exit 0 (no frontend file changed).
- `alembic heads`: `e6f7a8b9c1d2` (single head). Strict round trip from the prior
  head `d5e6f7a8b9c0` passed upgrade -> downgrade -> upgrade with existing data
  preserved, and fresh-database `alembic check` reported no new operations.
- The long-lived dev database already contained the new tables via the shared
  metadata's startup `create_all`; its version marker was stamped forward to the
  single head. No data was destroyed.

## Honest limits

No SPA surface is claimed: the acceptance criteria for these rows are API- and
server-level, including a real server-side direct-URL guard for hidden
navigation. No real file upload/storage backend, external identity provider,
hosted service, outbound HTTP, real email/message delivery or analytics vendor
is involved. NOVARA is not 100% complete. No commit, push, tag, deployment,
publishing or external send was made.
