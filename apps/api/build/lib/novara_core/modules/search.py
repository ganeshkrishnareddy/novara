"""Universal, workspace-scoped search over the shared CRM tables.

Pure reads only: no new tables, no events, no mutations. Every query filters on
the verified workspace id, so one tenant's rows can never appear in another.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import Principal, require, verify_workspace
from ..models import Company, Contact, Lead, Note, OutreachDraft, Task
from ..permissions import CONTACT_READ

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/search",
    tags=["search"],
)

SEARCH_TYPES = (
    "contact", "lead", "company", "task", "note", "outreach_draft", "ticket",
    "project", "project_item",
)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class SearchResult(BaseModel):
    type: str
    id: str
    title: str
    subtitle: str | None
    url_hint: str

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    results: list[SearchResult]
    counts: dict[str, int]
    total: int


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _pattern(term: str) -> str:
    """Escape LIKE wildcards so user input is matched literally."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("", response_model=SearchResponse)
def universal_search(
    workspace_id: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> SearchResponse:
    verify_workspace(principal, workspace_id)
    term = q.strip()
    if not term:
        raise HTTPException(status_code=422, detail="search query must not be blank")
    pattern = _pattern(term)
    escape = "\\"
    found: list[SearchResult] = []

    contacts = db.execute(
        select(Contact).where(
            Contact.workspace_id == workspace_id,
            or_(
                Contact.email.ilike(pattern, escape=escape),
                Contact.full_name.ilike(pattern, escape=escape),
                Contact.company_name.ilike(pattern, escape=escape),
                Contact.phone.ilike(pattern, escape=escape),
            ),
        ).limit(limit)
    ).scalars().all()
    for row in contacts:
        found.append(
            SearchResult(
                type="contact",
                id=row.id,
                title=row.full_name or row.email,
                subtitle=row.email,
                url_hint=f"/contacts/{row.id}",
            )
        )

    leads = db.execute(
        select(Lead, Contact)
        .join(
            Contact,
            and_(Contact.id == Lead.contact_id, Contact.workspace_id == workspace_id),
        )
        .where(
            Lead.workspace_id == workspace_id,
            or_(
                Lead.source.ilike(pattern, escape=escape),
                Lead.status.ilike(pattern, escape=escape),
                Lead.priority.ilike(pattern, escape=escape),
                Contact.email.ilike(pattern, escape=escape),
                Contact.full_name.ilike(pattern, escape=escape),
            ),
        )
        .limit(limit)
    ).all()
    for lead, contact in leads:
        found.append(
            SearchResult(
                type="lead",
                id=lead.id,
                title=contact.full_name or contact.email,
                subtitle=f"{lead.status} · {lead.source}",
                url_hint=f"/leads/{lead.id}",
            )
        )

    companies = db.execute(
        select(Company).where(
            Company.workspace_id == workspace_id,
            or_(
                Company.name.ilike(pattern, escape=escape),
                Company.industry.ilike(pattern, escape=escape),
                Company.website.ilike(pattern, escape=escape),
                Company.location.ilike(pattern, escape=escape),
            ),
        ).limit(limit)
    ).scalars().all()
    for row in companies:
        subtitle = " · ".join(
            part for part in (row.industry, row.location, row.website) if part
        )
        found.append(
            SearchResult(
                type="company",
                id=row.id,
                title=row.name,
                subtitle=subtitle or None,
                url_hint=f"/companies/{row.id}",
            )
        )

    tasks = db.execute(
        select(Task).where(
            Task.workspace_id == workspace_id,
            or_(
                Task.title.ilike(pattern, escape=escape),
                Task.description.ilike(pattern, escape=escape),
                Task.status.ilike(pattern, escape=escape),
            ),
        ).limit(limit)
    ).scalars().all()
    for row in tasks:
        found.append(
            SearchResult(
                type="task",
                id=row.id,
                title=row.title,
                subtitle=row.description or row.status,
                url_hint=f"/tasks/{row.id}",
            )
        )

    notes = db.execute(
        select(Note, Contact)
        .join(
            Contact,
            and_(Contact.id == Note.contact_id, Contact.workspace_id == workspace_id),
        )
        .where(
            Note.workspace_id == workspace_id,
            or_(
                Note.body.ilike(pattern, escape=escape),
                Contact.email.ilike(pattern, escape=escape),
                Contact.full_name.ilike(pattern, escape=escape),
            ),
        )
        .limit(limit)
    ).all()
    for note, contact in notes:
        found.append(
            SearchResult(
                type="note",
                id=note.id,
                title=contact.full_name or contact.email,
                subtitle=note.body[:120],
                url_hint=f"/contacts/{note.contact_id}/notes",
            )
        )

    drafts = db.execute(
        select(OutreachDraft).where(
            OutreachDraft.workspace_id == workspace_id,
            or_(
                OutreachDraft.subject.ilike(pattern, escape=escape),
                OutreachDraft.body.ilike(pattern, escape=escape),
                OutreachDraft.status.ilike(pattern, escape=escape),
            ),
        ).limit(limit)
    ).scalars().all()
    for row in drafts:
        found.append(
            SearchResult(
                type="outreach_draft",
                id=row.id,
                title=row.subject,
                subtitle=f"{row.status} · {row.body[:80]}",
                url_hint=f"/outreach-drafts/{row.id}",
            )
        )

    # Tickets (support module)
    try:
        from .support import Ticket as _Ticket
    except Exception:
        _Ticket = None
    if _Ticket is not None:
        tickets = db.execute(
            select(_Ticket).where(
                _Ticket.workspace_id == workspace_id,
                or_(
                    _Ticket.subject.ilike(pattern, escape=escape),
                    _Ticket.body.ilike(pattern, escape=escape),
                    _Ticket.status.ilike(pattern, escape=escape),
                    _Ticket.priority.ilike(pattern, escape=escape),
                ),
            ).limit(limit)
        ).scalars().all()
        for row in tickets:
            found.append(
                SearchResult(
                    type="ticket",
                    id=row.id,
                    title=row.subject,
                    subtitle=f"{row.status} · {row.priority}",
                    url_hint=f"/tickets/{row.id}",
                )
            )

    # Projects and work items (Plane family). Imported lazily like tickets so
    # the search module keeps no hard dependency on optional module wiring.
    try:
        from .projects import Project as _Project, ProjectItem as _ProjectItem
    except Exception:
        _Project = None
        _ProjectItem = None
    if _Project is not None and _ProjectItem is not None:
        projects = db.execute(
            select(_Project).where(
                _Project.workspace_id == workspace_id,
                or_(
                    _Project.name.ilike(pattern, escape=escape),
                    _Project.description.ilike(pattern, escape=escape),
                ),
            ).limit(limit)
        ).scalars().all()
        for row in projects:
            found.append(
                SearchResult(
                    type="project",
                    id=row.id,
                    title=row.name,
                    subtitle=f"{row.status} · project",
                    url_hint=f"/projects/{row.id}",
                )
            )
        items = db.execute(
            select(_ProjectItem, _Project)
            .join(
                _Project,
                and_(
                    _Project.id == _ProjectItem.project_id,
                    _Project.workspace_id == workspace_id,
                ),
            )
            .where(
                _ProjectItem.workspace_id == workspace_id,
                or_(
                    _ProjectItem.title.ilike(pattern, escape=escape),
                    _ProjectItem.status.ilike(pattern, escape=escape),
                ),
            )
            .limit(limit)
        ).all()
        for item, project in items:
            found.append(
                SearchResult(
                    type="project_item",
                    id=item.id,
                    title=item.title,
                    subtitle=f"{item.status} · {project.name}",
                    url_hint=f"/projects/{project.id}/items/{item.id}",
                )
            )

    order = {name: index for index, name in enumerate(SEARCH_TYPES)}
    found.sort(key=lambda item: (order[item.type], item.title.lower(), item.id))
    results = found[:limit]
    counts = {name: 0 for name in SEARCH_TYPES}
    for item in results:
        counts[item.type] += 1
    return SearchResponse(results=results, counts=counts, total=len(results))


@router.post("", response_model=SearchResponse)
def universal_search_post(
    workspace_id: str,
    body: dict,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> SearchResponse:
    # Engine-compatible POST: accept {"q": "...", "limit": N}
    q = (body.get("q") or body.get("query") or "").strip() if isinstance(body, dict) else ""
    limit = 20
    if isinstance(body, dict):
        try:
            limit = int(body.get("limit", 20))
        except (TypeError, ValueError):
            limit = 20
    limit = max(1, min(100, limit))
    if not q:
        raise HTTPException(status_code=422, detail="search query must not be blank")
    # delegate by calling the GET implementation logic via a shared helper
    return universal_search(workspace_id=workspace_id, q=q, limit=limit, principal=principal, db=db)


@router.get("/suggest")
def suggest(
    workspace_id: str,
    q: str = Query(..., min_length=1),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[str]:
    verify_workspace(principal, workspace_id)
    pattern = f"{q.strip()}%"
    suggestions: set[str] = set()
    from ..models import Contact, Company, Task

    for row in db.execute(
        select(Contact.full_name).where(Contact.workspace_id == workspace_id, Contact.full_name.ilike(pattern)).limit(10)
    ).scalars().all():
        if row:
            suggestions.add(row)
    for row in db.execute(
        select(Company.name).where(Company.workspace_id == workspace_id, Company.name.ilike(pattern)).limit(10)
    ).scalars().all():
        if row:
            suggestions.add(row)
    for row in db.execute(
        select(Task.title).where(Task.workspace_id == workspace_id, Task.title.ilike(pattern)).limit(10)
    ).scalars().all():
        if row:
            suggestions.add(row)
    return sorted(suggestions)[:20]


@router.get("/facets")
def facets(
    workspace_id: str,
    q: str = Query(default=""),
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    # counts by type across all searchable records
    from ..models import Contact, Company, Lead, Task, Note, OutreachDraft
    from .support import Ticket
    from .projects import Project, ProjectItem

    counts = {}
    counts["contact"] = db.execute(select(func.count()).select_from(Contact).where(Contact.workspace_id == workspace_id)).scalar() or 0
    counts["company"] = db.execute(select(func.count()).select_from(Company).where(Company.workspace_id == workspace_id)).scalar() or 0
    counts["lead"] = db.execute(select(func.count()).select_from(Lead).where(Lead.workspace_id == workspace_id)).scalar() or 0
    counts["task"] = db.execute(select(func.count()).select_from(Task).where(Task.workspace_id == workspace_id)).scalar() or 0
    counts["note"] = db.execute(select(func.count()).select_from(Note).where(Note.workspace_id == workspace_id)).scalar() or 0
    counts["outreach_draft"] = db.execute(select(func.count()).select_from(OutreachDraft).where(OutreachDraft.workspace_id == workspace_id)).scalar() or 0
    counts["ticket"] = db.execute(select(func.count()).select_from(Ticket).where(Ticket.workspace_id == workspace_id)).scalar() or 0
    counts["project"] = db.execute(select(func.count()).select_from(Project).where(Project.workspace_id == workspace_id)).scalar() or 0
    counts["project_item"] = db.execute(
        select(func.count()).select_from(ProjectItem).where(ProjectItem.workspace_id == workspace_id)
    ).scalar() or 0
    return {"workspace_id": workspace_id, "counts": counts}



