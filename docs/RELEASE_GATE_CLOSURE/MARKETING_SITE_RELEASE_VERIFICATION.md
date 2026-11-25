# Marketing site release verification — Phase B (RGC-B)

**Role:** Deployment Engineer, NOVARA Release Gate Closure.  
**Prepared:** 2026-11-25 (Asia/Calcutta, IST).  
**Method:** read-only evidence review plus one local `Get-FileHash` of `README.md`. No new deployment, Git write, external request, Docker build or provider call was made for this report. Existing working-tree changes are preserved.

## 1. Outcome

| Item | Verified finding |
|---|---|
| Live marketing site | **LIVE** at `https://ganeshkrishnareddy.github.io/novara/` (HTTP 200; checked assets HTTP 200) |
| Publication commit | `f1dcfefe162faac644e974f075a411eb0975f4cb` — 2026-11-25 11:23:25 +0530, "Publish NOVARA public marketing portal via GitHub Pages"; HEAD unchanged |
| Scope of this verification | Static public marketing site only |
| Product release verdict | **Unchanged. `LOCAL RELEASE ACCEPTED: NO` remains the governing verdict.** |
| New action in this phase | None; this report formalizes evidence already independently verified |

## 2. Pages configuration and workflow evidence

| Check | Value | Source |
|---|---|---|
| Pages state | **Enabled** | `BASELINE_RECONCILIATION.md:28,35`; `MARKETING_SITE_DEPLOYMENT_REPORT.md:9,52` |
| Build type | `workflow` | `MARKETING_SITE_DEPLOYMENT_REPORT.md:9,52` |
| Source | `main` / `/` | `MARKETING_SITE_DEPLOYMENT_REPORT.md:9,52` |
| Configured URL | `https://ganeshkrishnareddy.github.io/novara/` | `MARKETING_SITE_DEPLOYMENT_REPORT.md:9,52` |
| Workflow file | `.github/workflows/pages.yml` — `workflow_dispatch` and `push` on `site/**`, the workflow file and `scripts/validate_site.py`; `build` validates/stages/uploads, `deploy` uses `actions/deploy-pages@v4` | `.github/workflows/pages.yml:6-62` |
| Workflow run | `45556726447`, head SHA `f1dcfefe…`; first observed overall conclusion `failure` (`build` success, `deploy` failure) | `MARKETING_SITE_DEPLOYMENT_REPORT.md:36-45` |
| Successful rerun | Same run, **attempt 2**: `completed`, conclusion `success` | `MARKETING_SITE_DEPLOYMENT_REPORT.md:9,45,53` |
| Exact rerun timestamp | Not recorded in the cited evidence. Observation was updated 2026-11-25 IST; original observation was 2026-11-25 12:23 IST | `MARKETING_SITE_DEPLOYMENT_REPORT.md:3` |

## 3. Live HTTP verification

All rows below are reported as HTTP 200 in the deployment report; exact per-request timestamps were not recorded.

| Live resource | Result | Source |
|---|---|---|
| `GET https://ganeshkrishnareddy.github.io/novara/` | HTTP 200, 50,989 bytes; title and full section outline rendered | `MARKETING_SITE_DEPLOYMENT_REPORT.md:54` |
| CSS | HTTP 200 | `MARKETING_SITE_DEPLOYMENT_REPORT.md:55` |
| Logo, favicon, OG image, dashboard screenshot | HTTP 200 (named as categories in the source) | `MARKETING_SITE_DEPLOYMENT_REPORT.md:55` |
| `NOVARA_Product_Demo_2.0.mp4` | HTTP 200; embedded demo reached `readyState=4` | `MARKETING_SITE_DEPLOYMENT_REPORT.md:56` |
| `NOVARA_QA_Evidence_Walkthrough.mp4` | HTTP 200 | `MARKETING_SITE_DEPLOYMENT_REPORT.md:56` |
| `02_contacts.png`, `08_projects.png`, `10_experimentation.png` | HTTP 200 each; below the fold, therefore not decoded in the headless viewport | `MARKETING_SITE_DEPLOYMENT_REPORT.md:57` |
| `sitemap.xml` | HTTP 200 | `MARKETING_SITE_DEPLOYMENT_REPORT.md:58` |
| `robots.txt` | HTTP 200 | `MARKETING_SITE_DEPLOYMENT_REPORT.md:58` |

## 4. Validator and browser results

