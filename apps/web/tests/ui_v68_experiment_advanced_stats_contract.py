"""UI wiring guard for the clean-room advanced experimentation cluster.

A visible control without a dispatcher is a dead button. This reads the actual
SPA source so a future refactor cannot silently orphan the controls added for
GB-187/188/189/214/215/217/222/237.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def _source() -> str:
    assert APP_JS.is_file(), f"SPA source missing: {APP_JS}"
    return APP_JS.read_text(encoding="utf-8")


def _handlers(source: str, pattern: str) -> set[str]:
    return set(re.findall(pattern, source))


def test_advanced_experimentation_route_controls_are_rendered_and_dispatched():
    """GB-187/188/189/214/215/217/222/237 must be visible and operable."""
    source = _source()
    assert "async function loadAdvancedExperiments(token)" in source
    assert "case 'advanced-experiments': return loadAdvancedExperiments(token)" in source
    assert "{ route: 'advanced-experiments', label: 'Advanced experimentation'" in source
    assert "'advanced-experiments': ['Advanced experimentation', 'Operations']" in source
    for marker in (
        'data-action="view-adv-contract"',
        'data-action="adv-open-analysis"',
        "api(base + '/api-contract')",
        "api(base + '/analyses')",
        "api(base + '/holdouts')",
        "api(base + '/bandits/' + encodeURIComponent(banditKey))",
        "api(base + '/analyses/' + encodeURIComponent(analysisId))",
        "No GrowthBook source, stats package, hosted platform, warehouse, SDK or external statistics service is claimed.",
        'data-form="adv-analysis-create"',
        'data-form="adv-bandit-arm"',
        'data-form="adv-bandit-recommend"',
        'data-form="adv-bandit-reward"',
        'data-form="adv-holdout-create"',
        'data-form="adv-holdout-check"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-adv-contract", "adv-open-analysis"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
    for name in (
        "adv-analysis-create",
        "adv-bandit-arm",
        "adv-bandit-recommend",
        "adv-bandit-reward",
        "adv-holdout-create",
        "adv-holdout-check",
    ):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"
