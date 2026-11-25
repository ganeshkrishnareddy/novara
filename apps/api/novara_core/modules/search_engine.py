"""Clean-room local search engine with index, document and settings APIs.

This is an original NOVARA implementation of the documented Meilisearch
acceptance criteria. It runs entirely inside the workspace database: no
Meilisearch server, embedding provider or external service is contacted, and no
upstream source is copied. Every index and document is workspace-scoped and
every mutation is audited through the shared event bus.

Feature IDs closed here (evidence: apps/api/tests/test_search_engine_p2.py):
MS-004, MS-007, MS-008, MS-012, MS-013, MS-016, MS-017, MS-018, MS-019,
MS-020, MS-021, MS-023, MS-024, MS-025, MS-026, MS-027, MS-029, MS-030,
MS-031, MS-032, MS-033, MS-034, MS-035, MS-040, MS-041, MS-043, MS-044,
MS-045, MS-046, MS-047, MS-057, MS-061.
"""

from __future__ import annotations

import math
import re
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import JSON, DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE

INDEX_CHANGED = "search.index_changed"
DOCUMENT_CHANGED = "search.document_changed"
SETTINGS_CHANGED = "search.settings_changed"
register_event_types(INDEX_CHANGED, DOCUMENT_CHANGED, SETTINGS_CHANGED)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/search-engine",
    tags=["search-engine"],
)

ENGINE_VERSION = "novara-search/1.0.0"
DEFAULT_SETTINGS = {
    "synonyms": {},
    "stop_words": [],
    "separators": [],
    "non_separators": [],
    "dictionary": [],
    "ranking_rules": ["words", "typo", "proximity", "attribute", "exactness"],
    "searchable_attributes": [],       # empty = all non-_ fields
    "filterable_attributes": [],
    "sortable_attributes": [],
    "displayed_attributes": [],
    "distinct_attribute": None,
    "matching_strategy": "last",
    "typo_tolerance": {"enabled": True, "max_distance": 1, "min_word_length": 4},
    "locale": "en",
    "search_cutoff_ms": 0,              # 0 = no cutoff
    "crop_length": 200,
    "crop_marker": "...",
    "highlight_tags": ["<em>", "</em>"],
    "features": {"facet_search": True, "geo_search": True, "phrase_search": True},
}
EXPERIMENTAL_FEATURES = ("facet_search", "geo_search", "phrase_search", "vector_search")


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

class SearchIndex(Base):
    __tablename__ = "search_indexes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    primary_key: Mapped[str] = mapped_column(String(80), default="id")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


class SearchDocument(Base):
    __tablename__ = "search_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    index_id: Mapped[str] = mapped_column(ForeignKey("search_indexes.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(160), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class IndexCreate(BaseModel):
    name: str
    primary_key: str = "id"

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("index name is required")
        return v


class DocumentsIn(BaseModel):
    documents: list[dict]

    model_config = ConfigDict(extra="forbid")

    @field_validator("documents")
    @classmethod
    def _docs(cls, v):
        if not v:
            raise ValueError("at least one document is required")
        return v


class PartialDocument(BaseModel):
    data: dict

    model_config = ConfigDict(extra="forbid")


class SettingsPatch(BaseModel):
    synonyms: dict | None = None
    stop_words: list | None = None
    separators: list | None = None
    non_separators: list | None = None
    dictionary: list | None = None
    ranking_rules: list | None = None
    searchable_attributes: list | None = None
    filterable_attributes: list | None = None
    sortable_attributes: list | None = None
    distinct_attribute: str | None = None
    matching_strategy: str | None = None
    typo_tolerance: dict | None = None
    locale: str | None = None
    search_cutoff_ms: int | None = None
    crop_length: int | None = None
    features: dict | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("matching_strategy")
    @classmethod
    def _strategy(cls, v):
        if v is not None and v not in ("last", "all", "any"):
            raise ValueError("matching_strategy must be last, all or any")
        return v

    @field_validator("search_cutoff_ms", "crop_length")
    @classmethod
    def _nonneg(cls, v):
        if v is not None and v < 0:
            raise ValueError("value cannot be negative")
        return v