| Check | Exact time / window | Result | Evidence |
|---|---|---|---|
| `python scripts/validate_site.py` from `D:\NOVARA` (G-1) | 2026-11-25T13:32:10.9344321+05:30 → 13:32:11.1289976+05:30 | Exit 0; **35 passed, 0 failed, 0 warnings, 15 informational; `RESULT: PASS`** | `PHASE_G_VERIFICATION_LOG.md:9`; `PHASE_G_VALIDATOR.txt` |
| `node --check apps/web/app.js` (G-2, supporting) | 2026-11-25T13:32:27.7476232+05:30 → 13:32:27.8351770+05:30 | Exit 0; no syntax errors | `PHASE_G_VERIFICATION_LOG.md:10` |
| Live Browser-tab check (G-4) | Observed after 13:32 IST on 2026-11-25 | Title `NOVARA — Your Entire Business. One Connected System.`; canonical equals live URL; viewport 1280×720; **47 links, 6 images with 0 decode failures**; embedded demo `readyState=4`; background `rgb(255, 255, 255)` (light theme); full section outline rendered; **no console errors**; no unexpected external script/stylesheet requests | `PHASE_G_VERIFICATION_LOG.md:12,16-26`; `MARKETING_SITE_DEPLOYMENT_REPORT.md:59-60` |
| Historical **local** browser checks (not live) | 2026-11-24, re-run 2026-11-25 | 20/20 at `/` and 20/20 at local `/novara/` subpath; 0 console problems; Chromium only | `MARKETING_SITE_DEPLOYMENT_REPORT.md:26-28`; `MARKETING_WEBSITE_COMPLETION_REPORT.md:58-65` |

Note: the local validator log reports `index.html` as 50,963 characters, while the live `GET` reports 50,989 bytes. These are different measurement units on different pipelines and are not treated as a content discrepancy.

## 5. README integrity

| Check | Value |
|---|---|
| Required SHA-256 | `e3b18389a81816e43006d1667a6eff3fe6bf6ba2330168f2cfc9ba6a6767b64c` (`BASELINE_RECONCILIATION.md:13`) |
| Recomputed locally on 2026-11-25 by this agent (read-only `Get-FileHash … -Algorithm SHA256`) | `e3b18389a81816e43006d1667a6eff3fe6bf6ba2330168f2cfc9ba6a6767b64c` |
| Result | **Unchanged. No README edit was made or authorized in this phase.** |

## 6. Superseded 404 / disabled claims

| Stale claim | Where it appears | Superseded by |
|---|---|---|
| "GitHub Pages is **not enabled**"; `GET /repos/.../pages` returned HTTP 404 | `DATABASE_AND_DEPLOYMENT_REPORT.md:16-17` | Pages enabled, build type `workflow`, source `main` / `/` (`MARKETING_SITE_DEPLOYMENT_REPORT.md:9,52`) |
| "No claim is made that the site is live" | `DATABASE_AND_DEPLOYMENT_REPORT.md:18` | Live URL HTTP 200 and assets HTTP 200 (`MARKETING_SITE_DEPLOYMENT_REPORT.md:47-60`) |
| "**NOT PUBLISHED**"; expected Pages URL "not configured or verified live"; "Pages is not enabled or verified"; requires authorization before triggering the workflow | `MARKETING_WEBSITE_COMPLETION_REPORT.md:5-7,69,76,104-108` | Workflow attempt 2 `success`; site live at the configured URL |
| Campaign 2 expectation "GitHub Pages not enabled", "not live; previously HTTP 404", "Marketing site status NOT LIVE" | `BASELINE_RECONCILIATION.md:28-30` | Explicitly marked "No — superseded by new evidence" in the same file; Phase B confirms LIVE |
| Initial workflow overall `failure` / `deploy` job failure | `MARKETING_SITE_DEPLOYMENT_REPORT.md:36-45` | Historical state only; attempt 2 `completed`, conclusion `success` (`MARKETING_SITE_DEPLOYMENT_REPORT.md:45,53`) |

## 7. Boundary

The live marketing site is **NOT** proof of backend readiness, live PostgreSQL, hosted-application deployment, provider delivery, licence approval, packaging readiness or product release acceptance. Marketing-site deployment-platform verification is 100%; backend/hosted deployment-platform verification remains **0%** because no backend deployment was performed (`FINAL_RELEASE_CHECKLIST.md:33-34`; `MARKETING_SITE_DEPLOYMENT_REPORT.md:62-66`). This verification **does not change the product release verdict**: `LOCAL RELEASE ACCEPTED: NO` remains governing (`BASELINE_RECONCILIATION.md:31,77`; `FINAL_RELEASE_BLOCKERS.md:3,27-33`). No backend deployment, external message, provider call, commit, push, tag or Docker build was performed for this report.

## 8. Sources cited

- `BASELINE_RECONCILIATION.md` (lines 11, 13, 28-30, 31, 35-39, 67, 77)
- `PHASE_G_VERIFICATION_LOG.md` (lines 3, 9-10, 12, 16-26, 30)
- `PHASE_G_VALIDATOR.txt`
- `MARKETING_SITE_DEPLOYMENT_REPORT.md` (lines 3, 9, 36-45, 47-66)
- `MARKETING_WEBSITE_COMPLETION_REPORT.md` (lines 5-7, 58-65, 69, 76)
- `FINAL_RELEASE_BLOCKERS.md` (lines 3, 13, 27-33)
- `FINAL_RELEASE_CHECKLIST.md` (lines 12, 19, 33-34)
- `.github/workflows/pages.yml` (lines 6-62)
- Local read-only `Get-FileHash` of `README.md`, 2026-11-25
