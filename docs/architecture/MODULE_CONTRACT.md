# NOVARA module contract (v1)

Every capability module is a real, database-backed API surface inside the one
NOVARA application. There are no separate apps, no embedded third-party sites,
no mock endpoints and no client-supplied identity.

## Read first

- `apps/api/novara_core/modules/feedback.py` — the reference module. Copy its
  structure exactly.
- `apps/api/novara_core/dependencies.py` — `Principal`, `require()`, `verify_workspace()`.
- `apps/api/novara_core/events.py` — `publish_event()`, `register_event_types()`.
- `apps/api/novara_core/models.py` — shared `Workspace`, `Contact`, `Lead`, `Task`,
  `Event`, `User`, `WorkspaceMember` tables (read-only; do not edit).
- `apps/api/novara_core/permissions.py` — permission constants (read-only).
- `apps/api/novara_core/database.py` — `Base`, `get_db` (read-only).

## File ownership — strict

Each agent owns ONLY the files listed in its assignment. Shared files are owned
by the orchestrator and MUST NOT be edited by agents:

`main.py`, `models.py`, `schemas.py`, `permissions.py`, `security.py`,
`dependencies.py`, `events.py`, `database.py`, `workflow.py`,
`modules/__init__.py`, `modules/feedback.py`, `tests/conftest.py`,
`pyproject.toml`, any doc under `docs/`.

To add an event name, call `register_event_types("x.created", ...)` at the top
of your own module. Never edit `events.py`.

## Required module shape

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import <RESOURCE>_READ, <RESOURCE>_WRITE

EVENT_CREATED = "area.created"
register_event_types(EVENT_CREATED)

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/<area>", tags=["<area>"])
```

Rules:

1. Define module-owned SQLAlchemy tables in your own file, importing `Base`
   from `..database`. Every tenant table has `id`, `workspace_id` with
   `ForeignKey("workspaces.id")` and an index on `workspace_id`.
2. Every endpoint signature includes `workspace_id: str`, a `require(...)`
   dependency and `db: Session = Depends(get_db)`. Call
   `verify_workspace(principal, workspace_id)` as the first statement.
3. Every mutation calls `publish_event(db, workspace_id=..., event_type=...,
   entity_id=..., payload=..., actor_id=principal.user.id)` and then `db.commit()`.
4. Every row returned or updated is filtered by both its id AND `workspace_id`.
   A cross-workspace id must return 404, never another tenant's data.
5. Use Pydantic request models with `ConfigDict(extra="forbid")`. Validate
   non-empty names, score ranges, statuses, etc. Return 422/409/404 correctly.
6. Never accept a `user_id` or `workspace_id` from a request body as identity.
7. Never send email, SMS, webhooks or any external message. Outbound delivery
   is intentionally absent until separately authorised.
8. Response models use `model_config = ConfigDict(from_attributes=True)`.
9. Include `created_at` (and `updated_at` where edited) on mutable records.
10. No fake/static demo data. Empty tables return empty lists.

## Permission mapping (use existing constants; do not edit permissions.py)

| Area | Read | Write |
|---|---|---|
| sales (deals/pipeline) | CONTACT_READ | CONTACT_WRITE |
| marketing (campaigns, automation rules) | CONTACT_READ | CONTACT_WRITE |
| support (tickets, messages) | CONTACT_READ | NOTE_WRITE |
| projects (projects, items) | TASK_READ | TASK_WRITE |
| documents (folders, documents) | CONTACT_READ | NOTE_WRITE |
| analytics (metrics, experiments) | EVENT_READ | WORKSPACE_MANAGE |
| search (universal) | CONTACT_READ | — |
| automation builder | TASK_READ | WORKSPACE_MANAGE |
| AI agent center | EVENT_READ | OUTREACH_APPROVE |
| integrations/settings | CONTACT_READ | WORKSPACE_MANAGE |
| feedback (reference, already built) | CONTACT_READ | NOTE_WRITE |

## Testing

Write pytest tests in the exact test files named in your assignment. Use the
existing helpers in `tests/conftest.py`:

```python
from .conftest import auth, bootstrap

def test_x(client):
    tokens = bootstrap(client)
    wid, headers = tokens["workspace_id"], auth(tokens["access_token"])
    ...
```

Do not edit `tests/conftest.py`. Do not mark failed tests as passed. Run:

```
$env:PYTHONPATH='D:\NOVARA\apps\api'; python -m pytest -q 'D:\NOVARA\apps\api\tests'
```

Note: the full suite will only pass once every module file exists, because
`modules/__init__.py` imports all of them. Until then, target your own test file
with `-k` or report the import error honestly.

## Git

Never commit, push, tag, rebase or rewrite history. All changes stay local.