class SearchIn(BaseModel):
    q: str = ""
    limit: int = 20
    offset: int = 0
    attributes_to_retrieve: list[str] | None = None
    searchable_attributes: list[str] | None = None
    filter: dict | None = None
    facet_query: dict | None = None   # {"attribute": "prefix"}
    sort_by: str | None = None        # "field:asc" or "_geoDistance(lat,lng):asc"
    geo_lat: float | None = None
    geo_lng: float | None = None
    geo_radius: float | None = None   # metres

    model_config = ConfigDict(extra="forbid")

    @field_validator("limit")
    @classmethod
    def _limit(cls, v):
        if not 1 <= v <= 200:
            raise ValueError("limit must be 1..200")
        return v


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _index_or_404(db: Session, workspace_id: str, name: str) -> SearchIndex:
    row = db.execute(
        select(SearchIndex).where(SearchIndex.workspace_id == workspace_id,
                                  SearchIndex.name == name)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="index not found")
    return row


def _settings(index: SearchIndex) -> dict:
    result = dict(DEFAULT_SETTINGS)
    result.update(index.settings or {})
    return result


def _apply_dictionary(text: str, settings: dict) -> str:
    for phrase in settings.get("dictionary") or []:
        token = re.sub(r"[^\w]+", "_", phrase).strip("_").lower()
        text = re.sub(re.escape(phrase), token, text, flags=re.I)
    return text


def _tokenize(text: str, settings: dict) -> list[str]:
    text = _apply_dictionary(str(text), settings)
    seps = set(settings.get("separators") or [])
    non_seps = set(settings.get("non_separators") or [])
    stop = {str(w).lower() for w in settings.get("stop_words") or []}
    tokens: list[str] = []
    current: list[str] = []
    for ch in text:
        if ch.isspace() or ch in seps:
            if current:
                tokens.append("".join(current))
                current = []
        elif ch.isalnum() or ch in non_seps or ch == "_":
            current.append(ch.lower())
        # other punctuation is discarded
    if current:
        tokens.append("".join(current))
    return [t for t in tokens if t and t not in stop]


def _expand_synonyms(tokens: list[str], synonyms: dict) -> list[str]:
    """Expand single and multi-word synonym keys into equivalent terms."""
    expanded = list(tokens)
    for key, values in (synonyms or {}).items():
        key_tokens = _tokenize(key, {})
        width = len(key_tokens)
        if not width:
            continue
        for i in range(len(tokens) - width + 1):
            if tokens[i:i + width] == key_tokens:
                for value in values:
                    expanded.extend(_tokenize(str(value), {}))
    return list(dict.fromkeys(expanded))


def _levenshtein(a: str, b: str, max_distance: int) -> int:
    """Bounded Levenshtein distance; returns max_distance+1 when over budget."""
    if abs(len(a) - len(b)) > max_distance:
        return max_distance + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > max_distance:
            return max_distance + 1
        prev = cur
    return prev[len(b)]


def _synonym_groups(tokens: list[str], synonyms: dict) -> list[list[str]]:
    """Group query tokens with their synonyms: each group needs one match."""
    groups: list[list[str]] = []
    i = 0
    while i < len(tokens):
        matched = False
        for key, values in (synonyms or {}).items():
            key_tokens = _tokenize(key, {})
            if key_tokens and tokens[i:i + len(key_tokens)] == key_tokens:
                alternatives = list(key_tokens)
                for value in values:
                    alternatives.extend(_tokenize(str(value), {}))
                groups.append(list(dict.fromkeys(alternatives)))
                i += len(key_tokens)
                matched = True
                break
        if not matched:
            groups.append([tokens[i]])
            i += 1
    return groups


