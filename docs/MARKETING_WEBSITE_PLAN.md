# NOVARA marketing website plan

Status: planning document for a **locally prepared** public launch portal. Nothing in this plan authorises publication.

Product: **NOVARA** — "Everything Connected. Everything Under Control."
Repository: https://github.com/ganeshkrishnareddy/novara
Expected Pages URL: https://ganeshkrishnareddy.github.io/novara/ — **not configured or verified live**; the site is prepared locally only.

---

## A. Purpose and scope

Define a small, static, honest launch portal that explains what NOVARA is, shows locally captured evidence, and points visitors to the repository and documentation. The portal is informational: it does not sign users up, collect data, process payments, send messages, or expose any backend.

This plan covers the deliverables prepared by a concurrent workstream: `site/index.html`, `site/assets/css/styles.css`, `site/assets/js/site.js`, `site/assets/img/*`, `site/videos/NOVARA_Product_Demo_1.0.mp4`, `site/sitemap.xml`, `site/robots.txt`, `.github/workflows/pages.yml`, `scripts/validate_site.py`, and the redesigned `README.md`. These files are documented here, not created or edited by this document.

## B. Audience

| Audience | Question the page must answer | Content response |
| --- | --- | --- |
| Developer evaluating the repository | What is it, how do I run it locally, what is actually verified? | Overview, local quick start, evidence section, links to `README.md` and `docs/` |
| Self-hoster / small-team operator | Is it local-first, what are the prerequisites, what is not yet verified? | Local-first architecture, SQLite default, explicit unverified items (containers, live PostgreSQL) |
| Contributor | How can I help, and what are the rules? | Contribution program link, engagement policy, privacy-conscious identity verification |
| General visitor | Is this a released product with customers and testimonials? | Honest status: **active development, not a release candidate**; no customer or testimonial claims |

No audience segment is addressed with invented users, customers, or outcomes.

## C. Product identity and messaging

- Name: NOVARA. Tagline, verbatim: **"Everything Connected. Everything Under Control."**
- Core message: one local-first, self-hostable product with a shared identity, workspace, permission model and customer timeline — not ten separate applications linked together.
- Supporting message: functional alternatives to ten inspiration projects, implemented locally or documented as compatible replacements; no affiliation and no codebase redistribution.
- Status message, required verbatim in substance: **active development, NOT a release candidate**; prepared locally, not published.
- Licensing message, required wording: **"open-source foundation subject to final repository licensing review; licence file pending owner decision."** Do not call the project "fully open source".

## D. Brand palette and typography

The visual system for the site is defined by `site/assets/css/styles.css`. The tokens below were verified against that file and in a real browser on 2026-11-24; see `artifacts/marketing_site_qa/cdp_site_*.png`.

| Token role | Plan | Evidence / constraint |
| --- | --- | --- |
| Page surface | Light, neutral background | QA observed light-theme app background `rgb(245, 247, 245)` (`docs/QA/MASTER_QA_REPORT.md`); site palette must be confirmed in CSS |
| Text / muted text / borders | Neutral greys with sufficient contrast | Accessibility target: readable body text and visible focus states; verify in browser checks |
| Accent | Single restrained accent used for links and primary controls | No third-party brand colours or marks from the ten reference projects |
| Semantic states | Success / warning / neutral for status labels only | Must not imply certification, security audit, or release status |
| Typography | System UI font stack; no external font requests | Keeps the page static, offline-capable and free of third-party requests; exact stack and scale owned by `styles.css` |

Light theme only. No dark mode. No third-party icons, fonts, CDNs, or analytics scripts.

## E. Content principles

1. **Evidence-bound:** every number on the site maps to a named file in `docs/` or `artifacts/`. See `WEBSITE_CONTENT_CLAIMS_AUDIT.md`.
2. **Status-first:** the "active development, not a release candidate" status appears above the fold; no impression of a released SaaS product.
3. **Local-first honesty:** local SQLite, local synthetic QA data, and local video captures are labelled as such.
4. **No social proof fabrication:** no stars, forks, downloads, users, customers, testimonials, uptime, or performance figures.
5. **No engagement incentives:** stars, forks and watches are voluntary GitHub actions; no benefits in exchange (see `COMMUNITY_CONTRIBUTION_PROGRAM.md`).
6. **Conditional language:** hosting, licensing, delivery, containers and mobile statements remain conditional until verified.
7. **Attribution care:** ten projects are inspiration/functional alternatives only; no affiliation implied; no source copied (`docs/research/LICENSE_COMPLIANCE.md`, `THIRD_PARTY_NOTICES.md`).

## F. Component inventory

| Component | Purpose | Implementation note |
| --- | --- | --- |
| Header / navigation | Product name, tagline, in-page anchors, repo link | Static HTML anchors; repo link is external and checked manually |
| Status banner | "Active development — not a release candidate" | Plain HTML, no dynamic badge service |
| Hero | Tagline, one-paragraph overview, primary actions | No animated counters or inflated metrics |
| Capability overview | Modules grouped by capability, described as connected local modules | Grouped from the ten inspirations, described without brand-logo use |
| Evidence strip | Feature-row counts, backend suite result, isolated QA counts | Values exactly as in `WEBSITE_CONTENT_CLAIMS_AUDIT.md`; each linked to its source doc |
| Demo section | Two local MP4s with captions and durations | Embedded local files under `site/videos/`; labelled local QA capture, synthetic data |
| Screenshot gallery | Local UI captures | From `artifacts/final_qa_2026-11-24/`; labelled local QA capture |
| Local-first / architecture block | Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite, vanilla JS light-theme app | No claim of container, PostgreSQL, mobile, provider or hosted-AI verification |
| "What is not yet verified" block | Explicit gaps list | Prevents overclaiming; mirrors README limitations |
| Contribution block | Link to `COMMUNITY_CONTRIBUTION_PROGRAM.md` | States no star/follow incentives; human review only |
| Licensing / attribution block | Required licensing wording, reference projects list, notices link | Link to `docs/research/LICENSE_COMPLIANCE.md` and `THIRD_PARTY_NOTICES.md` |
| Footer | Repository link, "prepared locally, not published", no-analytics notice | No tracking pixels or external scripts |

