# License compliance — resolved terms (T-007)

Verified against the actual `LICENSE` / `LICENSE.md` / `NOTICE` / enterprise-license files fetched from each repository on 2026-11-22. **No source code has been copied or redistributed.** This document remains a gate: no large-scale code integration may begin until the decisions below are accepted.

Source of truth for intent: `docs/VISION.md` (NOVARA is to be genuinely free and open source, one product not ten, no blind copy-paste).

## Rule adopted

- Prefer modular adapters, public APIs/SDKs, independently licensed packages and clean-room implementations over copying source.
- Enterprise/EE/Commercial/Proprietary modules are **excluded** from NOVARA. Only community-licensed code paths may ever be considered, and only under the terms below.
- Every finding below cites the exact license file URL it was read from.

## Summary decision table

| # | Repository (default branch) | Actual community license | Enterprise split | Network/redistribution restriction | Source copy permitted? | Decision |
|---|---|---|---|---|---|---|
| 1 | formbricks/formbricks (main) | AGPL-3.0 (community) | `apps/web/modules/ee` under Formbricks EE (commercial, seat-based, no redistribution) | AGPL network copyleft: modified versions served over a network must offer Corresponding Source | Community: only under AGPL terms; EE: no | Reuse via public API/SDK (MIT SDK packages) + clean-room for server features |
| 2 | meilisearch/meilisearch (main) | MIT + OpenLDAP (core); BUSL-1.1 for `enterprise_editions` | `enterprise_editions` under BUSL-1.1 (non-production only; production needs commercial license; converts to MIT after 4 years) | MIT core: none; BUSL: no production use without commercial license | Core: yes (MIT); EE: no | Reuse via public API/SDK (MIT core) |
| 3 | growthbook/growthbook (main) | MIT (community) | `packages/*/enterprise` under GrowthBook Enterprise License (commercial, seat-based, no redistribution) | MIT community: none | Community: yes (MIT); EE: no | Reuse via public API/SDK (MIT) |
| 4 | papermark/papermark (main) | AGPL-3.0 (community) | `ee/` under Papermark Commercial License (commercial subscription, no redistribution) | AGPL network copyleft | Community: only under AGPL terms; EE: no | Clean-room implement (document sharing/viewer tracking); exclude EE |
| 5 | makeplane/plane (preview) | AGPL-3.0-only | None found (whole repo AGPL-3.0-only) | AGPL network copyleft | Only under AGPL terms | Clean-room implement (projects/tasks/kanban) |
| 6 | mautic/mautic (7.x) | GPL-3.0 (community) | None found (GPL-3.0; Mautic trademark noted) | GPL copyleft (no network clause, but derivative works must be GPL-3.0) | Only under GPL-3.0 terms | Integrate via public API/SDK; do not copy source |
| 7 | chatwoot/chatwoot (develop) | MIT (community) | `enterprise/` under Chatwoot Enterprise License (commercial, seat-based, no redistribution) | MIT community: none | Community: yes (MIT); EE: no | Reuse via public API/SDK (MIT core) |
| 8 | novuhq/novu (next) | MIT (community) | `enterprise/packages` under Novu Proprietary Software License (no modification, no redistribution, prior written approval) | MIT community: none; proprietary: internal use only | Community: yes (MIT); proprietary: no | Reuse via public API/SDK (MIT core); exclude proprietary packages |
| 9 | coreyhaines31/marketingskills (main) | MIT | None (single license) | MIT: none (attribution required) | Yes (MIT) | Reuse content with attribution (MIT) |
| 10 | ethanplusai/sellbird (main) | AGPL-3.0-only (v0.4.0+) ; versions ≤0.3.x MIT | None found (version split instead of directory split) | AGPL network copyleft for v0.4.0+; older MIT code stays MIT | v0.4.0+: only under AGPL terms; ≤0.3.x: yes (MIT) | Clean-room implement (lead research/prospecting); exclude AGPL code |

## Per-repository findings

### 1. formbricks/formbricks — https://github.com/formbricks/formbricks