def _parse_query(q: str, settings: dict) -> dict:
    """Extract phrases, exclusions, placeholders and synonym token groups."""
    phrases = re.findall(r'"([^"]+)"', q)
    rest = re.sub(r'"[^"]*"', " ", q)
    excluded = re.findall(r'(?:^|\s)-(\S+)', rest)
    rest = re.sub(r'(?:^|\s)-\S+', " ", rest)
    placeholders = re.findall(r'([^\W_]+)\*', rest)
    rest = re.sub(r'[^\W_]+\*', ' ', rest)
    match_all = q.strip() == "*"
    tokens = _tokenize(rest, settings)
    plain = _synonym_groups(tokens, settings.get("synonyms"))
    phrases = [p.lower().strip() for p in phrases if p.strip()]
    excluded = [e.lower() for e in excluded]
    return {"plain": plain, "phrases": phrases, "excluded": excluded,
            "placeholders": placeholders, "match_all": match_all, "raw": q.strip()}


def _field_texts(data: dict, settings: dict) -> dict[str, str]:
    configured = settings.get("searchable_attributes") or []
    fields = {}
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if configured and key not in configured:
            continue
        if isinstance(value, (str, int, float)):
            fields[key] = str(value)
        elif isinstance(value, (list, dict)):
            fields[key] = " ".join(str(v) for v in _flatten(value))
    # Keep configured order for attribute ranking.
    if configured:
        return {k: fields[k] for k in configured if k in fields}
    return fields


def _flatten(value) -> list:
    if isinstance(value, dict):
        out = []
        for v in value.values():
            out.extend(_flatten(v))
        return out
    if isinstance(value, list):
        out = []
        for v in value:
            out.extend(_flatten(v))
        return out
    return [value]


def _find_positions(haystack: str, token: str, settings: dict) -> list[dict]:
    """Return character positions of a term, with bounded typo tolerance."""
    haystack = _apply_dictionary(str(haystack), settings)
    extra = "".join(re.escape(c) for c in (settings.get("non_separators") or []))
    words = list(re.finditer(rf"[\w{extra}]+", haystack, flags=re.UNICODE))
    tolerance = settings.get("typo_tolerance") or {}
    max_dist = int(tolerance.get("max_distance", 1)) if tolerance.get("enabled", True) else 0
    min_len = int(tolerance.get("min_word_length", 4))
    results = []
    for match in words:
        word = match.group(0).lower()
        dist = 0
        if word == token:
            dist = 0
        elif token.endswith("*"):
            continue
        elif len(word) >= min_len and len(token) >= min_len and max_dist > 0:
            dist = _levenshtein(word, token, max_dist)
            if dist > max_dist:
                continue
        else:
            continue
        results.append({"start": match.start(), "length": match.end() - match.start(),
                        "distance": dist, "word": word})
    return results


