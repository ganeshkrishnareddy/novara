# Video chapter index

Three MP4 files were produced from **actual screen recordings** of the running local NOVARA QA instance using bundled `ffmpeg` `gdigrab` at 1920x1080. The older two were captured at 15 fps with per-chapter cards; the connected-journey demo was captured at 30 fps with only a title card and a limitations card. No application frame was simulated by animation or fabricated from still images; every application frame came from the live UI.

Deliverables:
- `../artifacts/final_qa_2026-11-24/videos/NOVARA_Complete_QA_Walkthrough.mp4` — H.264 1920x1080 15 fps, AAC audio, 00:03:16, 4,048,244 bytes, decode exit 0. Served on the site under the honest filename `NOVARA_QA_Evidence_Walkthrough.mp4`; evidence record: `QA_EVIDENCE_WALKTHROUGH_1_1.md`.
- `../artifacts/final_qa_2026-11-24/videos/NOVARA_Product_Demo_1.0.mp4` — H.264 1920x1080 15 fps, AAC audio, 00:01:40, 2,236,056 bytes, decode exit 0.
- `../artifacts/demo_v2_work/videos/NOVARA_Product_Demo_2.0.mp4` — H.264 1920x1080 30 fps, AAC audio, 00:03:12, 4,981,650 bytes, decode exit 0. Eleven real actions, one shared correlation id; evidence record: `PRODUCT_DEMO_2_EVIDENCE.md`.

Verification metadata: `../artifacts/final_qa_2026-11-24/evidence/video_walkthrough_verification.json` and `video_demo_verification.json`; `../artifacts/demo_v2_work/demo_v2_verification.json` and `journey_evidence.json`. Raw capture metadata and unedited chapter start times: `video_walkthrough_raw.json` and `video_demo_raw.json`.

Timestamps for the older videos are approximate positions in the **final assembled video** (5 s title card, 2 s chapter card before each segment, 7 s limitation card at the end). The raw capture start times are preserved in the raw metadata files.

## NOVARA_Complete_QA_Walkthrough.mp4 (21 chapters)

| # | Chapter | Route | Final-video start | Final-video end |
|---:|---|---|---:|---:|
| 1 | Overview / Command Center | `#/dashboard` | 00:07 | 00:15 |
| 2 | Universal search | `#/search` | 00:17 | 00:23 |
| 3 | Insights | `#/insights` | 00:25 | 00:31 |
| 4 | Agent activity / audit spine | `#/activity` | 00:33 | 00:39 |
| 5 | Contacts / CRM | `#/contacts` | 00:41 | 00:49 |
| 6 | Companies | `#/companies` | 00:51 | 00:56 |
| 7 | Leads | `#/leads` | 00:58 | 01:05 |
| 8 | Sales pipeline | `#/deals` | 01:07 | 01:13 |
| 9 | Campaign Studio | `#/campaigns` | 01:15 | 01:23 |
| 10 | Customer inbox | `#/inbox` | 01:25 | 01:33 |
| 11 | Documents | `#/documents` | 01:35 | 01:42 |
| 12 | Document engagement | `#/document-engagement` | 01:44 | 01:51 |
| 13 | Tasks | `#/tasks` | 01:53 | 01:58 |
| 14 | Projects | `#/projects` | 02:00 | 02:08 |
| 15 | Work-item planning | `#/work-item-planning` | 02:10 | 02:17 |
| 16 | Advanced experimentation | `#/advanced-experiments` | 02:19 | 02:27 |
| 17 | Survey delivery | `#/survey-delivery` | 02:29 | 02:35 |
| 18 | Agent center | `#/agents` | 02:37 | 02:44 |
| 19 | Notification automation | `#/notification-automation` | 02:46 | 02:53 |
| 20 | Access governance | `#/access-governance` | 02:55 | 03:02 |
| 21 | Settings | `#/settings` | 03:04 | 03:09 |

Narrator: Microsoft David Desktop. The narration explicitly states synthetic data, no external delivery and the distinction between route visibility and per-feature acceptance.

## NOVARA_Product_Demo_1.0.mp4 (8 chapters)

| # | Chapter | Route | Final-video start | Final-video end |
|---:|---|---|---:|---:|
| 1 | One connected workspace | `#/dashboard` | 00:07 | 00:16 |
| 2 | Customer records | `#/contacts` | 00:18 | 00:27 |
| 3 | Leads and conversion | `#/leads` | 00:29 | 00:38 |
| 4 | Campaign Studio | `#/campaigns` | 00:40 | 00:49 |
| 5 | Customer inbox | `#/inbox` | 00:51 | 01:00 |
| 6 | Projects and work items | `#/projects` | 01:02 | 01:11 |
| 7 | Experimentation | `#/advanced-experiments` | 01:13 | 01:22 |
| 8 | Agent center with approval gate | `#/agents` | 01:24 | 01:33 |

Narrator: Microsoft Zira Desktop. The narration explicitly states that campaign delivery is not performed and that the demo uses synthetic QA data only.

## NOVARA_Product_Demo_2.0.mp4 (11 connected actions, 30 fps)

Final-video positions are approximate. The unedited capture runs from 00:04 to 02:56; the limitations card runs from 02:56 to 03:12.

| # | Chapter | Route | Approx. start |
|---:|---|---|---:|
| 1 | Command centre | `#/dashboard` | 00:04 |
| 2 | Website-form intake | `#/contacts` | 00:20 |
| 3 | Unified contact timeline | `#/contacts/<id>` | 00:36 |
| 4 | Lead qualified and converted | `#/leads` | 00:52 |
| 5 | Audience segment created and refreshed | `#/feedback-intelligence` | 01:08 |
| 6 | Campaign draft recorded | `#/campaigns` | 01:24 |
| 7 | Human approval gate used | `#/drafts` | 01:40 |
| 8 | Support ticket linked to the contact | `#/inbox` | 01:56 |
| 9 | Follow-up task completed | `#/tasks` | 02:12 |
| 10 | Insights refreshed | `#/insights` | 02:28 |
| 11 | Append-only audit events | `#/activity` | 02:44 |
| — | Limitations card | generated | 02:56 |

Narrator: Microsoft Zira Desktop at a slower rate. The narration explicitly states synthetic data, no external delivery and the distinction between connected workflows and per-feature acceptance. Expected/observed results and linked identifiers are in `PRODUCT_DEMO_2_EVIDENCE.md`.

## Honest note about the recordings

- The two older videos evidence route rendering, UI state and navigation. Demo 2.0 additionally evidence real create, edit, save, refresh, approval and verification actions on one synthetic customer. None of them proves that all 1,488 source features passed; the registry remains the authoritative execution record.
- Screen capture was from a desktop session, not a dedicated clean-room recorder; incidental OS UI may appear at the edges.
- No real user, customer, message, or provider interaction appears in the recordings.
- Raw unedited captures, generated cards, narration WAV files and concat segments remain under `videos/` for reproducibility.
