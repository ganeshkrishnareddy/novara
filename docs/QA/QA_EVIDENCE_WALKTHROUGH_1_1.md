# NOVARA — QA Evidence Walkthrough 1.1

**Date:** 2026-11-25 · **Status:** documentation revision; video file unchanged; not published.
**Video:** `artifacts/final_qa_2026-11-24/videos/NOVARA_Complete_QA_Walkthrough.mp4`, also served as `site/videos/NOVARA_QA_Evidence_Walkthrough.mp4` (00:03:16, 1920 × 1080, 15 fps, 4,048,244 bytes, decode exit 0).

## What changed in 1.1

The recording itself was not edited. Version 1.1 corrects the **label and the evidence record**:

- The site now calls this file **QA Evidence Walkthrough**, not “complete QA walkthrough”, because a route sweep is not proof of per-feature acceptance.
- This document adds the expected/observed record and limitations that the original chapter index did not contain.
- The newer connected-journey demonstration is documented separately in `docs/QA/PRODUCT_DEMO_2_EVIDENCE.md`.

## Expected / observed record

The walkthrough covers 21 module routes. The table groups them by function; exact final-video timestamps remain in `docs/QA/VIDEO_CHAPTER_INDEX.md`.

| Group | Routes | Expected | Observed |
|---|---|---|---|
| Workspace | `#/dashboard`, `#/search`, `#/insights`, `#/activity` | Command centre, search, descriptive counts and append-only activity render in the light theme | **PASS** — all four routes rendered; counts described as calculated from stored rows; events shown in sequence order |
| Relationships | `#/contacts`, `#/companies`, `#/leads`, `#/deals` | CRM records and pipeline stages render with synthetic data | **PASS** — all four routes rendered; no real customer data present |
| Operations | `#/campaigns`, `#/inbox`, `#/documents`, `#/document-engagement`, `#/tasks`, `#/projects`, `#/work-item-planning` | Campaign, support, document, task and project surfaces render and state their local boundaries | **PASS** — all seven routes rendered; campaign/inbox views explicitly state that nothing is sent |
| Governance and automation | `#/advanced-experiments`, `#/survey-delivery`, `#/agents`, `#/notification-automation`, `#/access-governance`, `#/settings` | Experimentation, agent governance, automation and access views render without external calls | **PASS** — all six routes rendered; agent view records configuration and approval state locally |

**Result:** 21/21 route renders PASS. This is a route-visibility result, not a feature-acceptance result.

## Limitations

- Route rendering does **not** prove that all 1,488 feature IDs were individually accepted. Authoritative dispositions remain 28 `PASS`, 932 `PARTIAL`, 70 `REPLACEMENT_VERIFIED`, 432 `NOT_APPLICABLE`, 26 `NOT_TESTED`, 0 `FAIL`.
- The video was captured at 15 fps with short chapter cards; UI text is smaller than in Product Demo 2.0. For readable, action-by-action evidence use Demo 2.0.
- The recording shows navigation rather than end-to-end workflows. The connected journey, segment, approval gate and audit verification are demonstrated in `NOVARA_Product_Demo_2.0.mp4`.
- Local SQLite QA workspace and synthetic data only; no deployed database, real customer, outbound message or hosted provider call.
- Narration is locally synthesized (Microsoft David Desktop); no hosted speech service was contacted.

## Reproduction and integrity

The raw capture, generated cards, narration WAV and concat segments remain under `artifacts/final_qa_2026-11-24/videos/`. Verification metadata is in `evidence/video_walkthrough_verification.json` and `evidence/video_walkthrough_raw.json`. No file in this path is published or committed by this workstream.
