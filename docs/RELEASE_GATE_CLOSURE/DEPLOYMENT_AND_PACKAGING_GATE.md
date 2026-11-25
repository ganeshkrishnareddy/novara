# Deployment and packaging gate — Phase E (RGC-E)

**Role:** Deployment Engineer, NOVARA Release Gate Closure.  
**Prepared:** 2026-11-25 (Asia/Calcutta, IST).  
**Method:** read-only review of existing files and reports. No commit, push, tag, reset, clean, Docker build, container run, database run, hosted deployment, installer build, live/external request or message was made. Only the two assigned Phase B/Phase E reports were written; all pre-existing working-tree changes are preserved.

## 1. Verdict

**Verdict: RELEASE_BLOCKED**

No Docker image build, live PostgreSQL, hosted application deployment, signed installer, mobile package or production release has been performed or verified. The live Pages site is a static marketing publication only and does not close this gate. The governing campaign verdict remains `LOCAL RELEASE ACCEPTED: NO` (`FINAL_RELEASE_BLOCKERS.md:3`; `BASELINE_RECONCILIATION.md:77`).

## 2. Packaging and deployment files that exist

| Path | What is present | Source |
|---|---|---|
| `Dockerfile` | `python:3.12-slim`; installs `.[postgres,migrate]`; copies `apps/api/pyproject.toml`, `novara_core` (including vendored skills), `alembic.ini`, `migrations` and `apps/web`; non-root user `novara` (uid 10001); `/data` volume; `EXPOSE 8000`; `/health` healthcheck; `CMD` runs `alembic upgrade head && uvicorn novara_core.main:app --host 0.0.0.0 --port 8000` | `Dockerfile:1-36` |
| `docker-compose.yml` | `app` service (`build: .`, `8000:8000`, `NOVARA_DB_PATH=/data/novara.sqlite3`, `novara-data` volume, `restart: unless-stopped`); opt-in `db` service `postgres:16-alpine` under profile `postgres` with literal development values `novara`/`novara`/`novara`, `pg_isready` healthcheck and `novara-postgres` volume; no Redis required | `docker-compose.yml:1-35` |
| `.github/workflows/pages.yml` | Static-site Pages workflow: validate with `python scripts/validate_site.py`, stage `site-dist`, upload artifact, deploy via `actions/deploy-pages@v4`; permissions `contents: read`, `pages: write`, `id-token: write` | `.github/workflows/pages.yml:6-62` |
| `scripts/validate_site.py` | Local static-site validator; used in the workflow and in Phase G | `.github/workflows/pages.yml:39-40`; `PHASE_G_VERIFICATION_LOG.md:9` |
| `site/` | Static marketing site published through Pages | `MARKETING_SITE_DEPLOYMENT_REPORT.md:11-19` |
| `apps/api/alembic.ini`, `apps/api/migrations/` | Alembic configuration and migration versions, including the current head revision | `Dockerfile:16-17`; `apps/api/migrations/versions/b5c6d7e8f9a0_marketing_local_delivery_runs.py:1-45` |
| `THIRD_PARTY_NOTICES.md` | Root attribution notices for upstream components; **not** copied into the Docker image | `LICENSE_AND_COMPLIANCE_GATE.md:43,76-82,127-129` |
| `apps/api/novara_core/skills/vendor/marketingskills/2.14.25/` | Vendored MIT Marketing Skills bundle (53 skills / 400 manifest-listed files, ~4.2 MB); copied into the image by `Dockerfile:15` | `LICENSE_AND_COMPLIANCE_GATE.md:65,84-89,127` |

Notably absent or unverified in the cited evidence: a pinned lockfile/constraints file, an SBOM from a built image, a NOVARA root licence file, a signed installer, a native mobile package and any hosted deployment manifest for the API.

## 3. Verified versus not verified

