# Phase 4 browser evidence - Campaign Studio, Sales pipeline, Feedback Studio

Date: 2026-11-22
Environment: local uvicorn `127.0.0.1:8000`, Chromium browser, seeded local SQLite workspace
`206226fb-52f6-41e4-9a65-fc2d318d2a33` (QA Owner). All records are local only. No email, ad,
SMS, chat or any external message was sent. No third-party provider was contacted.

Server was started for this check and stopped afterwards (process confirmed `STOPPED`). The
complete request log is in the shell output for shell `sh_203ddf13b001rg6cvODaVw5RT2`.

## 1. Campaign Studio (`#/campaigns`)

- Page opened: heading "Campaign Studio", New campaign button, status filter, governance note
  "Campaigns and metrics are recorded here only. This build sends no email, ads or messages."
- Created campaign "Browser verification campaign" (email channel, goal "Verify campaign
  workflow locally") via New campaign form. API `POST /campaigns` -> `201 Created`; detail view
  opened automatically (`GET /campaigns/{id}` 200).
- Recorded a daily metric: date 2026-11-22, impressions 1200, clicks 120, leads 12, spend 45.5.
  API `POST /campaigns/{id}/metrics` -> `201 Created`. UI refreshed and showed:
  Metric days 1, Impressions 1200, Leads 12, Spend 45.50, and a Daily metrics table row
  `2026-11-22 | 1200 | 120 | 12 | 45.50`.
- Changed status Draft -> Active via the "Active" button. API `PATCH /campaigns/{id}` -> `200 OK`;
  badge updated to "Active" and remaining status buttons recalculated (Draft, Paused, Completed).

## 2. Sales pipeline (`#/deals`)

- Page opened: heading "Sales pipeline", New deal button, stage filter, stats cards.
- Created deal "Browser verification deal", company "Verification Co", value 2500, probability 40,
  stage New. API `POST /deals` -> `201 Created`; detail opened (`GET /deals/{id}` 200).
- Added activity type "Call", note "Intro discussion with verification co". API
  `POST /deals/{id}/activities` -> `201 Created`; Activity section rendered
  "Call / Intro discussion with verification co - 5h ago".
- Moved stage New -> Qualified via "Qualified" button. API `PATCH /deals/{id}` -> `200 OK`;
  header became "2,500.00 - Qualified - 40% probability", remaining stage buttons recalculated.

## 3. Feedback Studio (`#/surveys`)

- Page opened: heading "Feedback Studio", New survey button, governance note
  "Responses are recorded here only. This build does not distribute surveys or send invitations."
- Created survey "Browser verification survey", description "Onboarding satisfaction check". API
  `POST /surveys` -> `201 Created`; detail opened (`GET /surveys/{id}` 200).
- Recorded response score 9, comment "Very clear workflow", no linked contact. API
  `POST /surveys/{id}/responses` -> `201 Created`. UI refreshed and showed:
  Responses 1, Average score 9 / 10, With comment 1, Identified 0, and a response row
  `- | 9/10 | Very clear workflow | Nov 22, 2026`.

## Verification notes

- `node --check apps/web/app.js` clean after all wiring.
- Backend contract suite: `148 passed, 1 warning in 59.48s`
  (`docs/evidence/phase4-after-three-views-20261122.txt`), including new tests pinning the
  campaign, deal and survey response shapes (`test_phase4_ui_contract.py`).
- Skye's `docs/PHASE_4_MODULE_AUDIT.md` Top 5 gaps #1 Universal Search and #2 Customer Inbox
  were closed earlier (`docs/evidence/phase4-browser-20261122.md`); this record closes #3 Campaign
  Studio, #4 Sales pipeline and #5 Feedback Studio. All five audit gaps are now closed in code and
  browser-verified.
- Local-only governance upheld: no outbound delivery, no fake data or providers, light theme only.