## G. Technical architecture

- Static HTML + CSS + vanilla JS only. No backend, no build framework, no runtime API.
- No secrets, tokens, credentials, environment variables, or form endpoints in the site.
- No analytics, cookies, trackers, third-party fonts, or remote scripts. No network calls required to view the page.
- Assets served from relative paths so the site works under the expected GitHub Pages subpath `/novara/`.
- Videos are static files copied from `artifacts/final_qa_2026-11-24/videos/` into `site/videos/`.
- `sitemap.xml` and `robots.txt` are static files; the sitemap uses the expected Pages URL **as a placeholder** until hosting is configured and verified.
- `.github/workflows/pages.yml` is a deployment workflow prepared locally; it must not be enabled or triggered without owner authorization.
- `scripts/validate_site.py` is a local static validator (links, assets, metadata, subpath-safe paths). Its results are recorded, not assumed.

## H. SEO plan

| Item | Plan |
| --- | --- |
| `<title>` / meta description | Product name + tagline; description states active development and local-first scope |
| Headings | One `<h1>`; descriptive `<h2>`/`<h3>` hierarchy matching components |
| Canonical URL | Use `https://ganeshkrishnareddy.github.io/novara/` **only after** Pages is enabled and verified; otherwise omit or keep clearly conditional |
| Open Graph / Twitter metadata | Title, description, local video thumbnail; no remote image URLs |
| `sitemap.xml` / `robots.txt` | Static, subpath-aware; sitemap URL conditional on verified hosting |
| Image alt text | Describe the visible UI and label as local QA capture |
| Link hygiene | Internal anchors resolve; external repo link checked manually by a human, not by an automated network call |
| Structured data | None that implies ratings, reviews, prices, uptime, or organisation endorsements |

## I. Analytics and privacy decision

**Decision: no analytics.** No page views, referrers, cookies, local-storage identifiers, third-party scripts, or external requests. Rationale: the portal is informational, the project is in active development, and the engagement policy forbids metrics-driven incentives. The footer states this plainly. If the owner later authorises measurement, it requires a separate documented decision with a privacy review before any code change.

## J. Contribution flow

1. Visitor reads the contribution program (`docs/COMMUNITY_CONTRIBUTION_PROGRAM.md`) and chooses a legitimate activity (docs, tests, bug reports, clean-room code, translations, accessibility, QA evidence).
2. Contribution is submitted for review; status moves through Submitted → Under review → Accepted / Needs changes / Rejected.
3. Optional identity verification via GitHub OAuth with explicit consent and minimum scopes, or safe manual verification; human review decides eligibility.
4. A star, follow, or watch is **not** a qualifying contribution and is never rewarded.
5. Any benefit is based on substantive contribution under published criteria and an approved budget, never on engagement metrics.

## K. Licensing and claims review

- Use exactly: "open-source foundation subject to final repository licensing review; licence file pending owner decision." There is **no root LICENSE file yet**. Do not say "fully open source".
- Licensing review is complete in `docs/research/LICENSE_COMPLIANCE.md` and `THIRD_PARTY_NOTICES.md`; no source was copied from the ten reference projects.
- All site claims pass through `docs/WEBSITE_CONTENT_CLAIMS_AUDIT.md` before being merged into HTML.
- Videos and screenshots are labelled as local QA captures using synthetic data; no customer data appears.

## L. Testing matrix

All rows below are **planned checks for `scripts/validate_site.py` and a human browser pass**; results are recorded in the completion report, not assumed here.

| Area | Check |
| --- | --- |
| Desktop viewport | Layout, navigation, no horizontal overflow, readable text |
| Tablet viewport | Layout reflow, tappable links, media sizing |
| Mobile viewport | Single-column flow, legible text, no clipped controls |
| Links | All internal anchors resolve; external repo link verified manually by a human |
| Assets | All images, CSS, JS, and all three MP4s resolve and load locally |
| Metadata | Title, meta description, headings, Open Graph tags, alt text present |
| Pages subpath | All asset URLs work under `/novara/`; no root-absolute `/assets/...` links |
| Validator | `scripts/validate_site.py` exits 0 with no unresolved errors; output archived |
| Privacy | No analytics, cookies, remote scripts, forms, or secrets in rendered page source |
| Claims | Page text matches `WEBSITE_CONTENT_CLAIMS_AUDIT.md`; status banner present |

## M. Deployment gates and owner authorization

Publication requires **all** of the following, in order:

1. Site files exist locally and the validator passes.
2. Desktop/tablet/mobile browser pass completed and recorded.
3. Claims audit and licensing wording confirmed against this plan.
4. `README.md` audit completed after its rewrite (`docs/GITHUB_README_AUDIT.md`).
5. Pages workflow reviewed; hosting enabled and verified by the owner.
6. **Explicit owner authorization to commit, push, and trigger deployment.** No commit, push, tag, release, or deployment occurs without it.

At time of writing: **not configured, not verified live, not published.**
