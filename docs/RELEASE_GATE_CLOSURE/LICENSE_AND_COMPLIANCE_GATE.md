# License and Compliance Gate — owner decision report (RGC-C)

**Role:** License and Compliance Reviewer, NOVARA Release Gate Closure.
**Timestamp:** 2026-11-25 (Asia/Calcutta).
**Project root:** `D:\NOVARA\`.
**Method:** read-only inspection only. No licence was chosen or applied; no file other than this report was written; no commit, push, tag, deploy or external message was made. Existing working-tree changes are preserved.

## 1. Bottom line for the owner

| Question | Finding |
|---|---|
| Gate status | **NOT CLOSED.** Blocker B-04 remains open: NOVARA's own licence file does not exist. |
| Current licence status | No root `LICENSE` / `LICENSE.md` / `LICENSE.txt` / `COPYING` and no licence metadata in `apps/api/pyproject.toml`. Repository is source-visible, not licensed. |
| Can NOVARA honestly be called open source today? | **No.** Viewable source is not a licence grant. The only honest wording is the existing caution phrase: `open-source foundation subject to final repository licensing review; licence file pending owner decision.` |
| Ten inspirations | Only some upstream paths are permissive. Four projects have AGPL/GPL core copyleft, several have enterprise/proprietary splits, and one has a version-based MIT→AGPL split. Clean-room/API posture avoids inheriting those terms today. |
| Unrestricted reuse assumption | **Rejected.** No blanket claim of unrestricted reuse is supportable. |
| Attribution | MIT notices are catalogued and the vendored Marketing Skills MIT notice is preserved, but several repository statements claiming "no source/content copied" are now factually stale and must be corrected. |
| Distribution | Docker image copies the vendored MIT bundle into `novara_core`; notices must travel with the image. Dependency set is unpinned and needs an SBOM/lockfile review. |
| Reviewer's default recommendation | **MIT** (lowest-friction, matches current clean-room design and vendored MIT content). **Apache-2.0** if an explicit patent grant is preferred. Do not choose AGPL/GPL unless the owner accepts combined-work copyleft and network source-offer duties. Do not choose source-available unless the owner is willing to change the VISION/README/site claims. |

**Owner decision requested:** choose one licence for NOVARA, or explicitly keep B-04 open. This report does not choose one.

---

## 2. Evidence inspected (read-only)

- Root: `THIRD_PARTY_NOTICES.md`; absence of root licence files; `README.md` §21, §27 and FAQ; `Dockerfile`; `docker-compose.yml`.
- `docs/research/LICENSE_COMPLIANCE.md` (upstream terms, URLs, resolved 2026-11-22).
- `docs/FEATURE_PARITY/LICENSING_EXCEPTION_REGISTER.md`.
- `docs/FEATURE_PARITY/SOURCES/09-marketingskills.md` and `docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv` (as cited by the QA audit).
- `docs/research/repos/04-marketingskills-sellbird.md` (as cited by the inventory).
- `docs/FINAL_RELEASE_QA/LICENSING_CLAIMS_AUDIT.md`, `FINAL_RELEASE_BLOCKERS.md`, `FINAL_RELEASE_CHECKLIST.md`, `TEN_SOURCE_PROJECT_COMPLETION_REPORT.md`, `TEN_SOURCE_PROJECT_ACCEPTANCE_REPORT.md`, `AUDIT_RECONCILIATION.md`.
- `docs/RELEASE_GATE_CLOSURE/BASELINE_RECONCILIATION.md`.
- `apps/api/pyproject.toml`; `Dockerfile`; `docker-compose.yml`; `.github/workflows/pages.yml`.
- `apps/api/novara_core/modules/marketing_skills.py`; vendored bundle `apps/api/novara_core/skills/vendor/marketingskills/2.14.25/` (`LICENSE`, `MANIFEST.json`, `PROVENANCE.md`, 53 skill directories).
- `apps/web/` and `site/index.html` for third-party assets/CDN references; `.venv/Lib/site-packages/*.dist-info/METADATA` for locally installed licence identifiers; PyPI metadata for `psycopg` (read-only HTTP metadata fetch, 2026-11-25).
- Git state: HEAD `f1dcfefe162faac644e974f075a411eb0975f4cb`; working tree contains 18 modified tracked files and many untracked paths, preserved unchanged.

---

## 3. Current repository licence status

1. **No NOVARA licence grant exists.** A case-insensitive scan of the repository root found no `LICENSE`, `LICENSE.md`, `LICENSE.txt`, `COPYING` or root `NOTICE`. The only root notice file is `THIRD_PARTY_NOTICES.md`, which is attribution for others' work, not a grant of NOVARA rights.
2. **No package metadata declares a licence.** `apps/api/pyproject.toml:1-26` has `name`, `version`, dependencies and build configuration, but no `license`, `license-expression` or licence classifier. `novara_core-0.1.0.dist-info` in `.venv` likewise has no licence expression.
3. **Current honest wording is present and correct.** `README.md:351-364` states that upstream review is complete, that NOVARA's own licence file does not exist, requires the exact phrase `open-source foundation subject to final repository licensing review; licence file pending owner decision.`, and says `Do not describe NOVARA as an openly licensed release.` The same phrase appears in the FAQ (`README.md:458-460`) and `site/index.html:318,416`. `LICENSING_CLAIMS_AUDIT.md:25-31,74` confirms both occurrences in README and site.
4. **Gate blocker is open.** `FINAL_RELEASE_BLOCKERS.md:14` lists B-04 (`NOVARA's own licence file is not chosen`) as blocking a fully open-source/public-release claim; `BASELINE_RECONCILIATION.md:51` confirms B-04 is still open; `FINAL_RELEASE_CHECKLIST.md:39` tells the owner to choose a licence.
5. **No choice was made in this review.** Under default copyright, all rights are reserved until the owner grants a licence. The live GitHub Pages marketing site changes nothing about licence status.

---

## 4. Compatibility findings — the ten source-project inspirations

The authoritative upstream terms are `docs/research/LICENSE_COMPLIANCE.md:13-27` and per-repository findings at lines 30-128; notice texts are in `THIRD_PARTY_NOTICES.md`. "Compatibility" below assumes NOVARA keeps its current clean-room/no-copy posture. **Do not assume unrestricted reuse.**

| # | Inspiration | Actual upstream terms | Current NOVARA posture / evidence | Compatibility with candidate NOVARA licences |
|---|---|---|---|---|
| 1 | Formbricks | Community core **AGPL-3.0**; `apps/web/modules/ee` Formbricks EE (commercial, no redistribution); selected SDK packages MIT per `package.json`. | Clean-room survey/feedback runtime; no server source copied; no EE path; no SDK currently declared (`LICENSE_COMPLIANCE.md:30-38`; `LICENSING_EXCEPTION_REGISTER.md:11`). | MIT/Apache-2.0/MPL fine **only while no AGPL server code is copied**. If AGPL community code were combined, NOVARA would need AGPL-compatible terms and §13 source offer. EE remains excluded. MIT SDK reuse would need its per-package notice. |
| 2 | Meilisearch | Core **MIT + OpenLDAP** (`heed`/LMDB connector); `enterprise_editions` **BUSL-1.1** (non-production only; commercial licence for production). | Local SQL search; no Meilisearch engine, SDK or EE code vendored (`LICENSE_COMPLIANCE.md:40-48`; `dependency_boundary.py` records "no-meilisearch-sdk-dependency"). | Compatible with every candidate. Keep OpenLDAP notice if the connector is ever copied. BUSL EE must stay excluded unless separately licensed. |
| 3 | GrowthBook | Community **MIT**; `packages/*/enterprise` GrowthBook Enterprise License (seat-based, no redistribution). | Clean-room flags/experiments; no GrowthBook source, SDK or EE path (`LICENSE_COMPLIANCE.md:50-58`). | Compatible with every candidate. EE stays excluded. MIT notice required if SDK/API code is later reused. |
| 4 | Papermark | Community **AGPL-3.0**; `ee/` and `app/(ee)/` Papermark Commercial License. | Clean-room documents/share links/view events; no Papermark source or EE (`LICENSE_COMPLIANCE.md:60-68`). | Same as Formbricks: permissive NOVARA licence is safe only while no AGPL code is copied. AGPL path would trigger §13. Commercial EE excluded. |
| 5 | Plane | **AGPL-3.0-only across the reviewed repository**; no enterprise split found. | Clean-room projects/tasks/kanban; public-API interoperability only; no Plane source (`LICENSE_COMPLIANCE.md:70-78`). | Highest copyleft risk of the ten. A permissive NOVARA licence is viable only because no Plane code is copied. Any copy would require combined work to satisfy AGPL-3.0-only. |
| 6 | Mautic | **GPL-3.0**; third-party components in `LICENSE.txt`; "Mautic" is a trademark of the Mautic project. | Clean-room campaign/metrics/consent APIs; no Mautic source or hosted dependency (`LICENSE_COMPLIANCE.md:80-88`). | GPL-3.0 derivative works must be GPL-3.0-compliant; no AGPL network clause, but combining with AGPL material would impose both sets of terms. Trademark is **not** licensed by GPL. Do not copy source. |
| 7 | Chatwoot | Community **MIT**; `enterprise/` Chatwoot Enterprise License. | Clean-room support/tickets/conversations; no Chatwoot source or EE (`LICENSE_COMPLIANCE.md:90-98`). | Compatible with every candidate. EE excluded; MIT notice required if MIT core code is reused. |
| 8 | Novu | Community **MIT**; `enterprise/packages` Novu Proprietary Software License (internal use only; no modification/redistribution without approval). | Clean-room notification jobs/adapters; local mocks never claim delivery; no proprietary package (`LICENSE_COMPLIANCE.md:100-108`). | Compatible with every candidate for community paths. Proprietary packages absolutely excluded; no "verified delivery" claim without authorisation. |
| 9 | Marketing Skills | **MIT** (`Copyright (c) 2025 Corey Haines`), single licence; pinned commit `5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1`, plugin 2.14.25. | **Actually vendored:** 53 skills / 400 manifest-listed files (~4.2 MB) under `apps/api/novara_core/skills/vendor/marketingskills/2.14.25/`; served as inert reference content by `modules/marketing_skills.py`; not executed. | Compatible with every candidate, including permissive licences. MIT notice, frontmatter, partner/sponsor disclosures and pin provenance must survive redistribution. This is the **one** inspiration where third-party bytes are in the repository today. |
| 10 | Sellbird | **Version split:** v0.4.0+ **AGPL-3.0-only**; ≤0.3.x ("Harvey") MIT; `NOTICE` preserves MIT text. | Clean-room approval-gate/outreach-safety patterns; no AGPL code; no ≤0.3.x code identified as copied (`LICENSE_COMPLIANCE.md:120-128`). | Permissive NOVARA licence safe only while no AGPL code is copied. If MIT ≤0.3.x material is ever referenced, preserve its MIT notice. Current AGPL versions excluded from copying. |

**Cross-cutting finding:** the ten projects are inspirations, not a licence pool. Five have MIT family paths (Formbricks SDK subset, Meilisearch core, GrowthBook, Chatwoot, Novu, Sellbird ≤0.3.x, Marketing Skills), but Formbricks, Papermark, Plane, Mautic and Sellbird v0.4.0+ carry copyleft cores, and six have EE/proprietary/commercial splits. The existing clean-room boundary (`LICENSING_EXCEPTION_REGISTER.md:7-20`, 0 `LICENSING_RESTRICTED` rows) is the control that keeps these terms out of NOVARA. It must be preserved.

---

## 5. Required attribution

### 5.1 Already catalogued

`THIRD_PARTY_NOTICES.md:7-108` records the required notices and source URLs for:

- MIT components: Meilisearch core (plus OpenLDAP text for `heed`/LMDB), GrowthBook community, Chatwoot community, Novu community, Marketing Skills, Formbricks SDK packages (per-package notices), Sellbird ≤0.3.x ("Harvey").
- Copyleft components: Formbricks community (AGPLv3), Papermark community (AGPLv3), Plane (AGPL-3.0-only), Sellbird v0.4.0+ (AGPL-3.0-only), Mautic (GPL-3.0 plus third-party component notices in its `LICENSE.txt`).
- Excluded non-open paths: Formbricks EE, Meilisearch EE (BUSL-1.1), GrowthBook Enterprise, Papermark Commercial, Chatwoot Enterprise, Novu proprietary (`THIRD_PARTY_NOTICES.md:110-119`).

These notices must be preserved on any redistribution. MIT/BSD/Apache notices require the copyright notice, permission notice and "AS IS" disclaimer in all copies or substantial portions. AGPL/GPL notices require the full licence text and copyright notice.

### 5.2 Actually vendored content

- The vendored Marketing Skills bundle contains the unmodified upstream MIT `LICENSE` at `apps/api/novara_core/skills/vendor/marketingskills/2.14.25/LICENSE` and a repository-level notice at `THIRD_PARTY_NOTICES.md:54-64`.
- `MANIFEST.json` records the pinned SHA, SPDX MIT, 53 skills and 400 files; its SHA-256 is `50592552106d00ae88e81dab91fe63173f272f0387d30d89602b81536e3293c4`, matching the anchor in `modules/marketing_skills.py:37`.
- YAML frontmatter, Unicode punctuation, quotation marks and partner/sponsor disclosures (including the Converly partner rows in `skills/conversion-tracking/references/server-side.md`) are preserved verbatim. They are upstream disclosures, **not** NOVARA endorsements.
- The bundle contains upstream `.py`, `.mjs`, `.html`, `.csv`, `.md` and `.json` files. They are inert reference text and are not executed, but they are redistributed bytes.

### 5.3 Stale statements requiring owner-approved correction (not changed by this review)

The following statements conflict with the vendored bundle as it exists now:

| Location | Stale claim | Observed fact |
|---|---|---|
| `THIRD_PARTY_NOTICES.md:3` | "No third-party code has been copied or redistributed into NOVARA." | 400 MIT-licensed upstream files are vendored and copied into the Docker image (`Dockerfile:15` copies `novara_core`). |
| `README.md:355-356` | "No source code was copied or redistributed from the ten reference projects." | Marketing Skills is one of the ten; its content is vendored. |
| `README.md:534` | "no codebase from those projects was redistributed into NOVARA." | Same; at minimum needs qualification ("no AGPL/GPL/EE source"; "MIT Marketing Skills reference content is vendored with notice"). |
| `site/index.html:216` | "No source was copied or redistributed from these projects." | Same; public site claim needs correction. |
| `apps/api/novara_core/skills/vendor/marketingskills/2.14.25/PROVENANCE.md` | 7 skills, 44 upstream blobs, 557,839 bytes, manifest SHA `8da603bb…` | 53 skills, 400 manifest-listed files, ~4.2 MB, manifest SHA `50592552…`. |
| `docs/FEATURE_PARITY/SOURCES/09-marketingskills.md:3,7` | "No marketing-skills runtime module or vendored skill content is bundled"; "No source code or skill content has been copied into NOVARA" | 53 skills/vendored content exist; `modules/marketing_skills.py` serves them through a permissioned API (it does not execute them). |
| `docs/FINAL_RELEASE_QA/TEN_SOURCE_PROJECT_COMPLETION_REPORT.md:128,151` | "no runtime module bundled; MIT-derived playbooks documented with attribution" | A read-only serving/loader module exists for a vendored bundle; adjust wording to "no skill execution/eval runtime". |

**Required action:** correct these statements to an accurate formulation before external release; do not delete the MIT notices or provenance files while doing so.

### 5.4 Trademarks

Software licences do **not** grant trademark rights. No Formbricks, Meilisearch, GrowthBook, Papermark, Plane, Mautic, Chatwoot, Novu or Sellbird marks may be used in NOVARA branding, and no affiliation/endorsement may be implied. `README.md:531-534` already disclaims affiliation. Partner markers inside vendored content must remain as upstream disclosures, not NOVARA endorsements.

---

## 6. Copyleft and distribution obligations

| Licence family | Obligation if code/content is redistributed | Current NOVARA applicability |
|---|---|---|
| MIT / BSD / PSF | Include copyright notice, permission notice and warranty disclaimer in copies or substantial portions. No source-disclosure duty. | Runtime/dev dependencies and vendored Marketing Skills. Applies to source archives and container images. |
| Apache-2.0 | Include licence copy; preserve any upstream `NOTICE` file; patent grant and patent-retaliation terms apply; state changes if required by upstream NOTICE. | `bcrypt`, `python-multipart`, `opentelemetry-api`; `packaging` is dual `Apache-2.0 OR BSD-2-Clause`. Confirm which branch is chosen in the SBOM. |
| MPL-2.0 | File-level copyleft: modified MPL-covered files must remain MPL and source must be available; the larger work may use another licence. Preserve licence notices. | `certifi` (observed locally). Verify it is unmodified; include its licence text in distributions. |
| LGPL-3.0-only | Recipients must be able to modify/relink the library; licence and source/offer obligations apply to the library. | `psycopg` declared via the `postgres` extra and installed by the Dockerfile; not present in the local `.venv`. Needs specific review before image distribution. |
| AGPL-3.0 / AGPL-3.0-only | Full licence text, copyright notice, prominent modification notices, Corresponding Source for copies/derivatives, and **§13 source offer to remote network users** of modified versions served over a network. No additional restrictions. | Formbricks community, Papermark community, Plane, Sellbird v0.4.0+. Avoided today by clean-room design. Using them merely as separate unmodified network services is fact-specific and needs legal review before any integration (`LICENSE_COMPLIANCE.md:137`). |
| GPL-3.0 | Derivative works must be GPL-3.0-compliant; licence text/notices; no AGPL-style network clause. | Mautic. Avoided today by API/clean-room approach. Trademark separate. |
| BUSL-1.1 / EE / Commercial / Proprietary | No production use, copying, modification or redistribution without the relevant commercial licence/approval. | Formbricks EE, Meilisearch EE, GrowthBook EE, Papermark Commercial, Chatwoot EE, Novu proprietary, Sellbird AGPL. Excluded; no credential or paid tier is a dependency. |

### 6.1 Container and packaging distribution

- `Dockerfile:14-21` copies `pyproject.toml`, the whole `apps/api/novara_core` tree (including `skills/vendor/marketingskills/2.14.25`), Alembic config/migrations and `apps/web`, then runs `pip install '.[postgres,migrate]'`. Therefore the image redistributes the MIT bundle and installed third-party packages.
- `THIRD_PARTY_NOTICES.md` is **not** copied into the image by the Dockerfile. If the image is published, notices must accompany it (for example, copy the notices and the vendored `LICENSE` into the image or ship an image licence manifest/SBOM).
- `docker-compose.yml:17-31` uses `postgres:16-alpine` under the `postgres` profile. That base image carries PostgreSQL/Alpine/musl/BusyBox component licences separate from NOVARA's. `python:3.12-slim` likewise carries PSF/Debian component terms. Review if images are distributed.
- `pip install --upgrade pip` and unpinned `pyproject.toml` mean the final image dependency set is resolved at build time; see §7.

---

## 7. Dependencies needing further review

The following are **not** licence violations today; they are unresolved compliance work before a public binary/image release. Local versions below are observed in `D:\NOVARA\.venv\Lib\site-packages` on 2026-11-25 and are **not** authoritative for the Docker build.

| Area | Evidence | Licence / status | Review required |
|---|---|---|---|
| Dependency pinning / SBOM | `apps/api/pyproject.toml:6-19` uses only lower bounds (`>=`); `Dockerfile:18-19` resolves fresh with no lockfile/constraints. No JS manifests exist in the repo. | Process gap. | Produce a pinned lockfile/constraints file and generate an SBOM from the **built image**, then attach notices to distributions. Highest priority. |
| `psycopg[binary]>=3.1` | `pyproject.toml:18`; installed by `Dockerfile:19`. Not installed in local `.venv`. | `psycopg` metadata on PyPI (read 2026-11-25) reports `LGPL-3.0-only`; `binary` extra adds `psycopg-binary`/`psycopg-c` and bundled `libpq` components. | Review exact resolved version and binary-component notices; confirm relinking/source obligations and include notices if the image is distributed. |
| `certifi` 2026.11.20 | Local `.venv` metadata `License-Expression: MPL-2.0`. | MPL-2.0 file-level copyleft. | Confirm unmodified; include MPL text; record in SBOM. |
| Apache-2.0 group | `bcrypt` 5.0.0, `python-multipart` 0.0.34, `opentelemetry-api` 1.45.2, `packaging` 26.3 (`Apache-2.0 OR BSD-2-Clause`). | Apache-2.0 / dual. | Preserve NOTICE files and dual-licence choice; determine why `opentelemetry-api` is present (transitive/plugin) and whether it belongs in the shipped image. |
| PSF / base images | `typing_extensions` 4.16.0 = `PSF-2.0`; `python:3.12-slim` base (`Dockerfile:6`). | PSF-2.0 + Debian component licences. | Include in image notice/SBOM; verify no additional restrictions from base-image components. |
| BSD/MIT runtime set | `fastapi`, `starlette`, `uvicorn`, `h11`, `httpcore`, `httpx`, `idna`, `click`, `markupsafe`, `sqlalchemy`, `pydantic`, `pydantic_core`, `pypdf`, `alembic`, `mako`, `anyio`, `pluggy`, `iniconfig`, `pytest`, `pip`, `setuptools`, `pygments`, `typing_inspection`. | MIT / BSD-2 / BSD-3 / PSF as recorded in `.dist-info`. | Notice retention in binary/image distributions; low substantive risk but must be enumerated in SBOM. |
| Container image from `postgres:16-alpine` | `docker-compose.yml:17-31`. | PostgreSQL License + Alpine/musl/BusyBox etc. | Review only if the compose stack/image is distributed or supported as part of a release; currently opt-in profile. |
| GitHub Actions | `.github/workflows/pages.yml` uses `actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4`. | Third-party hosted actions; no repository attribution obligation established. | Optional supply-chain review (SHA pinning); not a licence blocker. |
| Frontend assets | `apps/web` and `site/` contain local HTML/CSS/JS/images/video; no CDN `<script src>`/`<link>` to third-party JS/CSS found; no `package.json`. | No current JS dependency licences to inherit. | Re-run this review if a JS package manager or CDN asset is introduced. |

---

## 8. Can NOVARA honestly be described as open source right now?

**No.**

- There is no licence file or licence grant. Under default copyright, recipients have permission to view the repository, not to copy, modify, redistribute or sublicense it. That is "source available", not "open source".
- The repository's own wording is appropriately cautious: `README.md:362` and `site/index.html:318,416` use the exact pending-licence phrase; `README.md:364` says "Do not describe NOVARA as an openly licensed release." `LICENSING_CLAIMS_AUDIT.md:72-74` confirms no `fully open source`/banned claims were found.
- `docs/VISION.md:44-46` expresses an *intent* to be genuinely free and open source; intent is not a licence.
- The live marketing site (`https://ganeshkrishnareddy.github.io/novara/`) is a publication of a page, not a grant of rights over the codebase.
- Keep B-04 open until the owner signs off a licence and it is committed. Do not upgrade the public wording to "open source", "fully open source" or "openly licensed release" before then.

