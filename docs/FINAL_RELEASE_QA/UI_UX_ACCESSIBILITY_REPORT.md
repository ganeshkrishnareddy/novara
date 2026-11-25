# UI, UX and accessibility report

Timestamp: 2026-11-25. Sources: `../../artifacts/marketing_site_qa/verify_site.json`,
`verify_subpath.json`, screenshots in the same folder, and `../QA/MASTER_QA_REPORT.md`.

| Check | Observed |
|---|---|
| Marketing site, root URL — 20 browser checks | 20/20 true; 0 console problems |
| Marketing site, `/novara/` subpath — 20 browser checks | 20/20 true; 0 console problems |
| Viewports | desktop, tablet and mobile rendered and captured |
| Rendering | CSS loaded, images loaded with alt text, fragments resolve, video source resolves with controls, no mojibake |
| Privacy | no cookies set, no external requests, no console errors, light background only |
| Application module routes | 50 configured routes rendered after two genuine frontend defects were corrected |

Evidence files: `verify_site.json`, `verify_subpath.json`, `cdp_site_desktop.png`, `cdp_site_tablet.png`,
`cdp_site_mobile.png`, `cdp_subpath_*.png`.

Limitations: Chromium-family browser only. Non-Chromium browsers, screen readers and automated axe/WCAG
scoring were not run; this is not a formal accessibility certification.
