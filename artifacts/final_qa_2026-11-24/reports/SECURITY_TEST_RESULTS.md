# Security and negative test results

Date: 2026-11-24. Instance: local isolated NOVARA QA instance at `http://127.0.0.1:8765`.
Evidence: `../artifacts/final_qa_2026-11-24/evidence/qa_security_log.jsonl` and the security section of `evidence/qa_api_log.jsonl`.
All identities are synthetic `.invalid` addresses. No real account, token, phone number, or provider was used.

## Result summary

17 of 17 dedicated security checks returned the expected outcome. This means the observed response matched the recorded expectation; it does not establish a formal security audit or production hardening.

| # | Scenario | Expected | Observed | Result |
|---:|---|---|---|---|
| 1 | Valid synthetic owner login | 200 | 200 | PASS |
| 2 | Second synthetic identity login | 200 | 200 | PASS |
| 3 | Wrong password rejected | 401 | 401 | PASS |
| 4 | Unknown account rejected | 401 | 401 | PASS |
| 5 | Tampered bearer token rejected | 401/403 | 401 | PASS |
| 6 | Missing bearer token rejected | 401/403 | 401 | PASS |
| 7 | Malformed workspace UUID rejected | 400/403/404/422 | 403 | PASS |
| 8 | Workspace A contact list readable by owner | 200 | 200 | PASS |
| 9 | Workspace B token reading Workspace A contact denied | 403/404 | 403 | PASS |
| 10 | Duplicate synthetic contact email rejected | 409 | 409 | PASS |
| 11 | Foreign contact id rejected on note creation | 403/404 | 403 | PASS |
| 12 | Invalid email rejected by intake | 422 | 422 | PASS |
| 13 | SQL-like search input handled literally | 200 | 200 | PASS |
| 14 | Script-like text stored as inert data | 201/409 | 201 | PASS |
| 15 | Oversized free text handled without server error | 200/201/413/422 | 201 | PASS |
| 16 | Invalid public form token fails closed | 400/403/404/422 | 422 | PASS |
| 17 | Workspace B token denied admin settings of A | 403/404 | 403 | PASS |

Additional security-relevant checks recorded in the API harness:
- Invalid login returned 401.
- Duplicate contact returned 409.
- Cross-workspace denial returned 403.
- Tampered token returned 401.
- Read-only GET sweep excluded streaming endpoints and used required query parameters derived from the live OpenAPI contract.

## Interpretation and limits

- Check 13 confirms the request was accepted and returned 200; it does not prove every SQL injection class is impossible. No source-code security audit was performed.
- Check 14 confirms script-like text was accepted as stored data. UI escaping was observed through normal rendering but no dedicated stored-XSS payload replay in the browser was executed. Do not treat this as an XSS clearance.
- Check 15 returned 201 for a 200,000-character field. The endpoint accepted the body without a server error; there is no evidence here that a size limit exists. This is recorded honestly, not as a passing hardening control.
- Check 16 confirms a bogus public form token was rejected with 422; no real public form token was used.
- No live external identity provider, SSO, OAuth, payment provider, email provider, SMS/WhatsApp gateway, or hosted AI model was contacted.
- Tokens were generated inside the isolated QA database and are not included in reports.