| Item | Status | Evidence / boundary |
|---|---|---|
| Static marketing site publication | **VERIFIED** | Pages enabled (`workflow`, `main` / `/`); run `45556726447` attempt 2 `success`; live URL and checked assets HTTP 200 — `MARKETING_SITE_RELEASE_VERIFICATION.md`; `MARKETING_SITE_DEPLOYMENT_REPORT.md:47-64` |
| Local static validator / JS syntax | **VERIFIED (local)** | 35 passed / 0 failed / 0 warnings / 15 informational, exit 0; `node --check` exit 0 — `PHASE_G_VERIFICATION_LOG.md:9-10` |
| Current Alembic single head in local code | **VERIFIED (local code state)** | Single head `b5c6d7e8f9a0`; see §4. No live database migration was applied |
| Backend regression baseline | **VERIFIED (historical local baseline only)** | `python -m pytest apps/api/tests -q`: 1,641 passed, 4 warnings, exit 0 in 1267.47s (`REGRESSION_TEST_REPORT.md:7`). It predates the later local marketing migration and does not validate that migration or any later change |
| Docker image build | **NOT VERIFIED** | `Dockerfile` exists, but no build was performed in this gate or evidenced as performed by owner/infrastructure — `FINAL_RELEASE_BLOCKERS.md:15`; `MARKETING_WEBSITE_COMPLETION_REPORT.md:72` |
| Container run / healthcheck at `8000/health` | **NOT VERIFIED** | No container was started; healthcheck is declared only |
| Live PostgreSQL (`docker compose --profile postgres up`) | **NOT VERIFIED** | `db` service is defined but was not run; no live PostgreSQL connection was tested |
| Hosted application deployment | **NOT VERIFIED** | Backend/hosted deployment-platform verification remains 0% (`FINAL_RELEASE_CHECKLIST.md:34`); no hosted API/UI deployment performed |
| Signed installers / desktop packages | **NOT VERIFIED** | B-05 open (`FINAL_RELEASE_BLOCKERS.md:15`) |
| Native mobile apps / packages | **NOT VERIFIED** | "No native mobile apps" (`MARKETING_WEBSITE_COMPLETION_REPORT.md:72`) |
| External provider delivery, webhooks, hosted AI | **NOT VERIFIED / owner-blocked** | Live provider verification 0/21; 221 `BLOCKED_EXTERNAL` rows (`FINAL_RELEASE_BLOCKERS.md:12`; `FINAL_RELEASE_CHECKLIST.md:32`) |
| Real email / SMS / WhatsApp send | **NOT VERIFIED** | Local approval-gated delivery records only; see §5 |
| Product release acceptance | **NOT MET** | Release gate NOT MET — `FINAL_RELEASE_CHECKLIST.md:25` |

## 4. Alembic head reconciliation

| Item | Finding |
|---|---|
| Current head | **`b5c6d7e8f9a0` — single head**, independently verified. Migration file declares `revision = "b5c6d7e8f9a0"`, `down_revision = "e0f1a2b3c4d5"`, `Create Date: 2026-11-25` (`apps/api/migrations/versions/b5c6d7e8f9a0_marketing_local_delivery_runs.py:3-17`) |
| Nature of the change | Additive, workspace-scoped `marketing_local_runs` table; no existing table altered, no external provider introduced; carries approval decision and correlation id tying audience, campaign, local delivery adapter and analytics trail together (same file, lines 1-10 and 22-41) |
| Phase G head | `PHASE_G_VERIFICATION_LOG.md:11` records `e0f1a2b3c4d5 (head)` at 2026-11-25T13:32:43.4991230+05:30 → 13:32:45.2833603+05:30; `PHASE_G_ALEMBIC_HEADS.txt` contains `e0f1a2b3c4d5 (head)` |
| Status of the Phase G value | **Superseded by later local code.** It is a checkpoint value, not the current head. No deployment or live migration is implied by either value |
| Related stale statement | `PHASE_G_VERIFICATION_LOG.md:30` says no database migration changed after the regression baseline; the later additive local marketing migration contradicts that statement for the period after the Phase A/G checkpoint. No fresh full-suite run was performed in this gate |
| Deployment effect | None. `Dockerfile:36` would run `alembic upgrade head` at container start, but no container was built or started, so the migration was not applied to any hosted or live database |

## 5. Local marketing boundary — not a deployment

