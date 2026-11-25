"""Advanced experimentation statistics and decision algorithms (GrowthBook P2).

Clean-room implementation of eight commercial-tier capabilities from the
documented *method*, not from upstream source:

* GB-187 regression-adjustment (CUPED variance reduction)
* GB-188 post-stratification
* GB-189 sequential testing (mSPRT + O'Brien-Fleming spending)
* GB-214 quantile metrics (with deterministic bootstrap interval)
* GB-215 retention metrics (retention curves)
* GB-217 compound metrics (weighted composition)
* GB-222 multi-armed bandits (Thompson sampling / UCB)
* GB-237 metric correlations (Pearson)

Every algorithm is implemented locally with the Python standard library.
No GrowthBook source, stats package, hosted platform, warehouse, SDK or
external statistics service is contacted. Definitions, analyses, bandit arm
state and holdout configuration are persisted in workspace-scoped tables and
all mutations are published to NOVARA's shared event spine.
"""

from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, DateTime, Float, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..dependencies import Principal, require, verify_workspace
from ..events import publish_event, register_event_types
from ..models import new_id, now
from ..permissions import CONTACT_READ, NOTE_WRITE

ADV_PREFIX = "/api/v1/workspaces/{workspace_id}/advanced-experiments"

ANALYSIS_SAVED = "advanced.analysis_saved"
BANDIT_RECOMMENDED = "advanced.bandit_recommended"
BANDIT_REWARDED = "advanced.bandit_rewarded"
HOLDOUT_CREATED = "advanced.holdout_created"
register_event_types(ANALYSIS_SAVED, BANDIT_RECOMMENDED, BANDIT_REWARDED, HOLDOUT_CREATED)

router = APIRouter(prefix=ADV_PREFIX, tags=["advanced-experiments"])

ANALYSIS_KINDS = frozenset({
    "cuped", "post_stratification", "sequential", "quantile",
    "retention", "compound", "correlation",
})
BANDIT_POLICIES = frozenset({"thompson", "ucb"})
KEY_RE = __import__("re").compile(r"^[a-z][a-z0-9_-]{1,63}$")


# ---------------------------------------------------------------------------
# Pure algorithm layer (no I/O, no external dependency)
# ---------------------------------------------------------------------------


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _var(xs: list[float]) -> float:
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)


def _cov(xs: list[float], ys: list[float]) -> float:
    mx, my = _mean(xs), _mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / len(xs)


def _numbers(value: Any, label: str, *, minimum: int = 2) -> list[float]:
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError(label + " must be a list of at least " + str(minimum) + " numbers")
    out: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(label + " must contain only numbers")
        if not math.isfinite(float(item)):
            raise ValueError(label + " must contain only finite numbers")
        out.append(float(item))
    return out


def cuped(control: list[float], treatment: list[float],
          control_pre: list[float], treatment_pre: list[float]) -> dict:
    """CUPED: adjust the treatment effect using a pre-experiment covariate.

    theta is estimated as Cov(pre, post) / Var(pre) over pooled units. The
    adjusted effect is ``raw - theta * (mean(pre_t) - mean(pre_c))``. The
    variance-reduction ratio compares Var(post - theta*pre) with Var(post).
    """
    c, t = _numbers(control, "control"), _numbers(treatment, "treatment")
    cp, tp = _numbers(control_pre, "control_pre"), _numbers(treatment_pre, "treatment_pre")
    if not (len(c) == len(t) == len(cp) == len(tp)):
        raise ValueError("control/treatment and their pre periods must have equal length")
    pooled_pre = cp + tp
    pre_var = _var(pooled_pre)
    if pre_var <= 0:
        raise ValueError("pre-period covariate has zero variance")
    pooled_post = c + t
    theta = _cov(pooled_pre, pooled_post) / pre_var
    raw = _mean(t) - _mean(c)
    adjusted = raw - theta * (_mean(tp) - _mean(cp))
    adjusted_values = [y - theta * x for y, x in zip(pooled_post, pooled_pre)]
    raw_var, adj_var = _var(pooled_post), _var(adjusted_values)
    return {
        "method": "cuped",
        "theta": theta,
        "raw_effect": raw,
        "adjusted_effect": adjusted,
        "raw_variance": raw_var,
        "adjusted_variance": adj_var,
        "variance_reduction_ratio": (1.0 - adj_var / raw_var) if raw_var > 0 else 0.0,
    }