---

## 9. Recommended licence options and trade-offs

This is a decision menu, **not** a selection. All options assume the existing clean-room boundary is retained; none authorises copying AGPL/GPL/EE code.

| Option | Fit with current codebase | Obligations created | Trade-offs / risks |
|---|---|---|---|
| **MIT** (reviewer default) | Best fit. Clean-room core, MIT/BSD/Apache deps, MIT Marketing Skills bundle. OSI-approved and matches `VISION.md` intent. | Preserve notices only. | Very permissive: allows proprietary forks and hosted clones with no copyleft reciprocity and weak explicit patent protection. If owner wants patent peace or copyleft reciprocity, choose another option. |
| **Apache-2.0** | Also a strong fit. Compatible with current dependency set and vendored MIT content. | MIT-style notice retention **plus** `NOTICE` file handling, licence copy, patent grant/patent retaliation, state-changes requirement where applicable. | More administrative overhead than MIT; explicit patent grant is a benefit. Compatible with GPLv3 (not GPLv2-only) if copyleft code were ever added, but still requires that separate review. |
| **MPL-2.0** | Workable. Permissive for the larger work, file-level copyleft only for MPL files. | Modified MPL-covered files must stay MPL with source available; per-file headers/notices; more care in a mixed Python package. | Middle ground: protects NOVARA files from proprietary capture without forcing the whole work. More complexity and less familiar to contributors than MIT. |
| **GPL-3.0-only** | Would only be coherent if the owner intends NOVARA to be strongly copyleft and accepts Mautic-style terms. | Whole combined derivative work GPL-3.0; source offer on distribution; notices/modification markers; trademark still separate. | Forces copyleft on all downstream derivatives; complicates any commercial/proprietary strategy; still does not authorise copying AGPL sources without联合 compliance. Higher legal-review burden. |
| **AGPL-3.0-only** | Strongest "no proprietary hosted capture" posture; aligns with Formbricks/Papermark/Plane/Sellbird community cores if ever combined. | All of GPL plus §13 Corresponding Source offer to remote users of modified versions served over a network; applies to hosted NOVARA instances. | Highest obligation. Would require re-auditing AGPL/GPL combination, Docker/source offers, and contributor/licence choices. Conflicts with any plan to keep hosted modifications private. |
| **BUSL / Commons Clause / other source-available** | Technically permissible for NOVARA's own code if notices to others are preserved, but **contradicts** `VISION.md:44-46` and current README/site wording. | Custom restrictions; must not purge third-party MIT/Apache/MPL notices. | Not OSI "open source"; would require rewriting README §21/FAQ, site FAQ and VISION language, and would change contributor expectations. Not recommended without an explicit owner product-strategy change. |
| **Dual-licence (e.g. AGPL + commercial)** | Possible later, but requires a deliberate commercial strategy and authority to license contributions. | Two notice stacks; contributor licensing/CLA decisions. | More legal work; premature for this gate. |