- The public site card for "02 Marketing" now reads **"Local workflow verified"** instead of "Delivery not executed" (`site/index.html:266`).
- The change reflects a local, approval-gated delivery-run API that records audience, campaign, approval, local-only delivery traces and analytics. It explicitly states that **no email, SMS or WhatsApp message is sent** (`apps/api/tests/test_marketing_delivery_local_run.py:246-267`).
- The supporting migration creates only a local run record with `audience_count`, `blocked_count`, `delivered_count`, `approved_by`, `approved_at` and `executed_at`; it introduces no provider transport (`apps/api/migrations/versions/b5c6d7e8f9a0_marketing_local_delivery_runs.py:1-10,22-41`).
- Historical cached browser artifacts still contain the old string "Delivery not executed" (for example `artifacts/marketing_site_qa/subpath_root/novara/index.html:266` and the `profile_*` cache files). These are stale local captures, not the live-page state and not a deployment record.
- This boundary is a local workflow verification only. It does not close B-02, does not constitute external delivery and does not change the deployment verdict.

## 6. Notice and SBOM gaps blocking distribution

| Gap | Observed fact | Required action before image/distribution release |
|---|---|---|
| NOVARA licence absent | No root `LICENSE`/`LICENSE.md`/`LICENSE.txt`/`COPYING`; no licence metadata in `apps/api/pyproject.toml` (`LICENSE_AND_COMPLIANCE_GATE.md:12-14,43-47`) | Owner chooses a licence or explicitly keeps B-04 open; authorised task then adds the licence file and metadata |
| MIT notices not shipped with image | `Dockerfile:14-21` copies `novara_core` (including the vendored MIT bundle) but not `THIRD_PARTY_NOTICES.md` (`LICENSE_AND_COMPLIANCE_GATE.md:127-129`) | Copy/preserve notices and the vendored `LICENSE` into the image or ship an image licence manifest/SBOM |
| Unpinned dependencies, no SBOM | `apps/api/pyproject.toml` uses only `>=` lower bounds; `Dockerfile:18-19` runs `pip install --upgrade pip` and resolves fresh; no lockfile/constraints and no SBOM from a built image (`LICENSE_AND_COMPLIANCE_GATE.md:18,140`) | Produce a pinned lockfile/constraints file and generate an SBOM from the **built image**, then attach notices to distributions |
| `psycopg[binary]` review | Declared via `postgres` extra and installed by `Dockerfile:19`; PyPI metadata reports `LGPL-3.0-only`; `binary` extra adds binary/libpq components (`LICENSE_AND_COMPLIANCE_GATE.md:120,141`) | Review exact resolved version, binary-component notices and relinking/source obligations before image distribution |
| `certifi` / Apache-dual / base images | `certifi` observed locally as MPL-2.0; Apache-2.0 group and `packaging` dual-licence need notice retention; `python:3.12-slim` carries PSF/Debian terms and `postgres:16-alpine` carries PostgreSQL/Alpine/musl/BusyBox terms (`LICENSE_AND_COMPLIANCE_GATE.md:118-119,129,142-146`) | Confirm `certifi` unmodified, include MPL text, preserve Apache/NOTICE files, resolve dual-licence choice and enumerate base-image components in the SBOM |
| Stale "no source copied" statements | `THIRD_PARTY_NOTICES.md:3`, `README.md:355-356,534`, `site/index.html:216`, vendored `PROVENANCE.md` and two parity docs conflict with the actually vendored 53-skill/400-file MIT bundle (`LICENSE_AND_COMPLIANCE_GATE.md:91-105`) | Owner-authorised correction to accurate wording; keep all MIT notices and provenance intact. **This gate did not edit `README.md`**; its SHA-256 remains `e3b18389a81816e43006d1667a6eff3fe6bf6ba2330168f2cfc9ba6a6767b64c` |

## 7. Exact owner decisions and actions required

