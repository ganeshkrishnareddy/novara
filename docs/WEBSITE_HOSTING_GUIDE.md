# NOVARA website hosting guide — preparation only

This guide prepares for static hosting. It does **not** enable GitHub Pages, deploy anything, or authorise publication. At time of writing, Pages is **not configured or verified live**; the site is prepared locally only.

- Product: NOVARA — "Everything Connected. Everything Under Control."
- Repository: https://github.com/ganeshkrishnareddy/novara
- Expected Pages URL: https://ganeshkrishnareddy.github.io/novara/ — placeholder, **not configured or verified live**

## 1. Hosting model

| Item | Plan |
| --- | --- |
| Host | GitHub Pages, project site under the `novara` repository |
| Expected subpath | `/novara/` (all page and asset URLs must work under this path) |
| Content | Static `site/` directory: HTML, CSS, vanilla JS, images, two local MP4s, `sitemap.xml`, `robots.txt` |
| Backend | None. No API, no database, no server-side code, no secrets, no forms |
| Third-party services | None: no analytics, no CDN, no remote fonts, no tracking scripts |
| Purpose | Informational launch portal only — not a commercial SaaS offering |

## 2. Subpath and asset base paths

GitHub Pages project sites serve content at `https://<owner>.github.io/<repo>/`. For this repository the subpath is `/novara/`.

Rules for the site build:

- Use **relative asset paths** (for example `assets/css/styles.css`, `assets/img/...`, `videos/NOVARA_Product_Demo_1.0.mp4`) so resources resolve under `/novara/` and in a local preview.
- Do **not** use root-absolute paths such as `/assets/...` or `/videos/...`; they break under the subpath.
- Internal links are relative anchors or relative files; the external repository link is absolute and checked manually.
- `sitemap.xml` may reference `https://ganeshkrishnareddy.github.io/novara/` only as an expected placeholder until hosting is configured and verified.
- `robots.txt` is static and subpath-aware; no directives that imply a live, indexed production site before verification.

## 3. Workflow description (prepared, not enabled)

`.github/workflows/pages.yml` has been prepared locally as a static-site deployment workflow. Its shape:

- triggers are reviewed and explicitly approved by the owner before the file is enabled or any run is allowed;
- build step is effectively a copy/publish of the `site/` directory — there is no framework build, no dependency install requiring secrets, and no backend;
- artifact is the static site content only;
- deployment target is GitHub Pages at the expected subpath;
- no step commits, pushes, tags, creates releases, or performs external network calls beyond the approved Pages deployment itself.

**No workflow has been enabled, triggered, or verified.** The file is present locally but is inert until the owner authorizes and configures Pages; see `MARKETING_WEBSITE_COMPLETION_REPORT.md`.

## 4. Local build and validation commands

There is no compile step. From the repository root on Windows PowerShell:

```powershell
# Serve the prepared site locally for a visual check
& 'D:\NOVARA\.venv\Scripts\python.exe' -m http.server 8000 --directory 'D:\NOVARA\site'

# Run the static validator (standard library only)
python 'D:\NOVARA\scripts\validate_site.py'
```

On macOS / Linux:

```sh
python3 -m http.server 8000 --directory site
python3 scripts/validate_site.py
```

Then open `http://localhost:8000/` and check the page at a simulated subpath where practical. Validator output must be archived; an unrun validator is not a pass.

Manual checks after the script runs:

| Check | Expected |
| --- | --- |
| Links | Internal anchors resolve; repository link verified by a human |
| Assets | CSS, JS, all images and all three MP4s load from the local server |
| Subpath | No broken paths when served under `/novara/` |
| Metadata | Title, description, Open Graph tags, alt text, sitemap, robots present |
| Privacy | No analytics, cookies, remote scripts, forms, or secrets in page source |
| Claims | Text matches `docs/WEBSITE_CONTENT_CLAIMS_AUDIT.md` |

## 5. Why Pages is informational only

- It hosts **static files** describing the product; it does not run NOVARA.
- No account creation, login, payment, data collection, messaging, campaign delivery, or hosted AI call occurs through the site.
- No uptime, availability, or SLA is implied. Pages is not configured or verified live, and the portal is not a commercial service.
- The application itself remains local-first: Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite by default, vanilla JS light-theme web app; no native mobile apps; no hosted provider calls executed.
- The site carries the honest status ("active development, not a release candidate") and the required licensing wording ("open-source foundation subject to final repository licensing review; licence file pending owner decision").

## 6. Deployment gate — no deploy without authorization

**No commit, push, tag, release, workflow enablement, or deployment without explicit owner authorization.** Required sequence:

1. Site files exist locally and `scripts/validate_site.py` exits 0 with archived output.
2. Desktop / tablet / mobile browser pass completed and recorded.
3. Claims audit (`docs/WEBSITE_CONTENT_CLAIMS_AUDIT.md`) and README audit (`docs/GITHUB_README_AUDIT.md`) completed against final text.
4. Owner reviews the workflow, the expected subpath, and all published text.
5. Owner explicitly authorizes commit, push, Pages enablement, and deployment.
6. Only then may the site go live; hosting must be verified after deployment and the completion report updated.

Until step 5, the correct statement is: **not configured, not verified live, not published.**
