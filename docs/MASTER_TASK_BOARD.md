# Master task board

Living board. Status values: TODO / IN PROGRESS / DONE / BLOCKED. Evidence means a file or test result that can be checked.

| Task ID | Description | Owner | Status | Dependencies | Branch / workspace | Test evidence | Review |
|---|---|---|---|---|---|---|---|
| T-001 | Inspect environment and create project workspace | MausBot | DONE | — | project workspace | Directory + `docs/PROJECT_STATUS.md` | — |
| T-002 | Verify ten source repositories and record metadata | MausBot | DONE | T-001 | `docs/research/REPOSITORY_AUDIT.md` | GitHub API, 2026-11-22 | — |
| T-003 | Deep audit: Formbricks, Meilisearch, GrowthBook | Nova | DONE | T-002 | `docs/research/repos/01-formbricks-meilisearch-growthbook.md` | 51 KB, 15 sections x 3 repos, placeholders verified removed | Pending |
| T-004 | Deep audit: Papermark, Chatwoot, Novu | Tango | DONE | T-002 | `docs/research/repos/02-papermark-chatwoot-novu.md` | 30 KB, 15 sections x 3 repos, source URLs | Pending |
| T-005 | Deep audit: Plane, Mautic | Atlas | DONE | T-002 | `docs/research/repos/03-plane-mautic.md` | 28 KB, 15 sections x 2 repos | Pending |
| T-006 | Deep audit: Marketing Skills, Sellbird | Panko | DONE | T-002 | `docs/research/repos/04-marketingskills-sellbird.md` | 24 KB, 15 sections x 2 repos | Pending |
| T-007 | Read actual license texts and complete compliance decision | Shield | DONE | T-002 | `docs/research/LICENSE_COMPLIANCE.md`, `THIRD_PARTY_NOTICES.md` | Commit `d6ee10d` | Pending |
| T-008 | Architecture and shared contracts (API, DB, events, permissions) | Unassigned | TODO | T-003..T-007 | `docs/architecture/` | — | — |
| T-009 | Feature and acceptance matrix | Unassigned | TODO | T-003..T-007 | `docs/research/FEATURE_MATRIX.md` | — | — |
| T-010 | Build environment: install Docker and validate local stack | Owner | BLOCKED (B-01) | — | — | — | — |
| T-011 | Create official repository and connect local workspace | Owner / MausBot | DONE | — | `https://github.com/ganeshkrishnareddy/novara`, branch `main` | GitHub API + git remote | — |

Rows will only move to DONE with linked evidence. No task is marked complete on assertion alone.
