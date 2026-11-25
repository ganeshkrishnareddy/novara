"""Static wiring guard for the final-capabilities SPA route."""
from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def _source() -> str:
    assert APP_JS.is_file(), f"SPA source missing: {APP_JS}"
    return APP_JS.read_text(encoding="utf-8")


def test_final_capabilities_route_is_registered_and_rendered():
    source = _source()
    assert "async function loadFinalCapabilities(token)" in source
    assert "case 'final-capabilities': return loadFinalCapabilities(token);" in source
    assert "{ route: 'final-capabilities', label: 'Final capabilities'" in source
    for marker in (
        "apiW('/final-capabilities')",
        'data-form="final-select-kind"',
        'data-form="final-create"',
        'data-form="final-evaluate"',
        'data-action="final-refresh"',
        "Final NOVARA local capabilities only; no source project code, provider, deployment or external send is claimed.",
    ):
        assert marker in source, f"missing UI marker: {marker}"


def test_every_final_capability_control_has_one_dispatch_handler():
    source = _source()
    actions = re.findall(r"case '([a-z0-9-]+)':", source)
    forms = re.findall(r"name === '([a-z0-9-]+)'", source)
    assert actions.count("final-refresh") == 1
    for name in ("final-select-kind", "final-create", "final-evaluate"):
        assert forms.count(name) == 1, f"unhandled or duplicated data-form: {name}"
