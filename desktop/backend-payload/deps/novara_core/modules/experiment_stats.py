"""Experimentation statistics (GrowthBook P2 clean-room cluster).

Clean-room implementation of GB-020 (Bayesian), GB-021 (frequentist), GB-022
(SRM), GB-023 (health checks), GB-029/030/031/032 (metric definitions and
proportion/mean/ratio metrics), GB-038 (power analysis) and GB-042 (multiple
testing corrections) over NOVARA's shared workspace identity.

All mathematics is implemented locally with the standard library. No
GrowthBook source is copied, no external statistics service is called and no
hosted experiment platform is contacted. Definitions, observations and results
are persisted in workspace-scoped tables and every mutation is audited.
"""

from __future__ import annotations

import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE

METRIC_CREATED = "experiment.metric_created"
EXPERIMENT_CREATED = "experiment.definition_created"
OBSERVATION_RECORDED = "experiment.observation_recorded"
ANALYSIS_RUN = "experiment.analysis_run"
register_event_types(METRIC_CREATED, EXPERIMENT_CREATED, OBSERVATION_RECORDED, ANALYSIS_RUN)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/experiment-stats",
    tags=["experiment-stats"],
)

METRIC_TYPES = frozenset({"proportion", "mean", "ratio"})
ENGINES = frozenset({"frequentist", "bayesian"})
KEY_RE = __import__("re").compile(r"^[a-z][a-z0-9_-]{1,63}$")


# ---------------------------------------------------------------------------
# Local statistics primitives (no SciPy, no external service)
# ---------------------------------------------------------------------------


def _erf(x: float) -> float:
    """Abramowitz & Stegun 7.1.26; |error| < 1.5e-7."""
    sign = 1.0 if x >= 0 else -1.0
    x = abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                - 0.284496736) * t + 0.254829592) * t * math.exp(-x * x)
    return sign * y


def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + _erf(z / math.sqrt(2.0)))


def norm_pdf(z: float) -> float:
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


def norm_ppf(p: float) -> float:
    """Inverse standard normal CDF by bisection (deterministic, exact enough)."""
    if not 0.0 < p < 1.0:
        raise ValueError("probability must be between 0 and 1")
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _gamma_q(a: float, x: float) -> float:
    """Regularised upper incomplete gamma Q(a, x) via Numerical Recipes."""
    if x <= 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1.0:
        # Series for P(a, x), then Q = 1 - P.
        ap, total, term = a, 1.0 / a, 1.0 / a
        for _ in range(1000):
            ap += 1.0
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-14:
                break
        return max(0.0, min(1.0, 1.0 - total * math.exp(-x + a * math.log(x) - gln)))
    # Continued fraction for Q(a, x) (Lentz's method).
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b if abs(b) > tiny else 1.0 / tiny
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return max(0.0, min(1.0, math.exp(-x + a * math.log(x) - gln) * h))


def chi2_sf(stat: float, df: int) -> float:
    """Upper tail of the chi-square distribution."""
    if stat <= 0 or df <= 0:
        return 1.0
    return _gamma_q(df / 2.0, stat / 2.0)


def _clean_key(value: str) -> str:
    key = (value or "").strip().lower()
    if not KEY_RE.match(key):
        raise ValueError("key must be 2-64 lowercase letters, digits, '_' or '-'")
    return key


def _rate_summary(sessions: int, conversions: int, value_sum: float, value_sq_sum: float) -> dict:
    sessions = max(0, sessions)
    proportion = min(1.0, max(0.0, conversions / sessions)) if sessions else 0.0
    mean = value_sum / sessions if sessions else 0.0
    variance = max(0.0, value_sq_sum / sessions - mean * mean) if sessions else 0.0
    return {"sessions": sessions, "conversions": conversions, "proportion": proportion,
            "mean": mean, "variance": variance}