def post_stratification(units: list[dict]) -> dict:
    """Estimate a treatment effect as the size-weighted mean of stratum effects."""
    if not isinstance(units, list) or len(units) < 4:
        raise ValueError("units must be a list of at least four observations")
    strata: dict[str, dict[str, list[float]]] = {}
    for unit in units:
        if not isinstance(unit, dict):
            raise ValueError("each unit must be an object")
        stratum = unit.get("stratum")
        variant = unit.get("variant")
        if stratum is None or variant not in ("control", "treatment"):
            raise ValueError("unit needs a stratum and a control/treatment variant")
        value = unit.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError("unit value must be a finite number")
        bucket = strata.setdefault(str(stratum), {"control": [], "treatment": []})
        bucket[variant].append(float(value))
    rows = []
    total = 0
    weighted = 0.0
    for name, bucket in sorted(strata.items()):
        if not bucket["control"] or not bucket["treatment"]:
            raise ValueError("stratum " + name + " needs both variants")
        size = len(bucket["control"]) + len(bucket["treatment"])
        effect = _mean(bucket["treatment"]) - _mean(bucket["control"])
        total += size
        weighted += size * effect
        rows.append({"stratum": name, "size": size, "effect": effect})
    return {"method": "post_stratification", "effect": weighted / total,
            "units": total, "strata": rows}


def _norm_ppf(p: float) -> float:
    """Acklam's rational approximation for the standard normal quantile."""
    if not 0 < p < 1:
        raise ValueError("p must be between 0 and 1")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    if p < 0.02425:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > 1 - 0.02425:
        return -_norm_ppf(1 - p)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def sequential(z: float, information: int, *, tau: float = 0.5, alpha: float = 0.05,
               fraction: float = 1.0) -> dict:
    """Combine an mSPRTAlways-Valid bound with O'Brien-Fleming alpha spending.

    ``information`` is the accumulated sample size; ``fraction`` is the
    planned-information fraction at this look (0 < fraction <= 1).
    """
    if information < 1 or not math.isfinite(float(z)):
        raise ValueError("information must be positive and z must be finite")
    if not 0 < fraction <= 1 or not 0 < alpha < 1 or tau <= 0:
        raise ValueError("fraction/alpha/tau are out of range")
    variance = 1.0 + information * tau * tau
    msprt_boundary = math.sqrt(variance / information *
                               math.log((1.0 / alpha) * math.sqrt(variance)))
    z_alpha = _norm_ppf(1 - alpha / 2)
    obf_boundary = z_alpha / math.sqrt(fraction)
    return {
        "method": "sequential",
        "z": float(z),
        "information": int(information),
        "fraction": float(fraction),
        "msprt_boundary": msprt_boundary,
        "msprt_stop": abs(float(z)) >= msprt_boundary,
        "obf_boundary": obf_boundary,
        "obf_stop": abs(float(z)) >= obf_boundary,
    }


def _quantile(sorted_values: list[float], q: float) -> float:
    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def quantile_metric(values: list[float], *, q: float = 0.5,
                    bootstrap: int = 200, seed: int = 7) -> dict:
    """Quantile estimate with a deterministic bootstrap percentile interval."""
    xs = _numbers(values, "values")
    if not 0 < q < 1:
        raise ValueError("q must be between 0 and 1")
    if bootstrap < 20 or bootstrap > 2000:
        raise ValueError("bootstrap must be between 20 and 2000")
    rng = random.Random(seed)
    ordered = sorted(xs)
    point = _quantile(ordered, q)
    estimates = sorted(_quantile(sorted(rng.choices(xs, k=len(xs))), q)
                       for _ in range(bootstrap))
    lo = estimates[int(0.025 * (bootstrap - 1))]
    hi = estimates[int(0.975 * (bootstrap - 1))]
    return {"method": "quantile", "q": q, "value": point,
            "ci_low": lo, "ci_high": hi, "bootstrap": bootstrap, "seed": seed}