def _match_document(data: dict, parsed: dict, settings: dict) -> dict | None:
    fields = _field_texts(data, settings)
    strategy = settings.get("matching_strategy", "last")
    matches: dict[str, list[dict]] = {}
    total_typos = 0
    proximity_distances = []
    matched_any_exclusion = False

    for token in parsed["excluded"]:
        for text in fields.values():
            if _find_positions(text, token.lower(), {"typo_tolerance": {"enabled": False}}):
                matched_any_exclusion = True
    if matched_any_exclusion:
        return None

    # Placeholder search: prefix matching.
    for prefix in parsed["placeholders"]:
        found = False
        for text in fields.values():
            for match in re.finditer(r"[^\W_]+", text, flags=re.UNICODE):
                if match.group(0).lower().startswith(prefix):
                    found = True
                    matches.setdefault("__placeholder__", []).append(
                        {"start": match.start(), "length": len(match.group(0)), "distance": 0,
                         "word": match.group(0).lower()})
        if not found:
            return None

    # Phrase search: consecutive words in the same field.
    for phrase in parsed["phrases"]:
        ptokens = _tokenize(phrase, settings)
        if not ptokens:
            continue
        found = False
        for text in fields.values():
            words = list(re.finditer(r"[^\W_]+", text, flags=re.UNICODE))
            for i in range(len(words) - len(ptokens) + 1):
                if all(words[i + k].group(0).lower() == ptokens[k] for k in range(len(ptokens))):
                    found = True
                    matches.setdefault("__phrase__", []).append(
                        {"start": words[i].start(),
                         "length": words[i + len(ptokens) - 1].end() - words[i].start(),
                         "distance": 0, "word": phrase})
                    break
            if found:
                break
        if not found:
            return None

    if parsed["match_all"]:
        for name, text in fields.items():
            words = list(re.finditer(r"[\w]+", text, flags=re.UNICODE))
            if words:
                matches[name] = [{"start": words[0].start(),
                                  "length": words[0].end() - words[0].start(),
                                  "distance": 0, "word": words[0].group(0).lower()}]

    for group in parsed["plain"]:
        group_matches: dict[str, list[dict]] = {}
        for token in group:
            for name, text in fields.items():
                found = _find_positions(text, token, settings)
                if found:
                    group_matches.setdefault(name, []).extend(found)
                    matches.setdefault(name, []).extend(found)
                    total_typos += min(p["distance"] for p in found)
        if not group_matches:
            if strategy in ("last", "all"):
                return None
            continue
        if strategy == "all" and len(group_matches) < len(fields):
            return None
        positions = [p["start"] for group_items in group_matches.values() for p in group_items]
        if len(positions) > 1:
            proximity_distances.append(max(positions) - min(positions))

    if not matches:
        return None
    proximity = min(proximity_distances) if proximity_distances else 0
    first_field = next(iter(matches), "")
    exactness = 1.0 if any(
        text.strip().lower() == parsed["raw"].lower() for text in fields.values()
    ) else 0.0
    attribute_rank = 0
    configured = settings.get("searchable_attributes") or list(fields)
    if first_field in configured:
        attribute_rank = len(configured) - configured.index(first_field)

    return {"fields": fields, "matches": matches, "typos": total_typos,
            "proximity": proximity, "exactness": exactness,
            "attribute_rank": attribute_rank, "proximity_distances": proximity_distances}


def _score(match: dict, settings: dict) -> tuple[float, dict]:
    weights = {"words": 10.0, "typo": -2.0, "proximity": -0.05,
               "attribute": 1.0, "exactness": 5.0, "sort": 0.5}
    details: dict[str, float] = {}
    total = 0.0
    for rule in settings.get("ranking_rules") or DEFAULT_SETTINGS["ranking_rules"]:
        if rule == "words":
            value = float(len(match["matches"]))
        elif rule == "typo":
            value = float(-match["typos"])
        elif rule == "proximity":
            value = float(-match["proximity"])
        elif rule == "attribute":
            value = float(match["attribute_rank"])
        elif rule == "exactness":
            value = match["exactness"]
        else:
            value = 0.0
        details[rule] = value
        total += value * weights.get(rule, 0.0)
    details["rankingScore"] = round(total, 4)
    return round(total, 4), details


