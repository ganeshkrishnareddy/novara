# Release blockers and open decisions

Timestamp: 2026-11-25 11:45 IST.

## Publication blocker (action required by owner)
1. **GitHub Pages is not enabled** for `ganeshkrishnareddy/novara`. The Pages workflow build succeeded but
   the deploy job failed. Enable it in repository **Settings → Pages → Build and deployment → Source: GitHub Actions**,
   then re-run the workflow. No live URL can be claimed until that succeeds.

## Product release blockers (owner or environment)
2. **NOVARA's own licence file is not chosen** (`B-03`). Blocks a fully open-source claim and a public release.
3. **Docker / live PostgreSQL / hosted deployment / signed installers** are unverified (`B-01`, `B-06`, `B-08`).
4. **External provider credentials absent** — Gmail, Microsoft 365, WhatsApp, SMS, AI providers (`B-07`).
   Provider-backed features stay `BLOCKED_EXTERNAL`; no fake delivery is reported.
5. **Name, trademark and domain availability not checked** (`B-04`).

## Acceptance evidence gap (not a defect, but blocks "release accepted")
6. **737 features are `NOT_TESTED` and 221 are `BLOCKED_EXTERNAL`** in the final acceptance registry.
   Only 28 are individually `PASS` and 70 `REPLACEMENT_VERIFIED`. The strict LOCAL RELEASE ACCEPTED gate
   is therefore **not met**, regardless of the 100% local test-suite pass rate.

Evidence: `../../docs/BLOCKERS.md`, `FEATURE_BY_FEATURE_ACCEPTANCE.csv`, `MARKETING_WEBSITE_LAUNCH_REPORT.md`.
