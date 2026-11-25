# Database and deployment report

Timestamp: 2026-11-25 11:40 IST.

## Database — verified locally
- Single authoritative Alembic head: `e0f1a2b3c4d5` (`python -m alembic heads` from `apps/api`).
- Fresh isolated QA database created and exercised at that head; migration check exited 0.
- Workspace scoping and persisted create/list behaviour observed in the 2026-11-24 QA pass.
- Evidence: `../../artifacts/final_qa_2026-11-24/test-results/migration-check.txt`,
  `../QA/MASTER_QA_REPORT.md`.

## Deployment — blocked, not verified
- Marketing site committed (`f1dcfefe162faac644e974f075a411eb0975f4cb`) and pushed to `main`.
- Pages workflow run `45556726447`: build job **success** (including `python scripts/validate_site.py`),
  deploy job **failure**.
- GitHub Pages is **not enabled** for the repository (`GET /repos/.../pages` returned 404); an
  authenticated attempt to enable it also returned 404, so this is an owner-side repository setting.
- No claim is made that the site is live. No backend, container, PostgreSQL or hosted deployment was performed.

See `MARKETING_WEBSITE_LAUNCH_REPORT.md` and `RELEASE_BLOCKERS.md`.