**Reviewer note:** MIT is the lowest-friction choice that makes the existing clean-room architecture, vendored MIT MIT-licensed content and dependency set coherent. Apache-2.0 is the alternative if the owner values an explicit patent grant. Neither choice permits copying AGPL/GPL/EE source.

---

## 10. Clear owner action

**Decision required from the owner (Task RGC-C):**

1. **Choose NOVARA's licence** by selecting one option from §9, or explicitly decide to keep B-04 open. My recommendation is **MIT** (alternative: Apache-2.0 if patent grant is prioritised). I have not chosen or applied a licence.
2. **Authorise a separate implementation task** (not this agent) to:
   - add the chosen root `LICENSE` file and set licence metadata in `apps/api/pyproject.toml`;
   - correct the stale "no source copied" statements listed in §5.3, keeping all MIT notices and provenance intact;
   - update `PROVENANCE.md` to the actual 53-skill/400-file bundle and the actual manifest SHA;
   - add third-party notices to the Docker image/distribution and produce a pinned lockfile + SBOM from the built image, with specific review of `psycopg[binary]` and `certifi`;
   - re-check README §21/§27, `site/index.html` and FAQ wording so the licence claim matches the committed file.
3. **Maintain the clean-room boundary.** Confirm that no AGPL/GPL/EE/proprietary source will be copied and that no EE credential or paid tier becomes a dependency. Obtain legal review before treating any AGPL/GPL upstream as a separate network service.
4. **External messaging until step 2 completes:** continue to use exactly `open-source foundation subject to final repository licensing review; licence file pending owner decision.` Do not publish "fully open source", "openly licensed release" or any claim of third-party endorsement.
5. **Gate closure criterion:** B-04 may be marked closed only after the owner's written licence choice and the committed licence/notices/SBOM corrections are verifiable. Until then, **LOCAL RELEASE ACCEPTED: NO** remains the governing verdict.

---

## 11. Limitations and preservation statement

- This is an evidence-based compliance review, **not a legal opinion**. Upstream terms are taken from the licence URLs and texts recorded in `docs/research/LICENSE_COMPLIANCE.md` and `THIRD_PARTY_NOTICES.md` as reviewed on 2026-11-22, plus the local metadata described above.
- Licence texts of upstream repositories were not re-fetched in full during this review; the existing audited findings were used. The one external metadata read was PyPI's `psycopg` JSON for its `license_expression`.
- No dependency was installed, upgraded or removed; no build, test, commit, push, deploy or external send was performed.
- Only this file was created. All pre-existing modified and untracked files in `D:\NOVARA\` were left untouched.
