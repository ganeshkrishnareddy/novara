# Marketing site deployment report — Campaign 2

Original observation: 2026-11-25 12:23 IST. Updated 2026-11-25 (IST) after live deployment verification. Scope: publication and verification state of the NOVARA marketing site only. No backend deployment was performed.

## Verdict

**MARKETING SITE DEPLOYMENT: LIVE AT `https://ganeshkrishnareddy.github.io/novara/`.**

The original deploy failed because GitHub Pages was not enabled. Pages was subsequently enabled with source `main` / `/` and build type `workflow`, workflow `45556726447` was rerun and completed with conclusion `success`, and the public URL plus all checked assets returned HTTP 200. This is a marketing-site deployment claim only; no backend deployment was performed.

## Publication set

Commit `f1dcfefe162faac644e974f075a411eb0975f4cb` ("Publish NOVARA public marketing portal via GitHub Pages") was pushed to `main`. It contains only:

- `site/` — HTML, CSS, JavaScript, images, screenshots and the two requested real MP4 walkthrough/demo files plus additional local demo/evidence videos.
- `.github/workflows/pages.yml`
- `scripts/validate_site.py`

README, backend, test, evidence and unrelated uncommitted work were deliberately excluded. HEAD remained `f1dcfefe162faac644e974f075a411eb0975f4cb` at this check; no later Git action was taken.

## Local verification before publication

| Check | Observed result | Evidence |
|---|---|---|
| Static validator | 35 passed, 0 failed, 0 warnings, 15 informational notes; `RESULT: PASS` | `artifacts/marketing_site_qa/validator-final.txt` |
| Browser checks at `/` | 20/20, desktop/tablet/mobile, 0 console problems | `artifacts/marketing_site_qa/verify_site.json`, screenshots |
| Browser checks at `/novara/` subpath | 20/20, desktop/tablet/mobile, 0 console problems | `artifacts/marketing_site_qa/verify_subpath.json`, screenshots |
| Community links/content | 20/20 local checks | `artifacts/marketing_site_qa/verify_community.json` |
| Application routes | local app checks passed | `artifacts/marketing_site_qa/verify_app.json` |
| Secret/local-path scan of publication set | 0 findings | validator output |

Local QA was performed in Chromium only. Non-Chromium browser rendering was not verified.

## GitHub Actions observation

Initial observation: GitHub API `GET /repos/ganeshkrishnareddy/novara/actions/runs?per_page=10` reported `total_count=1`, run `45556726447`, head SHA `f1dcfefe162faac644e974f075a411eb0975f4cb`, overall conclusion `failure`.

Initial job detail from `GET /repos/ganeshkrishnareddy/novara/actions/runs/45556726447/jobs`:

| Job | Conclusion | Observed steps |
|---|---|---|
| `build` | success | checkout, Python setup, `python scripts/validate_site.py`, stage static site, upload Pages artifact all succeeded |
| `deploy` | failure | "Deploy to GitHub Pages" step failed |

That failure was consistent with GitHub Pages not being configured, not with a site-source validator failure. After enabling Pages, the same run was rerun: attempt 2 moved from `in_progress` to `completed` with conclusion `success`.

## Live publication checks

| Check | Observed result |
|---|---|
| `GET https://api.github.com/repos/ganeshkrishnareddy/novara/pages` before enablement | HTTP 404 |
| Pages configuration after enablement | build type `workflow`, source `main` / `/`, URL `https://ganeshkrishnareddy.github.io/novara/` |
| Workflow `45556726447` attempt 2 | `completed`, conclusion `success` |
| `GET https://ganeshkrishnareddy.github.io/novara/` | HTTP 200, 50,989 bytes; title and full section outline rendered in the Browser tab |
| CSS, logo, favicon, OG image, dashboard screenshot | HTTP 200 |
| Demo videos (`NOVARA_Product_Demo_2.0.mp4`, `NOVARA_QA_Evidence_Walkthrough.mp4`) | HTTP 200; embedded demo reached `readyState=4` |
| Lazy-loaded screenshots (`02_contacts.png`, `08_projects.png`, `10_experimentation.png`) | HTTP 200 each; not decoded in the headless viewport because they are below the fold |
| `sitemap.xml` and `robots.txt` | HTTP 200 |
| Browser DOM check | 6 images, 47 links, 1 video; white light-theme background; no hard asset failures |
| Console errors | none reported in the verified Browser-tab session |

## Live verification boundary

Marketing-site deployment-platform verification is now **100%**: GitHub Pages is enabled, the workflow succeeded, and the live URL plus all checked assets returned HTTP 200. This does not change backend or hosted-application deployment verification, which remains **0%** because no backend deployment was performed.

Non-Chromium browser rendering, formal penetration testing, live provider delivery and product release acceptance remain unverified. No backend deployment or external transaction was performed.