def retention(cohorts: list[dict]) -> dict:
    """Build a day-N retention curve fromcohort counts."""
    if not isinstance(cohorts, list) or not cohorts:
        raise ValueError("cohorts must be a non-empty list")
    rows = []
    for cohort in cohorts:
        if not isinstance(cohort, dict):
            raise ValueError("each cohort must be an object")
        day = cohort.get("day")
        size = cohort.get("size")
        kept = cohort.get("retained")
        if not isinstance(day, int) or isinstance(day, bool) or day < 0:
            raise ValueError("cohort day must be a non-negative integer")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError("cohort size must be a positive integer")
        if not isinstance(kept, int) or isinstance(kept, bool) or kept < 0 or kept > size:
            raise ValueError("cohort retained must be between 0 and size")
        rows.append({"day": day, "retention": kept / size, "size": size, "retained": kept})
    rows.sort(key=lambda row: row["day"])
    return {"method": "retention", "curve": rows,
            "day_0": rows[0]["retention"], "last_day": rows[-1]["day"],
            "last_retention": rows[-1]["retention"]}


def compound(components: list[dict]) -> dict:
    """Combine weighted component metrics into one compound score."""
    if not isinstance(components, list) or len(components) < 2:
        raise ValueError("components must be a list of at least two metrics")
    total_weight = 0.0
    weighted = 0.0
    rows = []
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("each component must be an object")
        name = component.get("name")
        value = component.get("value")
        weight = component.get("weight", 1)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("component needs a name")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError("component value must be a finite number")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or float(weight) <= 0:
            raise ValueError("component weight must be positive")
        total_weight += float(weight)
        weighted += float(value) * float(weight)
        rows.append({"name": name, "value": float(value), "weight": float(weight)})
    return {"method": "compound", "score": weighted / total_weight,
            "total_weight": total_weight, "components": rows}


def correlation(xs: list[float], ys: list[float]) -> dict:
    """Pearson product-moment correlation between two equally long series."""
    a, b = _numbers(xs, "xs"), _numbers(ys, "ys")
    if len(a) != len(b):
        raise ValueError("xs and ys must have equal length")
    ma, mb = _mean(a), _mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    if den == 0:
        raise ValueError("correlation is undefined for a constant series")
    r = num / den
    return {"method": "correlation", "r": r, "r_squared": r * r, "n": len(a)}


def _gamma_sample(shape: float, rng: random.Random) -> float:
    """Marsaglia-Tsang gamma sampler for shape >= 1."""
    if shape < 1:
        return _gamma_sample(shape + 1, rng) * (rng.random() ** (1.0 / shape))
    d = shape - 1.0 / 3.0
    c = 1.0 / math.sqrt(9.0 * d)
    while True:
        x = rng.gauss(0.0, 1.0)
        v = 1.0 + c * x
        if v <= 0:
            continue
        v = v ** 3
        u = rng.random()
        if u < 1.0 - 0.0331 * x ** 4:
            return d * v
        if math.log(u) < 0.5 * x * x + d * (1.0 - v + math.log(v)):
            return d * v


def _beta_sample(a: float, b: float, rng: random.Random) -> float:
    ga = _gamma_sample(a, rng)
    gb = _gamma_sample(b, rng)
    return ga / (ga + gb)


def bandit_recommend(arms: list[dict], *, policy: str = "thompson",
                     seed: int = 11) -> str:
    """Pick an arm by Thompson sampling or upper confidence bound."""
    if policy not in BANDIT_POLICIES:
        raise ValueError("unknown bandit policy")
    if not isinstance(arms, list) or not arms:
        raise ValueError("arms must be a non-empty list")
    rng = random.Random(seed)
    scores: dict[str, float] = {}
    total = 0
    for arm in arms:
        if not isinstance(arm, dict) or not isinstance(arm.get("arm"), str):
            raise ValueError("each arm needs a string name")
        alpha = float(arm.get("alpha", 1))
        beta = float(arm.get("beta", 1))
        pulls = int(arm.get("pulls", 0))
        if alpha <= 0 or beta <= 0 or pulls < 0:
            raise ValueError("arm alpha/beta/pulls are out of range")
        total += pulls
        if policy == "thompson":
            scores[arm["arm"]] = _beta_sample(alpha, beta, rng)
        else:
            successes = max(alpha - 1.0, 0.0)
            mean = successes / (alpha + beta - 2.0) if (alpha + beta) > 2 else 0.0
            bonus = math.sqrt(2.0 * math.log(max(total, 2)) / (pulls + 1))
            scores[arm["arm"]] = mean + bonus
    return max(scores, key=lambda key: scores[key])


