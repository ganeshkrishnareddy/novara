# Licensing and claims audit (independent, read-only)

**Status:** read-only audit. No application code, README, site, or other repository files were modified. No commit, push, deploy or submission performed.
**Auditor:** Shield (Compliance Review Lead, ProgVision Games) on behalf of NOVARA final-release QA.
**Timestamp:** 2026-11-25 11:22 IST (Asia/Calcutta).
**Scope:** licensing phrase, banned marketing/completion claims, and RESTRICTED disposition documentation.

## 1. Method

1. Read (read-only):
   - `docs/research/LICENSE_COMPLIANCE.md`
   - `docs/FEATURE_PARITY/LICENSING_EXCEPTION_REGISTER.md`
   - `THIRD_PARTY_NOTICES.md`
   - `README.md`
   - `site/index.html`
   - `docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv` (for disposition counts)
2. Searched `README.md` and `site/index.html` (case-insensitive) for the required licensing phrase and for banned claim terms.
3. Checked the feature matrix for any `LICENSING_RESTRICTED` disposition and compared with the licensing exception register.
4. Recorded exact evidence lines with file paths and line numbers. No evidence was invented.

## 2. Required licensing phrase verification

Required phrase (exact): `open-source foundation subject to final repository licensing review; licence file pending owner decision.`

Result: PRESENT in both `README.md` and `site/index.html`.

Evidence:
- `README.md:362`: `> open-source foundation subject to final repository licensing review; licence file pending owner decision.`
- `README.md:459`: `an owner decision: open-source foundation subject to final repository licensing review; licence file pending owner decision. See`
- `site/index.html:318`: `<div class="host-callout">...treat NOVARA as an open-source foundation subject to final repository licensing review; licence file pending owner decision.</p></div>`
- `site/index.html:416`: `<details><summary>Is NOVARA open source?</summary><p>...treat NOVARA as an open-source foundation subject to final repository licensing review; licence file pending owner decision.</p></details>`

## 3. Banned claims search

Searched terms (case-insensitive): `fully open source`, `100% complete`, `100 percent complete`, `testimonials`, `download count`, `user count`, `uptime`, `customers`.

Result: No banned claim found in `README.md` or `site/index.html`, except one negative statement that explicitly denies testimonials/counts.

Evidence:
- `README.md:542-543`: `contributors who produced that evidence. No testimonials, user counts, download` / `counts, uptime figures or third-party endorsements are presented.`

This is a denial of fake counts/testimonials, not a claim of them. No instance of `fully open source`, `100% complete`, or fabricated testimonial/count was found.

## 4. RESTRICTED disposition documentation

Feature matrix (`docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv`): 1488 rows total.
- `VERIFIED_COMPLETE`: 1418
- `INTENTIONALLY_REPLACED_WITH_COMPATIBLE_IMPLEMENTATION`: 70
- `LICENSING_RESTRICTED`: 0

`docs/FEATURE_PARITY/LICENSING_EXCEPTION_REGISTER.md` states: "0 `LICENSING_RESTRICTED` features across 0 sources. No source code from an incompatible licence was copied; no enterprise credential, hosted service or paid tier is a NOVARA dependency."

Result: Every row's current status is either verified complete or an intentionally replaced compatible implementation; no row is marked `LICENSING_RESTRICTED`. The licensing exception register records 0 restricted features and documents clean-room alternatives for enterprise/proprietary/paid capabilities via the licensing-constraint column. No RESTRICTED disposition requiring an individual reason/approved alternative was found in the matrix.

## 5. Licensing documentation status

- `docs/research/LICENSE_COMPLIANCE.md`: upstream licence review complete; NOVARA's own licence file does not exist yet (owner decision pending). AGPL/GPL network-copyleft paths excluded from NOVARA combined codebase.
- `THIRD_PARTY_NOTICES.md`: attribution texts recorded; no third-party code copied or redistributed.
- `README.md` section 21 and FAQ: state the exact pending-licence description and prohibit describing NOVARA as an openly licensed release.

## 6. Limitations

- Read-only audit only; no runtime, build, or deployment verification performed.
- Banned-claim search limited to `README.md` and `site/index.html` as requested; other docs/site assets were not searched for marketing claims.
- Counts derived from `MASTER_FEATURE_MATRIX.csv` as of repository state on 2026-11-25; if the matrix changes, counts must be re-verified.
- This audit does not create or choose NOVARA's repository licence; that remains an owner decision.
- No legal opinion is expressed; findings are evidence-based documentation checks only.

## 7. Summary

- Required licensing phrase: present in README (2 occurrences) and site (2 occurrences).
- Banned claims (`fully open source`, `100% complete`, fake counts/testimonials): none found; only an explicit denial of testimonials/counts.
- RESTRICTED dispositions: 0 rows; licensing exception register consistent with 0 restricted features.
- NOVARA's own licence file remains pending owner decision; do not describe NOVARA as an openly licensed release.
