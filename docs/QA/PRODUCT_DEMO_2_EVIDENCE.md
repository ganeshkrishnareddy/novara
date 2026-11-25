# NOVARA Product Demo 2.0 — connected-journey evidence

**Date:** 2026-11-25 · **Status:** locally recorded, assembled and decoded; not published.
**Video:** `artifacts/demo_v2_work/videos/NOVARA_Product_Demo_2.0.mp4` (copied to `site/videos/`).
**Duration:** 00:03:12.27 · 1920 × 1080 · 30 fps · AAC narration · decode exit 0 · 4,981,650 bytes.
**Source:** unedited desktop capture of the running NOVARA application at `127.0.0.1:8765`, driven by real clicks, typing and form submissions through its local interface. The capture is 00:02:52.27; a 4 s title card and a 16 s limitations card are the only generated video segments.

## Why this revision exists

The first two recordings showed module routes clearly but demonstrated page viewing rather than feature behaviour. This revision answers the specific gap: **one customer, one connected journey**. Each step below is an observed UI action, not a title card or a simulated screen. The runtime was extended to the requested 3–5 minute range by holding each real screen long enough to read it, not by repeating footage.

## Observed steps

Every row was recorded in `artifacts/demo_v2_work/journey_evidence.json` together with the text observed on screen. Eleven of eleven steps passed in the same run that was captured on video.

| # | Action performed in the real UI | Expected | Observed result |
|---|---|---|---|
| 1 | Open the command centre | Overview renders with live workspace counts | **PASS** — Overview and current counts visible |
| 2 | Submit one website-form intake | One submission creates linked records under a shared correlation id | **PASS** — new contact, lead, task, draft and notification; correlation `45dbef87…` |
| 3 | Open the created contact | Cross-module events appear on one identity | **PASS** — unified timeline with 5 correlation references |
| 4 | Qualify then convert that exact lead | Lead state changes through its row controls | **PASS** — `New → Qualified`, then convert control used |
| 5 | Create an audience segment from contact attributes; refresh the view | Segment is stored and the count increases | **PASS** — stored segments `8 → 9` after refresh |
| 6 | Create a campaign draft for that audience | A draft campaign is recorded; no outbound send | **PASS** — “Northstar welcome journey” appears in Campaign Studio |
| 7 | Use the human approval gate on the intake-generated outreach draft | Approval is recorded without delivery | **PASS** — Approve control used on the draft for Jordan Rivera; the transient toast had cleared when the DOM snapshot was read, so the recorded evidence is the control click and re-rendered view |
| 8 | Create a support ticket linked to that contact | Ticket opens against the same CRM identity | **PASS** — ticket detail rendered, linked and open |
| 9 | Complete the exact follow-up task created by intake | Task state is saved as done | **PASS** — `Open → Done` on the task linked to the journey |
| 10 | Refresh Insights | Counts recalculate from stored rows | **PASS** — insights rendered with current local counts and the stated no-external-analytics note |
| 11 | Inspect the activity view | Events are append-only and in sequence | **PASS** — 359 recorded events shown in sequence order |

**Step result:** 11/11 PASS. All records are synthetic. No email, message, ad, notification delivery or hosted provider call was made.

## Linked identifiers from the recorded run

| Record | ID |
|---|---|
| Contact | `e64bf7ca-d0d5-440a-9474-9da577abeb4b` |
| Lead | `b8fa9d8f-7165-4d3e-a91e-4ac9221e0d48` |
| Task | `fe2481de-e7ad-4956-a629-abe11a68e0c5` |
| Draft | `7da1d8dd-5101-46f3-bc26-208970a84a0e` |
| Correlation | `45dbef87-aa6d-450c-9730-93364187b12d` |
| Audience segment | `northstar-welcome-final2` — “Northstar welcome audience - connected journey” |
| Synthetic submitter | `demo12.journey@novara.invalid` |
| Submission ID | `DEMO2-20261125-REC21` |

Recording window: 2026-11-24 18:49:03–18:51:52 UTC (2026-11-25 local).

## QA distinction

This video is evidence of **connected workflows**, not proof that all 1,488 feature IDs were individually accepted. The honest disposition record remains: 28 `PASS`, 932 `PARTIAL`, 70 `REPLACEMENT_VERIFIED`, 432 `NOT_APPLICABLE`, 26 `NOT_TESTED`, 0 `FAIL`; the parity ledgers account for 1,418 `VERIFIED_COMPLETE` plus 70 compatible replacements. The clean full-suite result is `1,641 passed, 4 warnings in 1395.31s (0:23:15)`, exit 0, in `docs/evidence/t131-fullsuite-clean-20261124.txt`.

## Limitations

- Local SQLite QA workspace, not a deployed PostgreSQL instance.
- Synthetic data only; no real customer, external integration, email, SMS, WhatsApp or payment action.
- The recording is a desktop capture at 30 fps. Title card 4 s, limitations card 16 s; the eleven application screens are held for readability rather than padded with repeated footage. Browser zoom was not applied, so application text remains at its native light-theme scale; the generated cards use 30–96 px type.
- Audience segments are validated by stored count because the Feedback intelligence view reports a count rather than listing segment names. The segment rules were set to match the synthetic contact's company attribute.
- The approval toast is transient; the DOM observation records the control click and re-rendered drafts view, not the toast text.
- The earlier `NOVARA_Complete_QA_Walkthrough.mp4` remains a module sweep. It is now labelled **QA Evidence Walkthrough** on the site; its expected/observed record is in `docs/QA/QA_EVIDENCE_WALKTHROUGH_1_1.md`.

## Reproduction

Run from the repository root while the local QA app is available at `127.0.0.1:8765` and the NOVARA page is open in a Chrome session with local debugging enabled. Use fresh synthetic identifiers if the same submission ID has already been used.

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:JOURNEY_SPEED='normal'
$env:DEMO_HOLD='13'
$env:DEMO_EMAIL='demo12.journey@novara.invalid'
$env:DEMO_SUBMISSION='DEMO2-20261125-REC21'
$env:DEMO_SEGMENT='northstar-welcome-final2'
$env:DEMO_SEGMENT_NAME='Northstar welcome audience - connected journey'
python 'D:\NOVARA\artifacts\demo_v2_work\record_v2.py'
python 'D:\NOVARA\artifacts\demo_v2_work\build_v2.py'
python 'D:\NOVARA\scripts\validate_site.py'
```

Nothing in these scripts publishes or commits anything.