def _highlight_and_crop(text: str, match: dict, settings: dict) -> str:
    open_tag, close_tag = settings.get("highlight_tags", ["<em>", "</em>"])
    tokens = {p["word"] for group in match["matches"].values() for p in group}
    result = text
    for token in sorted(tokens, key=len, reverse=True):
        if token and token != "__phrase__":
            result = re.sub(re.escape(token), open_tag + token + close_tag, result,
                            flags=re.IGNORECASE)
    crop = int(settings.get("crop_length", 200))
    if crop and len(result) > crop:
        marker = settings.get("crop_marker", "...")
        first = min([p["start"] for group in match["matches"].values() for p in group] or [0])
        start = max(0, first - crop // 2)
        result = marker + result[start:start + crop] + marker
    return result


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _doc_distance(doc: dict, lat: float, lng: float) -> float | None:
    geo = doc.get("_geo")
    if not isinstance(geo, dict) or "lat" not in geo or "lng" not in geo:
        return None
    return _haversine(lat, lng, float(geo["lat"]), float(geo["lng"]))


# --------------------------------------------------------------------------
# Index management  (MS-041, MS-043, MS-057, MS-061)
# --------------------------------------------------------------------------

@router.post("/indexes", status_code=status.HTTP_201_CREATED)
def create_index(
    workspace_id: str,
    body: IndexCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    if db.execute(select(SearchIndex.id).where(
        SearchIndex.workspace_id == workspace_id, SearchIndex.name == body.name
    )).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="index already exists")
    index = SearchIndex(id=new_id(), workspace_id=workspace_id, name=body.name,
                        primary_key=body.primary_key, settings=dict(DEFAULT_SETTINGS))
    db.add(index)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=INDEX_CHANGED,
                  entity_id=index.id, payload={"name": body.name, "action": "create"},
                  actor_id=principal.user.id)
    db.commit()
    return {"name": index.name, "primaryKey": index.primary_key, "createdAt": index.created_at}


@router.get("/indexes")
def list_indexes(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(SearchIndex).where(SearchIndex.workspace_id == workspace_id)
        .order_by(SearchIndex.created_at)
    ).scalars().all()
    return [{"name": r.name, "primaryKey": r.primary_key, "createdAt": r.created_at} for r in rows]