def _two_sided(a: dict, b: dict, kind: str) -> dict:
    """Frequentist two-sample test of b (variant) against a (control)."""
    n1, n2 = a["sessions"], b["sessions"]
    if n1 < 2 or n2 < 2:
        return {"z": 0.0, "p_value": 1.0, "difference": 0.0,
                "confidence_interval": [0.0, 0.0], "insufficient_data": True}
    if kind == "proportion":
        m1, m2 = a["proportion"], b["proportion"]
        pooled = (a["conversions"] + b["conversions"]) / (n1 + n2)
        se_pooled = math.sqrt(max(0.0, pooled * (1 - pooled) * (1 / n1 + 1 / n2)))
        se_unpooled = math.sqrt(max(0.0, m1 * (1 - m1) / n1 + m2 * (1 - m2) / n2))
    else:  # mean (and ratio handled by caller passing pre-computed summaries)
        m1, m2 = a["mean"], b["mean"]
        se_pooled = math.sqrt(max(0.0, a["variance"] / n1 + b["variance"] / n2))
        se_unpooled = se_pooled
    difference = m2 - m1
    z = difference / se_pooled if se_pooled > 0 else 0.0
    p_value = 2.0 * (1.0 - norm_cdf(abs(z)))
    z_crit = norm_ppf(0.975)
    return {
        "z": z, "p_value": p_value, "difference": difference,
        "confidence_interval": [difference - z_crit * se_unpooled, difference + z_crit * se_unpooled],
        "insufficient_data": False,
    }


def _bayesian(a: dict, b: dict, kind: str) -> dict:
    """Posterior probability that b beats a plus expected loss of choosing b."""
    if kind == "proportion":
        a_a, a_b = 1.0 + a["conversions"], 1.0 + a["sessions"] - a["conversions"]
        b_a, b_b = 1.0 + b["conversions"], 1.0 + b["sessions"] - b["conversions"]
        ma, mb = a_a / (a_a + a_b), b_a / (b_a + b_b)
        va = a_a * a_b / ((a_a + a_b) ** 2 * (a_a + a_b + 1))
        vb = b_a * b_b / ((b_a + b_b) ** 2 * (b_a + b_b + 1))
    else:
        ma, mb = a["mean"], b["mean"]
        va = a["variance"] / a["sessions"] if a["sessions"] else 1.0
        vb = b["variance"] / b["sessions"] if b["sessions"] else 1.0
    s = math.sqrt(va + vb)
    if s == 0:
        probability = 0.5 if ma == mb else (1.0 if mb > ma else 0.0)
        expected_loss = max(0.0, ma - mb)
    else:
        probability = norm_cdf((mb - ma) / s)
        d = (ma - mb) / s
        expected_loss = (ma - mb) * norm_cdf(d) + s * norm_pdf(d)
    return {
        "control_mean": ma, "variant_mean": mb,
        "probability_variant_beats_control": probability,
        "expected_loss": max(0.0, expected_loss),
        "credible_interval": [mb - 1.96 * math.sqrt(vb), mb + 1.96 * math.sqrt(vb)],
    }


def _ratio_summary(row) -> dict:
    den = row.denominator_sum or 0
    n = max(1, row.sessions or 0)
    mean_y = (row.numerator_sum or 0) / n
    mean_x = den / n
    var_y = max(0.0, (row.numerator_sq_sum or 0) / n - mean_y * mean_y)
    var_x = max(0.0, (row.denominator_sq_sum or 0) / n - mean_x * mean_x)
    ratio = (row.numerator_sum or 0) / den if den else 0.0
    variance = 0.0
    if mean_x:
        variance = var_y / (n * mean_x * mean_x) + mean_y * mean_y * var_x / (n * mean_x ** 4)
    return {"sessions": row.sessions, "mean": ratio, "variance": variance,
            "proportion": min(1.0, max(0.0, ratio)), "conversions": int(row.numerator_sum or 0)}


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class ExperimentMetric(Base):
    __tablename__ = "experiment_metrics"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_experiment_metric_workspace_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExperimentDefinition(Base):
    __tablename__ = "experiment_definitions"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_experiment_definition_workspace_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    variants: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExperimentObservation(Base):
    __tablename__ = "experiment_observations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "experiment_id", "metric_id", "variant",
                         name="uq_experiment_observation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiment_definitions.id"), nullable=False, index=True)
    metric_id: Mapped[str] = mapped_column(ForeignKey("experiment_metrics.id"), nullable=False, index=True)
    variant: Mapped[str] = mapped_column(String(64), nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    value_sum: Mapped[float] = mapped_column(default=0.0)
    value_sq_sum: Mapped[float] = mapped_column(default=0.0)
    numerator_sum: Mapped[float] = mapped_column(default=0.0)
    numerator_sq_sum: Mapped[float] = mapped_column(default=0.0)
    denominator_sum: Mapped[float] = mapped_column(default=0.0)
    denominator_sq_sum: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MetricCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    type: str = "proportion"
    config: dict = Field(default_factory=dict)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("name")
    @classmethod
    def _name(cls, value):
        value = (value or "").strip()
        if not value or len(value) > 200:
            raise ValueError("a name of 1-200 characters is required")
        return value

    @field_validator("type")
    @classmethod
    def _type(cls, value):
        if value not in METRIC_TYPES:
            raise ValueError("unsupported metric type")
        return value


class Variant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    traffic_share: float = 0.5

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)


class ExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    variants: list[Variant] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _key(cls, value):
        return _clean_key(value)

    @field_validator("variants")
    @classmethod
    def _variants(cls, value):
        if len(value) < 2 or len(value) > 10:
            raise ValueError("an experiment needs 2-10 variants")
        if len({v.key for v in value}) != len(value):
            raise ValueError("variant keys must be unique")
        if any(v.traffic_share <= 0 for v in value):
            raise ValueError("traffic shares must be positive")
        total = sum(v.traffic_share for v in value)
        if abs(total - 1.0) > 1e-6:
            raise ValueError("traffic shares must sum to 1")
        return value


class ObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    variant: str
    sessions: int = 0
    conversions: int = 0
    value_sum: float = 0.0
    value_sq_sum: float = 0.0
    numerator_sum: float = 0.0
    numerator_sq_sum: float = 0.0
    denominator_sum: float = 0.0
    denominator_sq_sum: float = 0.0

    @field_validator("sessions", "conversions")
    @classmethod
    def _non_negative(cls, value):
        if value < 0:
            raise ValueError("counts cannot be negative")
        return value


class AnalyzeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    engine: str = "frequentist"

    @field_validator("engine")
    @classmethod
    def _engine(cls, value):
        if value not in ENGINES:
            raise ValueError("unsupported engine")
        return value


class PowerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_rate: float = 0.1
    mde: float | None = None
    sample_size: int | None = None
    alpha: float = 0.05
    power: float = 0.8

    @field_validator("baseline_rate")
    @classmethod
    def _baseline(cls, value):
        if not 0 < value < 1:
            raise ValueError("baseline_rate must be between 0 and 1")
        return value

    @field_validator("mde")
    @classmethod
    def _mde(cls, value):
        if value is not None and not 0 < value < 1:
            raise ValueError("mde must be between 0 and 1")
        return value

    @field_validator("sample_size")
    @classmethod
    def _sample(cls, value):
        if value is not None and value < 2:
            raise ValueError("sample_size must be at least 2")
        return value

    @field_validator("alpha", "power")
    @classmethod
    def _prob(cls, value):
        if not 0 < value < 1:
            raise ValueError("alpha and power must be between 0 and 1")
        return value


class CorrectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p_values: list[float] = Field(default_factory=list)
    alpha: float = 0.05

    @field_validator("p_values")
    @classmethod
    def _pvalues(cls, value):
        if not value or len(value) > 1000:
            raise ValueError("provide 1-1000 p-values")
        for p in value:
            if not 0 <= p <= 1:
                raise ValueError("p-values must be between 0 and 1")
        return value

    @field_validator("alpha")
    @classmethod
    def _alpha(cls, value):
        if not 0 < value < 1:
            raise ValueError("alpha must be between 0 and 1")
        return value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric_or_404(db: Session, workspace_id: str, metric_id: str) -> ExperimentMetric:
    row = db.execute(
        select(ExperimentMetric).where(
            ExperimentMetric.id == metric_id, ExperimentMetric.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="metric not found")
    return row


def _experiment_or_404(db: Session, workspace_id: str, experiment_id: str) -> ExperimentDefinition:
    row = db.execute(
        select(ExperimentDefinition).where(
            ExperimentDefinition.id == experiment_id,
            ExperimentDefinition.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return row


def _observations(db: Session, workspace_id: str, experiment_id: str, metric_id: str):
    return db.execute(
        select(ExperimentObservation).where(
            ExperimentObservation.workspace_id == workspace_id,
            ExperimentObservation.experiment_id == experiment_id,
            ExperimentObservation.metric_id == metric_id,
        )
    ).scalars().all()


def _observation_out(row: ExperimentObservation) -> dict:
    return {
        "id": row.id, "experiment_id": row.experiment_id, "metric_id": row.metric_id,
        "variant": row.variant, "sessions": row.sessions, "conversions": row.conversions,
        "value_sum": row.value_sum, "value_sq_sum": row.value_sq_sum,
        "numerator_sum": row.numerator_sum, "denominator_sum": row.denominator_sum,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api-contract", operation_id="experimentStatsContract")
def api_contract():
    return {
        "version": "1", "legacy_versions": [], "delivery": "local-only",
        "engines": sorted(ENGINES), "metric_types": sorted(METRIC_TYPES),
        "router_prefix": "/api/v1/workspaces/{workspace_id}/experiment-stats",
    }


@router.get("/metrics", operation_id="listExperimentMetrics")
def list_metrics(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(ExperimentMetric).where(ExperimentMetric.workspace_id == workspace_id)
        .order_by(ExperimentMetric.key)
    ).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "type": r.type, "config": r.config} for r in rows]


@router.post("/metrics", status_code=status.HTTP_201_CREATED, operation_id="createExperimentMetric")
def create_metric(
    workspace_id: str,
    body: MetricCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    """GB-029/030/031/032: one typed metric definition resource."""
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(ExperimentMetric.id).where(
            ExperimentMetric.workspace_id == workspace_id, ExperimentMetric.key == body.key
        )
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="metric key already exists")
    row = ExperimentMetric(
        id=new_id(), workspace_id=workspace_id, key=body.key, name=body.name,
        type=body.type, config=body.config, created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=METRIC_CREATED,
                  entity_id=row.id, payload={"key": row.key, "type": row.type},
                  actor_id=principal.user.id)
    db.commit()
    return {"id": row.id, "key": row.key, "name": row.name, "type": row.type, "config": row.config}


@router.get("/experiments", operation_id="listExperimentDefinitions")
def list_experiments(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(
        select(ExperimentDefinition).where(ExperimentDefinition.workspace_id == workspace_id)
        .order_by(ExperimentDefinition.key)
    ).scalars().all()
    return [{"id": r.id, "key": r.key, "name": r.name, "variants": r.variants} for r in rows]


@router.post("/experiments", status_code=status.HTTP_201_CREATED, operation_id="createExperimentDefinition")
def create_experiment(
    workspace_id: str,
    body: ExperimentCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    exists = db.execute(
        select(ExperimentDefinition.id).where(
            ExperimentDefinition.workspace_id == workspace_id, ExperimentDefinition.key == body.key
        )
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="experiment key already exists")
    row = ExperimentDefinition(
        id=new_id(), workspace_id=workspace_id, key=body.key, name=body.name,
        variants=[v.model_dump() for v in body.variants], created_at=now(),
    )
    db.add(row)
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=EXPERIMENT_CREATED,
                  entity_id=row.id, payload={"key": row.key, "variants": len(row.variants)},
                  actor_id=principal.user.id)
    db.commit()
    return {"id": row.id, "key": row.key, "name": row.name, "variants": row.variants}


@router.post("/experiments/{experiment_id}/observations", status_code=status.HTTP_201_CREATED,
             operation_id="recordExperimentObservation")
def record_observation(
    workspace_id: str,
    experiment_id: str,
    body: ObservationCreate,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    experiment = _experiment_or_404(db, workspace_id, experiment_id)
    _metric_or_404(db, workspace_id, body.metric_id)
    if body.variant not in {v["key"] for v in experiment.variants}:
        raise HTTPException(status_code=422, detail="unknown experiment variant")
    if body.conversions > body.sessions:
        raise HTTPException(status_code=422, detail="conversions cannot exceed sessions")
    row = db.execute(
        select(ExperimentObservation).where(
            ExperimentObservation.workspace_id == workspace_id,
            ExperimentObservation.experiment_id == experiment_id,
            ExperimentObservation.metric_id == body.metric_id,
            ExperimentObservation.variant == body.variant,
        )
    ).scalar_one_or_none()
    if row is None:
        row = ExperimentObservation(
            id=new_id(), workspace_id=workspace_id, experiment_id=experiment_id,
            metric_id=body.metric_id, variant=body.variant, created_at=now(),
        )
        db.add(row)
    for field in ("sessions", "conversions", "value_sum", "value_sq_sum", "numerator_sum",
                  "numerator_sq_sum", "denominator_sum", "denominator_sq_sum"):
        setattr(row, field, getattr(body, field))
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=OBSERVATION_RECORDED,
                  entity_id=row.id, payload={"experiment_id": experiment_id, "variant": body.variant},
                  actor_id=principal.user.id)
    db.commit()
    return _observation_out(row)


@router.get("/experiments/{experiment_id}/observations", operation_id="listExperimentObservations")
def list_observations(
    workspace_id: str,
    experiment_id: str,
    metric_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    _experiment_or_404(db, workspace_id, experiment_id)
    _metric_or_404(db, workspace_id, metric_id)
    return [_observation_out(row) for row in
            _observations(db, workspace_id, experiment_id, metric_id)]


def _summaries(metric, observations) -> tuple[dict, dict]:
    control = next((row for row in observations if row.variant == "control"), None)
    variant = next((row for row in observations if row.variant != "control"), None)
    if control is None or variant is None:
        raise HTTPException(status_code=422, detail="control and one variant observation are required")
    if metric.type == "ratio":
        return _ratio_summary(control), _ratio_summary(variant)
    return (
        _rate_summary(control.sessions, control.conversions, control.value_sum, control.value_sq_sum),
        _rate_summary(variant.sessions, variant.conversions, variant.value_sum, variant.value_sq_sum),
    )


@router.post("/experiments/{experiment_id}/analyze", operation_id="runExperimentAnalysis")
def analyze(
    workspace_id: str,
    experiment_id: str,
    body: AnalyzeBody,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """GB-020 / GB-021: the selected statistics engine over stored observations."""
    verify_workspace(principal, workspace_id)
    experiment = _experiment_or_404(db, workspace_id, experiment_id)
    metric = _metric_or_404(db, workspace_id, body.metric_id)
    observations = _observations(db, workspace_id, experiment_id, metric.id)
    a, b = _summaries(metric, observations)
    kind = "proportion" if metric.type == "proportion" else "mean"
    if body.engine == "frequentist":
        result = _two_sided(a, b, kind)
        analysis = {"engine": "frequentist", "z_statistic": result["z"],
                    "p_value": result["p_value"], "absolute_difference": result["difference"],
                    "confidence_interval_95": result["confidence_interval"],
                    "insufficient_data": result["insufficient_data"]}
    else:
        result = _bayesian(a, b, kind)
        analysis = {"engine": "bayesian", **result}
    analysis.update({"experiment_id": experiment.id, "metric_id": metric.id,
                     "metric_type": metric.type, "control_sessions": a["sessions"],
                     "variant_sessions": b["sessions"]})
    db.flush()
    publish_event(db, workspace_id=workspace_id, event_type=ANALYSIS_RUN,
                  entity_id=experiment.id, payload={"engine": body.engine, "metric": metric.key},
                  actor_id=principal.user.id)
    db.commit()
    return analysis


@router.post("/experiments/{experiment_id}/srm", operation_id="runExperimentSrm")
def srm(
    workspace_id: str,
    experiment_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """GB-022: chi-square sample-ratio-mismatch check against the traffic split."""
    verify_workspace(principal, workspace_id)
    experiment = _experiment_or_404(db, workspace_id, experiment_id)
    rows = db.execute(
        select(ExperimentObservation).where(
            ExperimentObservation.workspace_id == workspace_id,
            ExperimentObservation.experiment_id == experiment_id,
        )
    ).scalars().all()
    # Use one metric's observations (or the sum across metrics) for exposure counts.
    observed: dict[str, int] = {}
    for row in rows:
        observed[row.variant] = observed.get(row.variant, 0) + row.sessions
    total = sum(observed.values())
    if total == 0:
        return {"srm_detected": False, "chi_square": 0.0, "p_value": 1.0,
                "observed": observed, "expected": {}, "insufficient_data": True}
    expected = {v["key"]: total * v["traffic_share"] for v in experiment.variants}
    chi_square = sum((observed.get(key, 0) - exp) ** 2 / exp for key, exp in expected.items() if exp > 0)
    df = max(1, len(expected) - 1)
    p_value = chi2_sf(chi_square, df)
    return {"srm_detected": p_value < 0.001, "chi_square": chi_square, "p_value": p_value,
            "degrees_of_freedom": df, "observed": observed, "expected": expected,
            "insufficient_data": False}


@router.post("/experiments/{experiment_id}/health", operation_id="runExperimentHealth")
def health(
    workspace_id: str,
    experiment_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """GB-023: aggregate diagnostics for a running or finished experiment."""
    verify_workspace(principal, workspace_id)
    experiment = _experiment_or_404(db, workspace_id, experiment_id)
    check = srm(workspace_id, experiment_id, principal, db)
    diagnostics: list[dict] = []
    if check["srm_detected"]:
        diagnostics.append({"code": "srm", "severity": "error",
                            "message": "sample ratio mismatch detected (p < 0.001)"})
    seen = set(check["observed"].keys())
    for variant in experiment.variants:
        sessions = check["observed"].get(variant["key"], 0)
        seen.add(variant["key"])
        if sessions == 0:
            diagnostics.append({"code": "no_exposure", "severity": "error",
                                "message": f"variant {variant['key']} has no exposures"})
        elif sessions < 100:
            diagnostics.append({"code": "low_sample", "severity": "warning",
                                "message": f"variant {variant['key']} has fewer than 100 exposures"})
    for unexpected in sorted(seen - {v["key"] for v in experiment.variants}):
        diagnostics.append({"code": "unknown_variant", "severity": "error",
                            "message": f"observations exist for undeclared variant {unexpected}"})
    if not diagnostics:
        diagnostics.append({"code": "healthy", "severity": "ok",
                            "message": "no result health issues detected"})
    return {"experiment_id": experiment.id, "healthy": not any(
        d["severity"] == "error" for d in diagnostics), "diagnostics": diagnostics}


@router.post("/analysis/power", operation_id="runExperimentPowerAnalysis")
def power(body: PowerBody, principal: Principal = Depends(require(CONTACT_READ))) -> dict:
    """GB-038: sample-size / minimum-detectable-effect estimation."""
    z_alpha = norm_ppf(1 - body.alpha / 2)
    z_power = norm_ppf(body.power)
    factor = (z_alpha + z_power) ** 2
    variance = body.baseline_rate * (1 - body.baseline_rate)
    required_n = None
    detectable_mde = None
    if body.mde is not None:
        required_n = math.ceil(2 * factor * variance / (body.mde ** 2))
    if body.sample_size is not None:
        detectable_mde = (z_alpha + z_power) * math.sqrt(2 * variance / body.sample_size)
    return {
        "baseline_rate": body.baseline_rate, "alpha": body.alpha, "power": body.power,
        "z_alpha": z_alpha, "z_power": z_power,
        "mde": body.mde, "required_sample_size_per_variant": required_n,
        "sample_size": body.sample_size, "detectable_mde": detectable_mde,
        "method": "normal-approximation two-proportion",
    }


@router.post("/analysis/correct", operation_id="runMultipleTestingCorrection")
def correct(body: CorrectBody, principal: Principal = Depends(require(CONTACT_READ))) -> dict:
    """GB-042: Bonferroni and Benjamini-Hochberg false-positive control."""
    p = body.p_values
    m = len(p)
    bonferroni = [min(1.0, value * m) for value in p]
    order = sorted(range(m), key=lambda i: p[i])
    bh_ordered = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        index = order[rank - 1]
        running = min(running, p[index] * m / rank)
        bh_ordered[index] = min(1.0, running)
    return {
        "count": m, "alpha": body.alpha,
        "bonferroni": [
            {"p_value": p[i], "adjusted": bonferroni[i], "significant": bonferroni[i] < body.alpha}
            for i in range(m)
        ],
        "benjamini_hochberg": [
            {"p_value": p[i], "adjusted": bh_ordered[i], "significant": bh_ordered[i] < body.alpha}
            for i in range(m)
        ],
    }
