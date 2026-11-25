# Security and regression report — Campaign 2

Timestamp: 2026-11-25 12:24 IST. HEAD `f1dcfefe162faac644e974f075a411eb0975f4cb`. No application code or test file was changed during this Campaign 2 check.

## Verdict

Local negative-testing and reliability checks are **PASS for the tested local scopes**. This is not a penetration test, security audit, certification, hosted-deployment verification or production-hardening claim.

## Fresh security/reliability batch

Command:

```powershell
cd D:\NOVARA
.\.venv\Scripts\python.exe -m pytest `
  "apps/api/tests/test_security.py" `
  "apps/api/tests/test_isolation.py" `
  "apps/api/tests/test_integrity.py" `
  "apps/api/tests/test_access_governance_p2.py::test_cw130_custom_role_cross_workspace_denied" `
  "apps/api/tests/test_access_governance_p2.py::test_pl125_permission_scheme_assign_propagate_audit" `
  "apps/api/tests/test_access_governance_p2.py::test_nv070_fine_grained_notification_permissions" `
  -v --tb=short --junitxml=docs\FINAL_RELEASE_QA\CAMPAIGN2\evidence\security_reliability_20261125.xml
```

Observed: **17 passed, 1 warning, exit 0 in 14.21s**. The warning is the known Starlette/httpx `TestClient` deprecation notice. Evidence: `CAMPAIGN2/evidence/security_reliability_20261125.txt` and `...xml`.

Coverage observed in this batch:

- Security headers on success and error responses.
- Validation errors do not reflect submitted values.
- Authentication rate limiter returns 429 with headers.
- CORS allowlist defaults to same-origin.
- Cross-workspace contact, event, member and password-hash isolation.
- Cross-workspace membership is not trusted.
- Repeated submission idempotency and distinct submission isolation.
- Transaction rollback on constraint failure and failed handler.
- Approval never sends an external message.
- Custom-role cross-workspace denial.
- Permission-scheme assignment propagation and audit.
- Fine-grained notification permissions.

All records are synthetic and local; no real account, token, provider, phone number or payment was used.

## Earlier dedicated negative pass

`docs/QA/SECURITY_TEST_RESULTS.md` and `artifacts/final_qa_2026-11-24/evidence/qa_security_log.jsonl` record **17/17** dedicated checks matching expectations (valid synthetic login, invalid credentials, tampered/missing token, cross-workspace denial, read-only denial, invalid input, duplicates, expired signed URL, unauthorized approval and unauthorized document access).

## Full regression baseline

The authoritative full backend suite at the campaign baseline is:

- `1641 passed, 4 warnings in 1267.47s`, exit 0.
- Evidence: `artifacts/final_qa_2026-11-24/test-results/regression-20261125-final.txt`.
- Reported in `REGRESSION_TEST_REPORT.md`.

No application or test code has been repaired in this report's scope. If any repair is made during feature closure, the full suite must be rerun before final acceptance; a targeted pass is not a substitute.

## Limits

- No formal penetration test, audit or certification.
- No hosted deployment, TLS production configuration or WAF review.
- No live provider credentials or outbound delivery.
- No non-Chromium browser security verification.
- These passes do not convert `BLOCKED_EXTERNAL` or `NOT_TESTED` feature rows into accepted features.
