# Provenance — vendored Marketing Skills (P1)

This directory is a verbatim, pinned vendoring of seven content skills from
`coreyhaines31/marketingskills`. It is reference content only: NOVARA does not
execute any `SKILL.md`, run any upstream eval, invoke any upstream script, or
send any model request on the strength of these files.

## Pin

- Upstream repository: <https://github.com/coreyhaines31/marketingskills>
- Pinned commit: `5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1`
- Plugin version at that commit: `2.14.25`
- Fetched on: 2026-11-23
- License: MIT (`SPDX-License-Identifier: MIT`), `Copyright (c) 2025 Corey Haines`
- Raw fetch pattern used:
  `https://raw.githubusercontent.com/coreyhaines31/marketingskills/5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1/<path>`
- Path enumeration: GitHub Git tree API at the same pinned SHA
  (`?recursive=1`, `truncated=false`, 1,098 tree entries).

## What is bundled

Seven skill directories, 44 upstream blobs in total (43 skill files plus the
upstream `LICENSE`), 557,839 bytes of vendored upstream content:

| Feature row | Skill | Upstream files | Skill version from frontmatter |
|---|---|---:|---|
| MK-001 | `ab-testing` | 4 | 2.0.7 |
| MK-005 | `analytics` | 5 | 2.2.7 |
| MK-015 | `conversion-tracking` | 13 | 1.0.6 |
| MK-017 | `copywriting` | 5 | 2.3.6 |
| MK-018 | `cro` | 4 | 2.0.6 |
| MK-039 | `product-marketing` | 3 | 2.2.3 |
| MK-048 | `seo-audit` | 9 | 2.2.9 |

For every skill the upstream `skills/<name>/SKILL.md`, every file under that
skill's `references/` directory, and every file under that skill's `evals/`
directory at the pinned commit are included. The `scripts/` directory is
included **only** for `conversion-tracking`, because that skill owns the two
upstream helper scripts; they were fetched as inert text and never executed.
Eval JSON is bundled as upstream reference content only — upstream evals spend
paid model requests and are not run by NOVARA.

## Integrity

`MANIFEST.json` records the pin, the plugin version, the fetch date, the
upstream URL, the SPDX license, the exact frontmatter `name`, `version` and
`description` of each skill, and a SHA-256 plus byte length for every bundled
file. It also records the Git blob SHA reported by the pinned tree API.

During vendoring each downloaded file was checked by reconstructing its Git
blob object (`blob <byte-length>\0` followed by the file bytes) and comparing
the resulting SHA-1 with the tree entry's blob SHA. All 44 files matched, so
the bytes on disk are byte-for-byte the pinned upstream blobs, including YAML
frontmatter, quotation marks, Unicode punctuation and partner markers.

`MANIFEST.json` itself has SHA-256
`8da603bb7b55cfb4eb0e789c2ee41ecf4a622b5a5175d47446a23748188330d9`; that
value is anchored in `apps/api/novara_core/modules/marketing_skills.py` so a
edited manifest cannot simply rewrite its own file hashes. The NOVARA loader
re-hashes the manifest and every listed file on load and refuses a tampered or
incomplete bundle.

## Attribution and disclosure

- The unmodified upstream MIT license and copyright notice are preserved in
  `LICENSE` inside this directory. The repository-level `THIRD_PARTY_NOTICES.md`
  also carries the required notice; it was not modified by this vendoring work.
- YAML frontmatter is preserved verbatim, including `metadata.version` and all
  descriptions.
- Partner/sponsor disclosure markers are part of the vendored content and were
  not sanitised. In particular, `skills/conversion-tracking/references/server-side.md`
  retains the `Converly ◆` Verified Partner rows and the disclosure paragraph.
  These are upstream disclosures, not NOVARA endorsements.
- No other upstream repository was vendored. In particular, no `sellbird`
  content (AGPL-3.0-only at the relevant versions) is present here.

The licensing decision is recorded in `docs/research/LICENSE_COMPLIANCE.md`
and `docs/research/repos/04-marketingskills-sellbird.md`. This file documents
the mechanical provenance of the pinned copy; it does not re-open that
decision.
