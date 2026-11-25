# Marketing content and contact classification (Mautic P2) — evidence

Date: 2026-11-23
Scope: MT-009, MT-029, MT-031, MT-032, MT-036, MT-037, MT-048
Status: implemented locally, named acceptance tests passing.

## What was built

- `apps/api/novara_core/modules/marketing_content.py` was completed and
  registered in `novara_core.modules.MODULE_NAMES`. It provides local contact
  typing (visitor/known), landing pages with local previews and publish flags,
  progressive profiling from form fields, recorded form-submit effects,
  deterministic dynamic-content variants, validated base64 asset bundles and a
  dashboard that aggregates only locally stored rows.
- A dedicated `marketing-content` Operations route in `apps/web/app.js` exposes
  every feature with one dispatcher per control; `test_ui_wiring.py` guards the
  static wiring.
- Seven additive workspace-scoped tables were introduced by Alembic revision
  `c3d4e5f6a7b8`: `content_contact_types`, `content_landing_pages`,
  `content_forms`, `content_form_submissions`, `content_dynamic_contents`,
  `content_assets` and `content_dashboard_widgets`. The `content_` prefix avoids
  colliding with the older `marketing_forms` table owned by the existing
  `marketing` module. No existing table was altered.
- The live SQLite database was upgraded to the single head `c3d4e5f6a7b8`
  without error.

## Safety boundaries

- No Mautic source, Symfony bundle, hosted service, external storage, real
  email/SMS delivery, outbound HTTP or webhook callback is used.
- Reads require `contact:read`, writes require `contact:write`, and every
  cross-workspace id fails closed with 404.
- Form submit actions are limited to `tag`, `update_contact`, `create_task` and
  `notify`; `send_email` is rejected with 422. Every response states
  `external_calls: false` and `delivery: local-only`.
- The API contract reports `version: "1"`, `legacy_versions: []`,
  `email_sent: false` and `sms_sent: false`. No secret, token or credential is
  stored in docs, UI or logs.

## Named acceptance tests

File: `apps/api/tests/test_marketing_content_p2.py`

| Test | Matrix row | What it proves |
| --- | --- | --- |
| `test_mt009_visitor_and_known_contact_types` | MT-009 | Visitor/known classification, 409 duplicate, 422 invalid kind, local identification with details. |
| `test_mt029_landing_pages_render_and_publish_locally` | MT-029 | Unique slug, 409 duplicate, 422 invalid slug, local preview and local publish URL. |
| `test_mt031_progressive_profiling_fields` | MT-031 | Only unknown fields are returned for a known contact; a visitor sees all fields. |
| `test_mt032_form_submit_actions_are_local_effects` | MT-032 | Unknown answers and `send_email` are rejected; allowed actions are recorded as local effects. |
| `test_mt036_dynamic_content_resolves_deterministically` | MT-036 | Segment-field variants resolve deterministically with a safe default; empty variants rejected. |
| `test_mt037_asset_bundle_validates_base64` | MT-037 | Base64 is validated, size and sha256 are computed, invalid payload rejected. |
| `test_mt048_dashboard_bundle_aggregates_local_rows` | MT-048 | Counter and breakdown widgets aggregate only local rows; duplicate widget name 409. |
| `test_marketing_content_contract_and_workspace_isolation` | all | Contract denies external delivery; a second workspace sees no content. |
| `test_marketing_content_writes_require_contact_write` | all | Anonymous writes are refused with 401/403. |

Every test patches `socket.socket.connect` to raise, so any outbound traffic
fails the test immediately.

## Commands and exact results

```
cd /d D:\NOVARA
.venv\Scripts\python.exe -m pytest apps/api/tests/test_marketing_content_p2.py -q --disable-warnings
-> 9 passed, 1 warning in 8.36s

node --check apps/web/app.js
-> exit 0

.venv\Scripts\python.exe -m pytest apps/api/tests/test_marketing_content_p2.py apps/api/tests/test_support_reporting_p2.py apps/api/tests/test_ui_wiring.py apps/api/tests/test_plane_support_ui_p1.py -q --disable-warnings
-> 64 passed, 1 warning in 19.90s

cd /d D:\NOVARA\apps\api
D:\NOVARA\.venv\Scripts\python.exe -m alembic heads
-> c3d4e5f6a7b8 (head)

D:\NOVARA\.venv\Scripts\python.exe -m alembic upgrade head
-> upgraded b2c3d4e5f6a7 -> c3d4e5f6a7b8, no errors
```

Before this work the nine tests failed with 405/404 because the module existed
but its router was not registered. No test was skipped or rewritten to hide the
failure; the missing registration and tables were supplied.

## Remaining work

None for these seven rows. Other NOVARA rows keep their existing matrix status;
no upload, publish, deploy, external send or commit was performed.
