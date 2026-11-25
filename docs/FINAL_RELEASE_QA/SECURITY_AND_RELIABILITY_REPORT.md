# Security and reliability report

Source: `../QA/SECURITY_TEST_RESULTS.md` (2026-11-24 QA pass) and `../QA/MASTER_QA_REPORT.md`.

- **17 of 17** dedicated negative/security checks matched their recorded expectation.
- Covered: valid synthetic login, invalid credentials, tampered/missing token, cross-workspace denial,
  read-only role denial, invalid input, duplicate requests, expired signed URL, unauthorized approval
  and unauthorized document access.
- All identities are synthetic `.invalid` addresses; no real account, token, phone number or provider was used.
- Matrix-level evidence records fail-closed permission guards (`require(...)`, `verify_workspace`) across
  the workspace-scoped route families; cross-workspace access fails closed.
- Full suite regression on 2026-11-25: 1,641 passed, exit 0.

Evidence: `../../artifacts/final_qa_2026-11-24/evidence/qa_security_log.jsonl`,
`../../artifacts/final_qa_2026-11-24/test-results/security-console.txt`.

Limitations: this is local negative testing, not a penetration test, audit or certification. No hosted
deployment, TLS configuration, live provider credential or production hardening was verified.