def holdout_assigned(user_key: str, fraction: float) -> bool:
    """Deterministically assign a user to a global holdout by hash bucket."""
    if not isinstance(user_key, str) or not user_key:
        raise ValueError("user_key is required")
    if not 0 <= fraction <= 1:
        raise ValueError("fraction must be between 0 and 1")
    digest = hashlib.sha256(("novara-holdout:" + user_key).encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % 10000
    return bucket < int(fraction * 10000)


# ---------------------------------------------------------------------------
# Persistence models
# ---------------------------------------------------------------------------


class AdvAnalysis(Base):
    __tablename__ = "adv_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    experiment_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now)


class AdvBanditArm(Base):
    __tablename__ = "adv_bandit_arms"
    __table_args__ = (
        UniqueConstraint("workspace_id", "bandit_key", "arm", name="uq_adv_bandit_arm"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    bandit_key: Mapped[str] = mapped_column(String(128), nullable=False)
    arm: Mapped[str] = mapped_column(String(128), nullable=False)
    alpha: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    beta: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    pulls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now)


class AdvHoldout(Base):
    __tablename__ = "adv_holdouts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_adv_holdout"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    fraction: Mapped[float] = mapped_column(Float, nullable=False)
    experiment_keys: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class AnalysisIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    name: str = Field(min_length=2, max_length=200)
    experiment_key: str = ""
    inputs: dict[str, Any]

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        if value not in ANALYSIS_KINDS:
            raise ValueError("unknown analysis kind")
        return value


class BanditArmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arm: str = Field(min_length=1, max_length=128)
    alpha: float = 1.0
    beta: float = 1.0
    pulls: int = 0


class BanditRecommendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: str = "thompson"
    seed: int = 11
    arms: list[BanditArmIn] | None = None


class BanditRewardIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arm: str = Field(min_length=1, max_length=128)
    reward: float


class HoldoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=200)
    fraction: float
    experiment_keys: list[str] = Field(default_factory=list)

    @field_validator("fraction")
    @classmethod
    def _fraction(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("fraction must be between 0 and 1")
        return value


class HoldoutCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_key: str = Field(min_length=1, max_length=320)


# ---------------------------------------------------------------------------
# Helpers and routes
# ---------------------------------------------------------------------------


def _compute(kind: str, inputs: dict) -> dict:
    try:
        if kind == "cuped":
            return cuped(inputs["control"], inputs["treatment"],
                         inputs["control_pre"], inputs["treatment_pre"])
        if kind == "post_stratification":
            return post_stratification(inputs["units"])
        if kind == "sequential":
            return sequential(float(inputs["z"]), int(inputs["information"]),
                              tau=float(inputs.get("tau", 0.5)),
                              alpha=float(inputs.get("alpha", 0.05)),
                              fraction=float(inputs.get("fraction", 1.0)))
        if kind == "quantile":
            return quantile_metric(inputs["values"], q=float(inputs.get("q", 0.5)),
                                   bootstrap=int(inputs.get("bootstrap", 200)),
                                   seed=int(inputs.get("seed", 7)))
        if kind == "retention":
            return retention(inputs["cohorts"])
        if kind == "compound":
            return compound(inputs["components"])
        if kind == "correlation":
            return correlation(inputs["xs"], inputs["ys"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise HTTPException(status_code=422, detail="unknown analysis kind")


def _audit(db: Session, workspace_id: str, event_type: str, entity_id: str,
           payload: dict, principal: Principal) -> None:
    publish_event(db, workspace_id=workspace_id, event_type=event_type,
                  entity_id=entity_id, payload=payload, actor_id=principal.user.id)


def _analysis_out(row: AdvAnalysis) -> dict:
    return {"id": row.id, "kind": row.kind, "name": row.name,
            "experiment_key": row.experiment_key, "inputs": row.inputs,
            "result": row.result, "created_at": row.created_at.isoformat()}


def _bandit_rows(db: Session, workspace_id: str, bandit_key: str) -> list[AdvBanditArm]:
    return list(db.execute(select(AdvBanditArm).where(
        AdvBanditArm.workspace_id == workspace_id,
        AdvBanditArm.bandit_key == bandit_key,
    ).order_by(AdvBanditArm.arm)).scalars().all())


@router.get("/api-contract", operation_id="advancedExperimentsContract")
def api_contract() -> dict:
    return {
        "external_calls": False,
        "source": "NOVARA clean-room; algorithms implemented locally from the documented method",
        "analysis_kinds": sorted(ANALYSIS_KINDS),
        "bandit_policies": sorted(BANDIT_POLICIES),
        "capabilities": ["GB-187", "GB-188", "GB-189", "GB-214", "GB-215",
                         "GB-217", "GB-222", "GB-237"],
    }


@router.post("/analyses", status_code=status.HTTP_201_CREATED, operation_id="saveAdvancedAnalysis")
def save_analysis(
    workspace_id: str,
    body: AnalysisIn,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    result = _compute(body.kind, body.inputs)
    row = AdvAnalysis(
        id=new_id(), workspace_id=workspace_id, kind=body.kind, name=body.name,
        experiment_key=body.experiment_key, inputs=body.inputs, result=result,
        created_by=principal.user.id, created_at=now(),
    )
    db.add(row)
    db.flush()
    _audit(db, workspace_id, ANALYSIS_SAVED, row.id,
           {"kind": row.kind, "name": row.name}, principal)
    db.commit()
    return _analysis_out(row)


@router.get("/analyses", operation_id="listAdvancedAnalyses")
def list_analyses(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(AdvAnalysis).where(
        AdvAnalysis.workspace_id == workspace_id).order_by(AdvAnalysis.created_at)
    ).scalars().all()
    return [_analysis_out(row) for row in rows]


@router.get("/analyses/{analysis_id}", operation_id="getAdvancedAnalysis")
def get_analysis(
    workspace_id: str,
    analysis_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(AdvAnalysis).where(
        AdvAnalysis.id == analysis_id, AdvAnalysis.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return _analysis_out(row)


@router.post("/bandits/{bandit_key}/arms", status_code=status.HTTP_201_CREATED,
             operation_id="upsertBanditArm")
def upsert_arm(
    workspace_id: str,
    bandit_key: str,
    body: BanditArmIn,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if not KEY_RE.match(bandit_key):
        raise HTTPException(status_code=422, detail="invalid bandit key")
    if body.alpha <= 0 or body.beta <= 0 or body.pulls < 0:
        raise HTTPException(status_code=422, detail="invalid arm statistics")
    row = db.execute(select(AdvBanditArm).where(
        AdvBanditArm.workspace_id == workspace_id,
        AdvBanditArm.bandit_key == bandit_key, AdvBanditArm.arm == body.arm,
    )).scalar_one_or_none()
    if row is None:
        row = AdvBanditArm(id=new_id(), workspace_id=workspace_id,
                           bandit_key=bandit_key, arm=body.arm)
        db.add(row)
    row.alpha, row.beta, row.pulls, row.updated_at = body.alpha, body.beta, body.pulls, now()
    db.flush()
    out = {"arm": row.arm, "alpha": row.alpha, "beta": row.beta, "pulls": row.pulls}
    db.commit()
    return out


@router.get("/bandits/{bandit_key}", operation_id="getBanditState")
def get_bandit(
    workspace_id: str,
    bandit_key: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    rows = _bandit_rows(db, workspace_id, bandit_key)
    return {"bandit_key": bandit_key,
            "arms": [{"arm": r.arm, "alpha": r.alpha, "beta": r.beta, "pulls": r.pulls}
                     for r in rows]}


@router.post("/bandits/{bandit_key}/recommend", operation_id="recommendBanditArm")
def recommend_bandit(
    workspace_id: str,
    bandit_key: str,
    body: BanditRecommendIn,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if body.policy not in BANDIT_POLICIES:
        raise HTTPException(status_code=422, detail="unknown bandit policy")
    persisted = _bandit_rows(db, workspace_id, bandit_key)
    arms = body.arms
    if arms is None:
        arms = [BanditArmIn(arm=r.arm, alpha=r.alpha, beta=r.beta, pulls=r.pulls)
                for r in persisted]
    payload = [{"arm": a.arm, "alpha": a.alpha, "beta": a.beta, "pulls": a.pulls}
               for a in arms]
    try:
        chosen = bandit_recommend(payload, policy=body.policy, seed=body.seed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(db, workspace_id, BANDIT_RECOMMENDED, bandit_key,
           {"policy": body.policy, "arm": chosen}, principal)
    db.commit()
    return {"bandit_key": bandit_key, "policy": body.policy, "arm": chosen}


@router.post("/bandits/{bandit_key}/reward", operation_id="rewardBanditArm")
def reward_bandit(
    workspace_id: str,
    bandit_key: str,
    body: BanditRewardIn,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if not math.isfinite(body.reward) or not 0 <= body.reward <= 1:
        raise HTTPException(status_code=422, detail="reward must be between 0 and 1")
    row = db.execute(select(AdvBanditArm).where(
        AdvBanditArm.workspace_id == workspace_id,
        AdvBanditArm.bandit_key == bandit_key, AdvBanditArm.arm == body.arm,
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="bandit arm not found")
    row.alpha += body.reward
    row.beta += (1.0 - body.reward)
    row.pulls += 1
    row.updated_at = now()
    db.flush()
    _audit(db, workspace_id, BANDIT_REWARDED, row.id,
           {"arm": row.arm, "reward": body.reward}, principal)
    out = {"arm": row.arm, "alpha": row.alpha, "beta": row.beta, "pulls": row.pulls}
    db.commit()
    return out


@router.post("/holdouts", status_code=status.HTTP_201_CREATED, operation_id="createHoldout")
def create_holdout(
    workspace_id: str,
    body: HoldoutIn,
    principal: Principal = Depends(require(NOTE_WRITE)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    if not KEY_RE.match(body.name.lower().replace(" ", "-")):
        raise HTTPException(status_code=422, detail="invalid holdout name")
    exists = db.execute(select(AdvHoldout.id).where(
        AdvHoldout.workspace_id == workspace_id, AdvHoldout.name == body.name
    )).first()
    if exists:
        raise HTTPException(status_code=409, detail="holdout already exists")
    row = AdvHoldout(id=new_id(), workspace_id=workspace_id, name=body.name,
                     fraction=body.fraction, experiment_keys=body.experiment_keys,
                     created_at=now())
    db.add(row)
    db.flush()
    _audit(db, workspace_id, HOLDOUT_CREATED, row.id,
           {"name": row.name, "fraction": row.fraction}, principal)
    db.commit()
    return {"id": row.id, "name": row.name, "fraction": row.fraction,
            "experiment_keys": row.experiment_keys}


@router.get("/holdouts", operation_id="listHoldouts")
def list_holdouts(
    workspace_id: str,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> list[dict]:
    verify_workspace(principal, workspace_id)
    rows = db.execute(select(AdvHoldout).where(
        AdvHoldout.workspace_id == workspace_id).order_by(AdvHoldout.name)
    ).scalars().all()
    return [{"id": r.id, "name": r.name, "fraction": r.fraction,
             "experiment_keys": r.experiment_keys} for r in rows]


@router.post("/holdouts/{holdout_id}/check", operation_id="checkHoldoutAssignment")
def check_holdout(
    workspace_id: str,
    holdout_id: str,
    body: HoldoutCheckIn,
    principal: Principal = Depends(require(CONTACT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    verify_workspace(principal, workspace_id)
    row = db.execute(select(AdvHoldout).where(
        AdvHoldout.id == holdout_id, AdvHoldout.workspace_id == workspace_id
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="holdout not found")
    try:
        assigned = holdout_assigned(body.user_key, row.fraction)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"holdout": row.name, "user_key": body.user_key, "assigned": assigned}
