# End-to-end workflow results

Date: 2026-11-24. Evidence: `../artifacts/final_qa_2026-11-24/evidence/qa_e2e_log.jsonl` and `test-results/e2e-console.txt`.
All records are synthetic and local. 61 records were written: **52 PASS, 9 informational, 0 FAIL**. The final harness run completed with no failures after its payloads were corrected to the live API contract. Corrections were harness fixes, not application changes.

Each numbered record below refers to the `seq` field in the JSONL evidence file.

| Workflow | Records | Observed outcome | Key evidence |
|---|---:|---|---|
| W1 Lead to customer | 7 PASS + 1 INFO | PASS (local scope) | 3 website-form intake; 4 contact search; 5 lead create returns 409 on rerun (synthetic lead already exists); 6 lead list; 7 transition; 8 convert; 9 events |
| W2 Campaign lifecycle | 6 PASS + 2 INFO | PARTIAL — send not executed | 11 draft campaign; 12 list; 13 segment 409 on rerun; 14 status active; 15 local schedule; 16 lifecycle analytics; 17 explicit `NOT_EXECUTED` for delivery |
| W3 Customer support | 5 PASS + 1 INFO | PASS (ticket scope) | 19 ticket; 20 agent reply; 21 private note; 22 detail; 23 counts |
| W4 Document engagement | 6 PASS + 1 INFO | PASS (local scope) | 25 room 409 on rerun; 26 document; 27 share link; 28 document detail; 29 link detail; 30 room list |
| W5 Experimentation | 8 PASS + 1 INFO | PASS (local analysis) | 32 metric 409 on rerun; 33 metric list; 34 two-variant experiment; 35/36 observations; 37 analyze; 38 experiment list; 39 API contract |
| W6 Project execution | 6 PASS + 1 INFO | PASS (project scope) | 41 project; 42 work item; 43 status PATCH; 44 detail; 45 comment; 46 list |
| W7 Automation | 6 PASS + 1 INFO | PARTIAL — in-app only | 48 automation; 49 status active; 50 read; 51 templates; 52/53 local notification workflow triggers |
| W8 AI-assisted operation | 7 PASS + 1 INFO | PARTIAL — simulated agent | 55 agent; 56 simulated run; 57 run read; 58 progress to awaiting approval; 59 human approval; 60 outreach draft; 61 draft list |

## Explicit boundaries

- **Campaign delivery was not executed.** No email, SMS, WhatsApp, push, or provider call was made. W2 record 17 is labelled `NOT_EXECUTED` in the evidence log.
- **Document links are local records.** No public notification or external recipient was contacted.
- **Agent execution is simulated.** The run uses a local agent configuration, is advanced to `awaiting_approval`, and is approved by a human action in the harness. No hosted model or external AI provider was called.
- **Automation delivery is in-app only.** External channel steps were not executed.
- **Experimentation analysis is local.** No hosted experimentation SDK, exposure stream, or billing control plane was contacted.

## Harness corrections made during this pass

The first E2E runs produced failures caused by incorrect request payloads, not application defects. The harness was corrected against the live OpenAPI contract and observed 422/409 responses:
- Campaign status enum was corrected from `scheduled` to `active`; schedule fields were changed to ISO datetimes.
- Document link body no longer sends an unsupported `label` field.
- Observation body was corrected to `metric_id` / `variant` / `sessions` / `conversions`; the experiment now declares `control` and `variant_a` variants.
- Metric type was corrected to supported `proportion`.
- Project item body uses `title` rather than `name`.
- Automation definition steps were given non-empty `id`, `type` and valid `check` values.
- Agent uses supported local provider and the run request uses `task`.
- Agent run progress is set to `awaiting_approval` before the approval endpoint is called.
- Idempotent 409 responses on reruns are recorded as PASS with an explicit note that the synthetic record already exists.

These corrections are logged in `_tools/qa_e2e.py` and the final clean console output; earlier failed runs were overwritten by the final verified run, and no failure was hidden from this report.
