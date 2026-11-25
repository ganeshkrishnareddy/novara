# Evidence — PL clean-room P1 extensions (2026-11-23)

## Scope

Four P1 rows that were previously LICENSING_RESTRICTED are now backed by an
independent clean-room implementation. No Plane source was consulted, copied or
embedded; the code is derived solely from the acceptance criteria and NOVARA's
own workspace/permission/event contracts.

Implementation: `apps/api/novara_core/modules/project_extensions.py`, registered
in `modules/__init__.py`, with additive migration
`e7d2c4b8a1f6_project_extensions_cleanroom.py`.

Named suite: `apps/api/tests/test_p1_project_extensions_cleanroom.py`
(4 tests, all passing against the real FastAPI app).

| Row | Named test | What is proven |
| --- | --- | --- |
| PL-019 | `test_pl019_milestones_link_work_and_render_on_a_timeline` | a milestone has a target date, links to a real work item, rejects duplicates, and appears with its linked item on an ordered timeline; cross-workspace timeline access is denied |
| PL-028 | `test_pl028_custom_properties_enforce_types_and_mandatory_rules` | typed definitions (select/number), duplicate-key and missing-options rejection, mandatory rules, unknown keys, invalid option and wrong type all return 422, and valid values round-trip |
| PL-116 | `test_pl116_resource_grants_override_role_defaults_and_deny_wins` | an explicit deny overrides an owner's role grant, an explicit allow grants a read-only member one resource, grants do not leak between users, and the fallback reports `source: role` |
| PL-117 | `test_pl117_audit_view_is_admin_only_filterable_and_exportable` | immutable events are ordered, filterable by type and entity, exportable as CSV, and return 403 for a read-only member and 403/404 for a foreign workspace |

## Verification

- Targeted: 4 passed.
- Full API suite after integration: see `docs/TEST_RESULTS.md` and the execution
  record for the authoritative count.
- Single Alembic head (`e7d2c4b8a1f6`); strict migration-only round trip passes;
  `alembic check` reports no new upgrade operations.

## Honest limits

These are NOVARA-native equivalents, not Plane features. There is no Plane
installation, no AGPL source reuse, no hosted Plane instance and no claim that
paid Plane-only behaviour was observed. The audit view reads NOVARA's append-only
event table; the CSV export is local and never leaves the workspace.
