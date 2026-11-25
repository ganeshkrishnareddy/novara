"""Static wiring guard for the parity-capabilities SPA route.

A visible control without a dispatcher is a dead button. This reads the real
SPA source so a future refactor cannot silently orphan the controls added for
the 150-row local-capability cluster (T-130).
"""
from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def _source() -> str:
    assert APP_JS.is_file(), f"SPA source missing: {APP_JS}"
    return APP_JS.read_text(encoding="utf-8")


def test_parity_capabilities_route_is_registered_and_rendered():
    source = _source()
    assert "async function loadParityCapabilities(token)" in source
    assert "case 'parity-capabilities': return loadParityCapabilities(token);" in source
    assert "{ route: 'parity-capabilities', label: 'Parity capabilities'" in source
    for marker in (
        "api(base + '/kinds')",
        "api(base + '?kind=' + encodeURIComponent(kind))",
        'data-form="parity-select-kind"',
        'data-form="parity-create"',
        'data-form="parity-evaluate"',
        'data-action="parity-refresh"',
        "api(apiW('/parity-capabilities') + '?kind=' + encodeURIComponent(state.parityKind || ''), {",
        "'/evaluate?kind=' + encodeURIComponent(state.parityKind || '')",
        "Local NOVARA capability records only; no source project code, provider, deployment or external send is claimed.",
    ):
        assert marker in source, f"missing UI marker: {marker}"


def test_every_parity_capability_control_has_one_dispatch_handler():
    source = _source()
    actions = re.findall(r"case '([a-z0-9-]+)':", source)
    forms = re.findall(r"name === '([a-z0-9-]+)'", source)
    assert actions.count("parity-refresh") == 1
    for name in ("parity-select-kind", "parity-create", "parity-evaluate"):
        assert forms.count(name) == 1, f"unhandled or duplicated data-form: {name}"