- License file: `LICENSE` at `https://github.com/formbricks/formbricks/blob/main/LICENSE`
- Actual terms: "Portions of this software are licensed as follows": `apps/web/modules/ee` under Formbricks EE license; `packages/js`, `packages/android`, `packages/ios`, `packages/api`, `packages/surveys`, `packages/survey-ui` under MIT (per their `package.json`); third-party components under original licenses; everything else under AGPLv3.
- Community vs enterprise split: community core is AGPLv3; enterprise features (`apps/web/modules/ee`) under Formbricks EE (commercial, valid seat license required for production, no copy/merge/publish/distribute/sublicense/sell; dev/test copying allowed).
- Attribution/notice: AGPLv3 copyright notice `Copyright (c) 2024 Formbricks GmbH` and full AGPLv3 text must be preserved for community code; MIT SDK packages require their own copyright notice and permission notice.
- Redistribution/network: AGPLv3 §13 requires offering Corresponding Source to remote network users of any modified version. Combining AGPL code into NOVARA and serving it over a network would obligate NOVARA to release the combined source under AGPLv3.
- Source copy permitted? Community code only under AGPLv3 terms; EE code not permitted.
- Decision: **Reuse via public API/SDK** for the MIT-licensed SDK packages (`@formbricks/js` and platform SDKs) with attribution; **clean-room implement** survey/NPS/CSAT capability in NOVARA rather than copying AGPL server code; exclude EE.

### 2. meilisearch/meilisearch — https://github.com/meilisearch/meilisearch

- License files: `LICENSE` (`https://github.com/meilisearch/meilisearch/blob/main/LICENSE`), `LICENSE-EE` (`.../blob/main/LICENSE-EE`), `LICENSE-MIT` (`.../blob/main/LICENSE-MIT`), `LICENSE-OPENLDAP` (`.../blob/main/LICENSE-OPENLDAP`).
- Actual terms: core under MIT + OpenLDAP (heed/LMDB connector); `enterprise_editions` under BUSL-1.1 (Meili SAS). SPDX: `MIT AND OpenLDAP AND BUSL-1.1`.
- Community vs enterprise split: core engine is MIT (plus OpenLDAP for the LMDB connector); enterprise features under BUSL-1.1 — non-production use only (testing/development/evaluation); production use requires a commercial license; converts to MIT on the Change Date (four years from publication).
- Attribution/notice: MIT notice `Copyright (c) 2019-2025 Meili SAS` must be preserved; OpenLDAP license text must be preserved for the LMDB connector; BUSL text must be displayed on copies of the Licensed Work.
- Redistribution/network: MIT core has no copyleft. BUSL prohibits production use without a commercial license and prohibits violating the license.
- Source copy permitted? Core: yes (MIT, with attribution). EE: no production use without commercial license; do not copy into NOVARA.
- Decision: **Reuse via public API/SDK** — integrate Meilisearch as a service/client using the MIT-licensed core and its client SDKs; exclude `enterprise_editions`.

### 3. growthbook/growthbook — https://github.com/growthbook/growthbook

- License file: `LICENSE` at `https://github.com/growthbook/growthbook/blob/main/LICENSE`; enterprise license at `packages/back-end/src/enterprise/LICENSE` (and front-end/shared equivalents).
- Actual terms: community code under MIT Expat; `packages/back-end/src/enterprise`, `packages/front-end/enterprise`, `packages/shared/src/enterprise` under GrowthBook Enterprise License.
- Community vs enterprise split: community core is MIT; enterprise features require a valid GrowthBook Enterprise/Pro license and seat count; no copy/merge/publish/distribute/sublicense/sell; dev/test copying allowed.
- Attribution/notice: MIT notice `Copyright (c) 2025 GrowthBook, Inc.` must be preserved.
- Redistribution/network: MIT community has no copyleft.
- Source copy permitted? Community: yes (MIT). EE: no.
- Decision: **Reuse via public API/SDK** — feature flags/experiments/analytics via GrowthBook SDKs (MIT) with attribution; exclude enterprise.

### 4. papermark/papermark — https://github.com/papermark/papermark

