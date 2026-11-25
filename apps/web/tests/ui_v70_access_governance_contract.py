from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def _source() -> str:
    assert APP_JS.is_file(), f"SPA source missing: {APP_JS}"
    return APP_JS.read_text(encoding="utf-8")


def test_access_governance_route_controls_are_rendered_and_dispatched():
    """CW-130/CW-139/PL-124/PL-125/NV-070 access governance is wired in the SPA."""
    source = _source()
    assert "async function loadAccessGovernance(token)" in source
    assert "case 'access-governance': return loadAccessGovernance(token)" in source
    assert "{ route: 'access-governance', label: 'Access governance'" in source
    assert "'access-governance': ['Access governance', 'Operations']" in source
    for marker in (
        "api(base + '/permissions')",
        "api(base + '/custom-roles')",
        "api(base + '/schemes')",
        "/audit",
        "No upstream source is copied. No external service, licence server or hosted control plane is contacted. IP data is never invented.",
        "data-form=\"ag-custom-role-create\"",
        "data-form=\"ag-custom-role-assign\"",
        "data-form=\"ag-custom-role-revoke\"",
        "data-form=\"ag-scheme-create\"",
        "data-form=\"ag-scheme-assign\"",
        "data-form=\"ag-permission-check\"",
        "data-action=\"view-access-governance-contract\"",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = set(re.findall(r"case '([a-z0-9-]+)':", source))
    forms = set(re.findall(r"name === '([a-z0-9-]+)'", source))
    for name in ("view-access-governance-contract",):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
    for name in ("ag-custom-role-create", "ag-custom-role-assign", "ag-custom-role-revoke",
                 "ag-scheme-create", "ag-scheme-assign", "ag-permission-check"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"