| ID | Owner decision / action | Source |
|---|---|---|
| B-01 | Explicitly authorize before promoting any `NOT_TESTED` row to `PASS`; no automatic promotion from named local evidence | `FINAL_RELEASE_BLOCKERS.md:11,29` |
| B-02 | Provide explicit authorization and isolated credentials before any live provider verification; no silent provider call | `FINAL_RELEASE_BLOCKERS.md:12,32`; `FINAL_RELEASE_CHECKLIST.md:42` |
| B-03 | **Resolved** — marketing site live; no further owner action for the public page | `FINAL_RELEASE_BLOCKERS.md:13`; `FINAL_RELEASE_CHECKLIST.md:38` |
| B-04 | Choose NOVARA's licence from the documented options, or explicitly keep B-04 open; authorize a separate implementation task for licence file + `pyproject.toml` metadata, stale-statement corrections, `PROVENANCE.md` update, image notices/SBOM, and `psycopg[binary]`/`certifi` review | `LICENSE_AND_COMPLIANCE_GATE.md:184-195`; `FINAL_RELEASE_BLOCKERS.md:14` |
| B-05 | Authorize and then verify (by owner/infrastructure, not this read-only gate) a Docker image build, container run/healthcheck, live PostgreSQL under the `postgres` profile, hosted API/UI deployment and signed installers before any deployment/packaging claim | `FINAL_RELEASE_BLOCKERS.md:15`; `FINAL_RELEASE_CHECKLIST.md:41`; `MARKETING_WEBSITE_COMPLETION_REPORT.md:72` |
| B-06 | Complete name, trademark and domain availability review | `FINAL_RELEASE_BLOCKERS.md:16`; `FINAL_RELEASE_CHECKLIST.md:43` |
| B-07 | Decide on the README advisory gap (explicit Star/Fork/PR URLs); any edit must be a separate owner-authorized task because the audited README hash is unchanged here | `FINAL_RELEASE_BLOCKERS.md:17`; `FINAL_RELEASE_CHECKLIST.md:39` |
| B-08 | Commission non-Chromium browser checks and a formal penetration test before broad browser/security claims | `FINAL_RELEASE_BLOCKERS.md:18` |
| Regression | Authorize a fresh full backend-suite run after the later local marketing migration and before any release acceptance claim; the 1,641-pass baseline predates it | `REGRESSION_TEST_REPORT.md:7`; `PHASE_G_VERIFICATION_LOG.md:30`; `FINAL_RELEASE_BLOCKERS.md:33` |
| Boundary | Maintain the clean-room boundary: no AGPL/GPL/EE/proprietary source copying and no EE credential or paid tier as a dependency; obtain legal review before treating AGPL/GPL upstreams as separate network services | `LICENSE_AND_COMPLIANCE_GATE.md:193` |
| Messaging | Until licence implementation completes, use exactly `open-source foundation subject to final repository licensing review; licence file pending owner decision.` Do not publish "fully open source", "openly licensed release" or third-party endorsement claims | `LICENSE_AND_COMPLIANCE_GATE.md:194`; `site/index.html:318,416` |

No owner decision above was made, assumed or fabricated in this report.

## 8. Sources cited

- `Dockerfile:1-36`; `docker-compose.yml:1-35`; `.github/workflows/pages.yml:6-62`
- `MARKETING_SITE_RELEASE_VERIFICATION.md` (this campaign, Phase B); `MARKETING_SITE_DEPLOYMENT_REPORT.md:3,47-66`
- `PHASE_G_VERIFICATION_LOG.md:9-11,30`; `PHASE_G_ALEMBIC_HEADS.txt`; `PHASE_G_VALIDATOR.txt`
- `apps/api/migrations/versions/b5c6d7e8f9a0_marketing_local_delivery_runs.py:1-45`
- `apps/api/tests/test_marketing_delivery_local_run.py:246-267`; `site/index.html:266,318,416`
- `REGRESSION_TEST_REPORT.md:7-17`; `DATABASE_AND_DEPLOYMENT_REPORT.md:5-19`
- `LICENSE_AND_COMPLIANCE_GATE.md:12-19,43-47,65,84-105,113-148,184-204`
- `FINAL_RELEASE_BLOCKERS.md:3,9-18,27-33`; `FINAL_RELEASE_CHECKLIST.md:15,25,33-45`
- `MARKETING_WEBSITE_COMPLETION_REPORT.md:5-7,67-76,104-108`
- `BASELINE_RECONCILIATION.md:31,45-63,77`