- License files: `LICENSE` (`https://github.com/papermark/papermark/blob/main/LICENSE`); `ee/LICENSE.md` (`https://github.com/papermark/papermark/blob/main/ee/LICENSE.md`).
- Actual terms: community code under AGPLv3; `ee/` (and `app/(ee)`) under Papermark Commercial License.
- Community vs enterprise split: community core is AGPLv3; enterprise (`ee/`) requires a valid Commercial Subscription and mutual agreement; no copy/merge/publish/distribute/sublicense/sell; dev/test copying allowed.
- Attribution/notice: AGPLv3 copyright `Copyright (c) 2023-present Papermark, Inc.` and full AGPLv3 text must be preserved; Commercial License text for EE.
- Redistribution/network: AGPLv3 §13 network source offer for modified versions served over a network.
- Source copy permitted? Community: only under AGPLv3 terms; EE: no.
- Decision: **Clean-room implement** secure document sharing/viewer tracking/permissions/data rooms in NOVARA; do not copy AGPL or Commercial code; exclude EE.

### 5. makeplane/plane — https://github.com/makeplane/plane

- License file: `LICENSE.txt` at `https://github.com/makeplane/plane/blob/preview/LICENSE.txt`; `COPYRIGHT.txt` at `https://github.com/makeplane/plane/blob/preview/COPYRIGHT.txt`.
- Actual terms: AGPL-3.0-only. COPYRIGHT.txt: `Copyright (c) 2023-present Plane Software, Inc. and contributors` / `SPDX-License-Identifier: AGPL-3.0-only`.
- Community vs enterprise split: none found in the reviewed tree; entire reviewed codebase is AGPL-3.0-only.
- Attribution/notice: copyright notice and full AGPLv3 text must be preserved; modified versions must carry prominent modification notices and Appropriate Legal Notices.
- Redistribution/network: AGPLv3 §13 requires offering Corresponding Source to remote users of modified versions.
- Source copy permitted? Only under AGPL-3.0-only terms; combined work must be AGPL-3.0-only.
- Decision: **Clean-room implement** projects/tasks/issues/kanban/cycles/milestones in NOVARA to keep NOVARA's license flexible; do not copy Plane source.

### 6. mautic/mautic — https://github.com/mautic/mautic

- License file: `LICENSE.txt` at `https://github.com/mautic/mautic/blob/7.x/LICENSE.txt`.
- Actual terms: GPL-3.0. Header: "Mautic is released under the GPL v3." Includes third-party components listed (Carbon pictograms Apache-2.0, Bootstrap MIT, etc.).
- Community vs enterprise split: none found; GPL-3.0 throughout; "Mautic is a trademark of the Mautic project of the Open Source Collective."
- Attribution/notice: copyright `Copyright 2014 by the contributors` and GPL-3.0 text; third-party notices as listed in LICENSE.txt.
- Redistribution/network: GPL-3.0 copyleft — derivative works must be GPL-3.0; no network source clause (unlike AGPL), but combining into NOVARA would force GPL-3.0 on the combined work.
- Source copy permitted? Only under GPL-3.0 terms.
- Decision: **Integrate via public API/SDK** for segmentation/email marketing/campaigns/landing pages/journeys; do not copy Mautic source into NOVARA. (Mautic exposes a REST API.)

### 7. chatwoot/chatwoot — https://github.com/chatwoot/chatwoot

- License files: `LICENSE` (`https://github.com/chatwoot/chatwoot/blob/develop/LICENSE`); `enterprise/LICENSE` (`.../blob/develop/enterprise/LICENSE`).
- Actual terms: community code under MIT Expat; `enterprise/` under Chatwoot Enterprise License.
- Community vs enterprise split: community core is MIT; enterprise requires a valid Chatwoot Enterprise license and seat count; no copy/merge/publish/distribute/sublicense/sell; dev/test copying allowed.
- Attribution/notice: MIT notice `Copyright (c) 2017-2026 Chatwoot Inc.` must be preserved.
- Redistribution/network: MIT community has no copyleft.
- Source copy permitted? Community: yes (MIT). EE: no.
- Decision: **Reuse via public API/SDK** — support/shared inbox/omnichannel via Chatwoot's MIT core and API; optionally reuse MIT-licensed components with attribution; exclude enterprise.