@router.get("/indexes/{name}/fields")
def index_fields(
    workspace_id: str,
    name: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    index = _index_or_404(db, workspace_id, name)
    docs = db.execute(
        select(SearchDocument).where(SearchDocument.workspace_id == workspace_id,
                                     SearchDocument.index_id == index.id)
    ).scalars().all()
    fields: dict[str, set[str]] = {}
    for doc in docs:
        for key, value in (doc.data or {}).items():
            fields.setdefault(key, set()).add(type(value).__name__)
    return [{"name": key, "types": sorted(types)} for key, types in sorted(fields.items())]


@router.delete("/indexes/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_index(
    workspace_id: str,
    name: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    index = _index_or_404(db, workspace_id, name)
    from sqlalchemy import delete as sa_delete
    db.execute(sa_delete(SearchDocument).where(
        SearchDocument.workspace_id == workspace_id, SearchDocument.index_id == index.id))
    db.delete(index)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=INDEX_CHANGED,
                  entity_id=index.id, payload={"name": name, "action": "delete"},
                  actor_id=principal.user.id)
    db.commit()
    return None


@router.get("/version")
def version(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    return {"version": ENGINE_VERSION, "commit": "local-cleanroom", "buildDate": "2026-11-23"}


@router.get("/features")
def features(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    return {"features": list(EXPERIMENTAL_FEATURES), "enabled": {
        f: True for f in EXPERIMENTAL_FEATURES}}


# --------------------------------------------------------------------------
# Documents  (MS-044, MS-045, MS-046, MS-047)
# --------------------------------------------------------------------------

def _doc_id(index: SearchIndex, data: dict, explicit: str | None = None) -> str:
    key = index.primary_key
    value = explicit if explicit is not None else data.get(key)
    if value in (None, ""):
        raise HTTPException(status_code=422, detail=f"document missing primary key '{key}'")
    return str(value)


@router.post("/indexes/{name}/documents", status_code=status.HTTP_202_ACCEPTED)
def add_documents(
    workspace_id: str,
    name: str,
    body: DocumentsIn,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    index = _index_or_404(db, workspace_id, name)
    seen = set()
    for doc in body.documents:
        did = _doc_id(index, doc)
        seen.add(did)
        row = db.execute(
            select(SearchDocument).where(
                SearchDocument.workspace_id == workspace_id,
                SearchDocument.index_id == index.id,
                SearchDocument.document_id == did,
            )
        ).scalar_one_or_none()
        if row is None:
            row = SearchDocument(id=new_id(), workspace_id=workspace_id,
                                 index_id=index.id, document_id=did)
            db.add(row)
        row.data = doc
        row.updated_at = now()
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=DOCUMENT_CHANGED,
                  entity_id=index.id, payload={"action": "add_or_replace", "count": len(seen)},
                  actor_id=principal.user.id)
    db.commit()
    return {"taskUid": new_id(), "status": "enqueued", "documentCount": len(seen)}


@router.patch("/indexes/{name}/documents/{document_id}", status_code=status.HTTP_202_ACCEPTED)
def update_document(
    workspace_id: str,
    name: str,
    document_id: str,
    body: PartialDocument,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    index = _index_or_404(db, workspace_id, name)
    row = db.execute(
        select(SearchDocument).where(
            SearchDocument.workspace_id == workspace_id,
            SearchDocument.index_id == index.id,
            SearchDocument.document_id == document_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    data = dict(row.data or {})
    data.update(body.data)
    data[index.primary_key] = document_id
    row.data = data
    row.updated_at = now()
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=DOCUMENT_CHANGED,
                  entity_id=row.id, payload={"action": "partial_update"},
                  actor_id=principal.user.id)
    db.commit()
    return {"documentId": document_id, "data": data}


@router.delete("/indexes/{name}/documents/{document_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_document(
    workspace_id: str,
    name: str,
    document_id: str,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    index = _index_or_404(db, workspace_id, name)
    row = db.execute(
        select(SearchDocument).where(
            SearchDocument.workspace_id == workspace_id,
            SearchDocument.index_id == index.id,
            SearchDocument.document_id == document_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    db.delete(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=DOCUMENT_CHANGED,
                  entity_id=row.id, payload={"action": "delete"},
                  actor_id=principal.user.id)
    db.commit()
    return {"taskUid": new_id(), "status": "enqueued"}


@router.get("/indexes/{name}/documents")
def list_documents(
    workspace_id: str,
    name: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    index = _index_or_404(db, workspace_id, name)
    rows = db.execute(
        select(SearchDocument).where(SearchDocument.workspace_id == workspace_id,
                                     SearchDocument.index_id == index.id)
        .order_by(SearchDocument.document_id)
    ).scalars().all()
    return [{"documentId": r.document_id, "data": r.data} for r in rows]


# --------------------------------------------------------------------------
# Settings  (MS-016..021, MS-030, MS-032, MS-034, MS-040)
# --------------------------------------------------------------------------

@router.get("/indexes/{name}/settings")
def get_settings(
    workspace_id: str,
    name: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    return _settings(_index_or_404(db, workspace_id, name))


@router.patch("/indexes/{name}/settings")
def patch_settings(
    workspace_id: str,
    name: str,
    body: SettingsPatch,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    index = _index_or_404(db, workspace_id, name)
    current = _settings(index)
    updates = body.model_dump(exclude_none=True)
    current.update(updates)
    index.settings = current
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=SETTINGS_CHANGED,
                  entity_id=index.id, payload={"keys": sorted(updates)},
                  actor_id=principal.user.id)
    db.commit()
    return current


# --------------------------------------------------------------------------
# Search  (MS-004, MS-007, MS-008, MS-012, MS-013, MS-023..027, MS-029, MS-031, MS-033, MS-035)
# --------------------------------------------------------------------------

@router.post("/indexes/{name}/search")
def search(
    workspace_id: str,
    name: str,
    body: SearchIn,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
):
    verify_workspace(principal, workspace_id)
    index = _index_or_404(db, workspace_id, name)
    settings = _settings(index)
    if body.searchable_attributes is not None:
        settings["searchable_attributes"] = body.searchable_attributes
    if not body.q.strip():
        raise HTTPException(status_code=422, detail="search query must not be empty")
    parsed = _parse_query(body.q, settings)
    docs = db.execute(
        select(SearchDocument).where(SearchDocument.workspace_id == workspace_id,
                                     SearchDocument.index_id == index.id)
    ).scalars().all()

    started = time.perf_counter()
    cutoff_ms = int(settings.get("search_cutoff_ms", 0) or 0)
    scored = []
    for doc in docs:
        if cutoff_ms and (time.perf_counter() - started) * 1000 > cutoff_ms:
            break
        data = dict(doc.data or {})
        if body.filter:
            if any(data.get(k) != v for k, v in body.filter.items()):
                continue
        if body.geo_lat is not None and body.geo_lng is not None:
            distance = _doc_distance(data, body.geo_lat, body.geo_lng)
            if body.geo_radius is not None and (distance is None or distance > body.geo_radius):
                continue
            if distance is not None:
                data["_geoDistance"] = round(distance, 2)
        match = _match_document(data, parsed, settings)
        if match is None:
            continue
        score, details = _score(match, settings)
        scored.append({"documentId": doc.document_id, "data": data,
                       "match": match, "score": score, "details": details})

    # Geo distance sorting via sort_by=_geoDistance(lat,lng):asc|desc
    if body.sort_by and body.sort_by.startswith("_geoDistance("):
        m = re.match(r"_geoDistance\(([-\d.]+),([-\d.]+)\):(asc|desc)", body.sort_by)
        if m:
            lat, lng, direction = float(m.group(1)), float(m.group(2)), m.group(3)
            for h in scored:
                d = _doc_distance(h["data"], lat, lng)
                h["data"]["_sortDistance"] = d if d is not None else float("inf")
            scored.sort(key=lambda h: h["data"]["_sortDistance"],
                        reverse=(direction == "desc"))
    elif body.sort_by and ":" in body.sort_by:
        field, direction = body.sort_by.rsplit(":", 1)
        if field in (settings.get("sortable_attributes") or []):
            scored.sort(key=lambda h: str(h["data"].get(field, "")),
                        reverse=(direction == "desc"))
    else:
        scored.sort(key=lambda h: h["score"], reverse=True)

    # Distinct attribute: keep the best hit per value.
    distinct = settings.get("distinct_attribute")
    if distinct:
        kept, seen = [], set()
        for h in scored:
            value = str(h["data"].get(distinct))
            if value not in seen:
                seen.add(value)
                kept.append(h)
        scored = kept

    total = len(scored)
    page = scored[body.offset:body.offset + body.limit]
    hits = []
    for h in page:
        data = h["data"]
        data.pop("_sortDistance", None)
        if body.attributes_to_retrieve:
            data = {k: data[k] for k in body.attributes_to_retrieve if k in data}
        positions = {k: [{"start": p["start"], "length": p["length"]} for p in v]
                     for k, v in h["match"]["matches"].items()}
        formatted = {}
        for name, text in h["match"]["fields"].items():
            if any(p["word"] for p in h["match"]["matches"].get(name, [])) or \
                    "__phrase__" in h["match"]["matches"]:
                formatted[name] = _highlight_and_crop(text, h["match"], settings)
        hits.append({
            "documentId": h["documentId"], "data": data,
            "rankingScore": h["score"], "scoreDetails": h["details"],
            "formatted": formatted, "matchesPosition": positions,
        })

    facets = {}
    filterable = settings.get("filterable_attributes") or []
    if filterable:
        for attribute in filterable:
            counts: dict[str, int] = {}
            for h in scored:
                value = h["data"].get(attribute)
                for item in (value if isinstance(value, list) else [value]):
                    if item is not None:
                        counts[str(item)] = counts.get(str(item), 0) + 1
            facets[attribute] = dict(sorted(counts.items()))

    facet_stats = {}
    if body.facet_query and settings.get("features", {}).get("facet_search", True):
        for attribute, prefix in body.facet_query.items():
            facet_stats[attribute] = [v for v in facets.get(attribute, {})
                                      if v.lower().startswith(str(prefix).lower())]

    return {"hits": hits, "totalHits": total, "offset": body.offset, "limit": body.limit,
            "facets": facets, "facetSearch": facet_stats,
            "processingTimeMs": round((time.perf_counter() - started) * 1000, 3)}
