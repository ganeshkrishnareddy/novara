# Final release blockers — Campaign 2

Original timestamp: 2026-11-25 12:31 IST. Updated 2026-11-25 (IST) after marketing-site live deployment. Verdict: **LOCAL RELEASE ACCEPTED: NO.**

Campaign 2 attached per-feature evidence to the 737 formerly `NOT_TESTED` rows and documented the 221 `BLOCKED_EXTERNAL` rows by dependency group. The conservative final acceptance statuses were deliberately not promoted: a named local test pass is not the same as product release acceptance, and no live provider was contacted.

## Blocking conditions

| # | Blocker | Owner | Release impact | Evidence |
|---|---|---|---|---|
| B-01 | 737 rows remain `NOT_TESTED` in the final acceptance status column | Release owner | Blocks any full feature-acceptance or release-accepted claim | `FEATURE_BY_FEATURE_ACCEPTANCE.csv`, `FINAL_FEATURE_ACCEPTANCE_REGISTRY.csv`, `NOT_TESTED_FEATURE_CLOSURE_REPORT.md` |
| B-02 | 221 rows remain `BLOCKED_EXTERNAL`; live provider verification is 0/21 | Release owner / integration owner | Blocks live experimentation, campaign delivery, webhooks and hosted AI claims | `EXTERNAL_BLOCKER_RESOLUTION_REPORT.md`, `INTEGRATION_ACCEPTANCE_REPORT.md` |
| B-03 | **RESOLVED** — GitHub Pages enabled; marketing site live at `https://ganeshkrishnareddy.github.io/novara/` with HTTP 200 assets | Repository owner | Marketing-site deployment-platform verification now 100%; backend/hosted deployment still 0% | `MARKETING_SITE_DEPLOYMENT_REPORT.md` |
| B-04 | NOVARA's own licence file is not chosen | Owner | Blocks a fully open-source/public-release claim | `LICENSING_EXCEPTION_REGISTER.md`, `RELEASE_BLOCKERS.md` |
| B-05 | Docker, live PostgreSQL, hosted deployment and signed installers unverified | Owner / infrastructure | Blocks deployment and packaging claims | `DATABASE_AND_DEPLOYMENT_REPORT.md`, `KNOWN_LIMITATIONS.md` |
| B-06 | Name, trademark and domain availability not checked | Owner | Blocks public naming/domain claim | `RELEASE_BLOCKERS.md` |
| B-07 | README has advisory gaps: no explicit Star/Fork/PR URLs in README (site has them) | Docs owner | Documentation improvement, not a code defect | `README_AND_COMMUNITY_AUDIT.md` |
| B-08 | Non-Chromium browsers and formal penetration test not verified | QA owner | Blocks broad browser/security claims | `SECURITY_AND_REGRESSION_REPORT.md`, `UI_UX_ACCESSIBILITY_REPORT.md` |

## What was resolved in Campaign 2

- All 737 formerly `NOT_TESTED` rows received individual execution records and evidence references; no row was accepted by a broad sweep alone.
- All 221 `BLOCKED_EXTERNAL` rows were grouped by dependency class with credentials, owner, release impact and local/sandbox/live boundary recorded.
- Fresh local workflow, integration, security and regression samples passed; these are local verification, not external delivery or deployment verification.
- Marketing-site build job passed initially; after Pages enablement the rerun succeeded and the live URL/assets were verified.

## What must happen before release acceptance

1. Owner decision on the conservative final statuses: explicit authorization is required before any `NOT_TESTED` or `BLOCKED_EXTERNAL` row is promoted to `PASS`.
2. Marketing-site launch is complete. Remaining owner actions concern licence, packaging, external providers and product release acceptance, not the public marketing page.
3. Licence file, name/trademark/domain and packaging decisions are completed.
4. If live integrations are desired, explicit authorization, isolated credentials and provider-specific evidence are required. No silent provider call is permitted.
5. Full regression must be rerun after any application or test repair.