### 8. novuhq/novu — https://github.com/novuhq/novu

- License files: `LICENSE-MIT` (`https://github.com/novuhq/novu/blob/next/LICENSE-MIT`); `LICENSE-ENTERPRISE` (`.../blob/next/LICENSE-ENTERPRISE`); `EE-PACKAGES-LICENSE` (`.../blob/next/EE-PACKAGES-LICENSE`).
- Actual terms: community code under MIT (copyright `Copyright (c) 2019 Noti-fire Apps Ltd.`); `enterprise/packages` under Novu Proprietary Software License (internal use only, prior written approval required, no modification, no redistribution, no reverse engineering).
- Community vs enterprise split: community core is MIT; enterprise packages are proprietary and require prior written approval from Novu.
- Attribution/notice: MIT notice must be preserved for community code.
- Redistribution/network: MIT community has no copyleft; proprietary code must not be redistributed.
- Source copy permitted? Community: yes (MIT). Proprietary: no.
- Decision: **Reuse via public API/SDK** — notification workflows (email/push/SMS/in-app) via Novu's MIT core and SDKs; exclude `enterprise/packages`.

### 9. coreyhaines31/marketingskills — https://github.com/coreyhaines31/marketingskills

- License file: `LICENSE` at `https://github.com/coreyhaines31/marketingskills/blob/main/LICENSE`.
- Actual terms: MIT. `Copyright (c) 2025 Corey Haines`.
- Community vs enterprise split: none (single MIT license; it is a skills/prompt library, not a runtime system).
- Attribution/notice: copyright notice and permission notice must be included in all copies or substantial portions.
- Redistribution/network: MIT — no copyleft.
- Source copy permitted? Yes (MIT), with attribution.
- Decision: **Reuse content with attribution (MIT)** — use as inspiration/templates for NOVARA's marketing intelligence (SEO, copywriting, CRO, competitor research) with the copyright notice preserved; independent implementation of runtime logic preferred per VISION.md.

### 10. ethanplusai/sellbird — https://github.com/ethanplusai/sellbird

- License files: `LICENSE` (`https://github.com/ethanplusai/sellbird/blob/main/LICENSE`); `NOTICE` (`https://github.com/ethanplusai/sellbird/blob/main/NOTICE`).
- Actual terms: v0.4.0+ is AGPL-3.0-only (`Copyright (C) 2026 Ethan Rogers and the Sellbird contributors`). Versions ≤0.3.x were released as "Harvey" under MIT (`Copyright (c) 2026 Ethan Rogers`), and that earlier code remains MIT; the NOTICE file preserves the MIT notice.
- Community vs enterprise split: version-based, not directory-based. Current (v0.4.0+) code is AGPL-3.0-only; older releases remain MIT.
- Attribution/notice: AGPL-3.0 copyright and full license text for v0.4.0+; MIT notice for ≤0.3.x code must be preserved (per NOTICE).
- Redistribution/network: AGPL-3.0-only §13 network source offer for modified versions served over a network.
- Source copy permitted? v0.4.0+: only under AGPL-3.0-only terms. ≤0.3.x: yes (MIT), with attribution.
- Decision: **Clean-room implement** lead research/prospecting/enrichment/outreach/AI sales in NOVARA; do not copy v0.4.0+ AGPL code. May reference ≤0.3.x MIT code with attribution, but clean-room implementation preferred.

## NOVARA's own license

No `LICENSE` file exists for NOVARA yet, and choosing one is a human/owner decision (especially given AGPL-3.0-only/GPL-3.0 interaction). This document does not create one. Work that does not depend on it (research, architecture, contracts, independent implementation) continues.

## Unresolved / owner-required items

1. Final choice of NOVARA's own license (owner decision) — blocks any redistribution of combined code.
2. Legal review of whether NOVARA may depend on AGPL-3.0 components as separate network services (formbricks, papermark, plane, sellbird) without contaminating NOVARA's license — recommended before any such integration.
3. Confirmation that no enterprise/EE/Commercial/Proprietary code paths are included in any NOVARA build (CI check recommended).
4. Verification of any additional third-party notices inside dependencies (npm/pip/composer) — separate SBOM task, not covered here.