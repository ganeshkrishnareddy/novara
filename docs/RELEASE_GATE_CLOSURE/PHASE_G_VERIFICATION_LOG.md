# Phase G verification log — Release Gate Closure

Timestamp: 2026-11-25 13:32–13:33 IST. Environment: this computer, project root `D:\NOVARA\`, Python from the project environment, Node.js on PATH, built-in Browser tab for live-page checks. No application, test, migration or runtime configuration changed during this campaign, so the full backend suite was not rerun.

## Executions

| # | Command / check | Start | End | Exit | Result | Log / evidence |
|---|---|---|---|---:|---|---|
| G-1 | `python scripts/validate_site.py` (from `D:\NOVARA`) | 2026-11-25T13:32:10.9344321+05:30 | 2026-11-25T13:32:11.1289976+05:30 | 0 | 35 passed, 0 failed, 0 warnings, 15 informational; `RESULT: PASS` | `docs/RELEASE_GATE_CLOSURE/PHASE_G_VALIDATOR.txt` |
| G-2 | `node --check apps/web/app.js` (from `D:\NOVARA`) | 2026-11-25T13:32:27.7476232+05:30 | 2026-11-25T13:32:27.8351770+05:30 | 0 | No syntax errors | `docs/RELEASE_GATE_CLOSURE/PHASE_G_NODE_CHECK.txt` |
| G-3 | `python -m alembic heads` (from `D:\NOVARA\apps\api`) | 2026-11-25T13:32:43.4991230+05:30 | 2026-11-25T13:32:45.2833603+05:30 | 0 | `e0f1a2b3c4d5 (head)` — single head | `docs/RELEASE_GATE_CLOSURE/PHASE_G_ALEMBIC_HEADS.txt` |
| G-4 | Live Browser-tab check at `https://ganeshkrishnareddy.github.io/novara/` | observed after 13:32 IST | observed after 13:32 IST | n/a | Page rendered; see details below | Browser-tab snapshot and DOM evaluation in this session |

G-3 note: an earlier attempt piped output to a relative log path from `D:\NOVARA\apps\api` and failed to create the file (`EXIT=-1` for that pipeline). The command was then rerun successfully with an absolute log path; G-3 above is the successful execution. G-2 succeeded with exit 0 on its first run.

## G-4 live browser details

- URL: `https://ganeshkrishnareddy.github.io/novara/`
- Title: `NOVARA — Your Entire Business. One Connected System.`
- Canonical: `https://ganeshkrishnareddy.github.io/novara/`
- Viewport: 1280 × 720 (desktop). Mobile/tablet rendering was verified locally in Campaign 2 (20/20 at root and 20/20 at `/novara/` subpath); it was not re-run at a changed viewport during this fresh check.
- Links: 47. Images: 6, with 0 decoded failures. Embedded video `NOVARA_Product_Demo_2.0.mp4` reached `readyState=4`.
- Background: `rgb(255, 255, 255)` — light theme, no accidental dark theme.
- Full section outline rendered, including all module cards, ten source-project table, workflow section, self-hosting, community and FAQ.
- No JavaScript console errors were reported in the Browser-tab session.
- No unexpected external script or stylesheet requests were introduced; the validator reported zero external HTTP(S) `<script src>` and zero external stylesheet URLs.

## Backend regression baseline

Not rerun. `docs/FINAL_RELEASE_QA/REGRESSION_TEST_REPORT.md` records `python -m pytest apps/api/tests -q` as **1,641 passed, 4 warnings, exit 0 in 1267.47s**. No application code, test code, database migration or runtime configuration changed after that baseline; the launch used the already committed static site and existing workflow. Any later code/config repair requires a fresh full-suite run.

## Boundary

These results establish local static-site validity, syntax and migration-head integrity, plus live marketing-page rendering. They do not establish backend deployment, live provider verification, licence approval, packaging readiness or product release acceptance.
