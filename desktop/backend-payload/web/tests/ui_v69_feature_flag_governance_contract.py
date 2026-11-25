

from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def _source() -> str:
    assert APP_JS.is_file(), f"SPA source missing: {APP_JS}"
    return APP_JS.read_text(encoding="utf-8")


def _handlers(source: str, pattern: str) -> set[str]:
    return set(re.findall(pattern, source))


def test_flag_governance_route_controls_are_rendered_and_dispatched():
    """GB-183/196/206/209/210/211/224/225/231/232/233/247/248/249 are wired."""
    source = _source()
    assert "async function loadFlagGovernance(token)" in source
    assert "case 'flag-governance': return loadFlagGovernance(token)" in source
    assert "{ route: 'flag-governance', label: 'Flag governance'" in source
    assert "'flag-governance': ['Flag governance', 'Operations']" in source
    for marker in (
        'data-action="view-flag-governance-contract"',
        "api(base + '/api-contract')", "api(base + '/settings')",
        "api(base + '/templates')", "api(base + '/configs')",
        "No GrowthBook source, SDK, hosted endpoint, licence server, warehouse or external service is used.",
        'data-form="fg-schedule-create"', 'data-form="fg-schedule-resolve"',
        'data-form="fg-secure-attr"', 'data-form="fg-sticky"',
        'data-form="fg-prereq-create"', 'data-form="fg-prereq-check"',
        'data-form="fg-redirect-create"', 'data-form="fg-redirect-resolve"',
        'data-form="fg-env-create"', 'data-form="fg-env-resolve"',
        'data-form="fg-template-create"', 'data-form="fg-template-instantiate"',
        'data-form="fg-safe-rollout-create"', 'data-form="fg-safe-rollout-eval"',
        'data-form="fg-settings-save"', 'data-form="fg-ramp-create"',
        'data-form="fg-ramp-percent"', 'data-form="fg-revision-create"',
        'data-form="fg-revision-apply"', 'data-form="fg-revision-resolve"',
        'data-form="fg-config-set"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-flag-governance-contract",):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
    for name in ("fg-schedule-create", "fg-schedule-resolve", "fg-secure-attr",
                 "fg-sticky", "fg-prereq-create", "fg-prereq-check",
                 "fg-redirect-create", "fg-redirect-resolve", "fg-env-create",
                 "fg-env-resolve", "fg-template-create", "fg-template-instantiate",
                 "fg-safe-rollout-create", "fg-safe-rollout-eval", "fg-settings-save",
                 "fg-ramp-create", "fg-ramp-percent", "fg-revision-create",
                 "fg-revision-apply", "fg-revision-resolve", "fg-config-set"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"
