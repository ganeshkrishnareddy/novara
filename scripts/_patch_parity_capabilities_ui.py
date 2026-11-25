"""Add the parity-capabilities SPA route and its static wiring contract test."""
from pathlib import Path

ROOT = Path(r"D:\NOVARA")
APP = ROOT / "apps/web/app.js"
TEST = ROOT / "apps/api/tests/test_parity_capabilities_ui_contract.py"

source = APP.read_text(encoding="utf-8")
patches = []

patches.append((
    "    { route: 'advanced-experiments', label: 'Advanced experimentation', icon: 'insights', perm: P.contactRead },\n",
    "    { route: 'advanced-experiments', label: 'Advanced experimentation', icon: 'insights', perm: P.contactRead },\n"
    "    { route: 'parity-capabilities', label: 'Parity capabilities', icon: 'layers', perm: P.contactRead },\n",
))

patches.append((
    "    case 'advanced-experiments': return loadAdvancedExperiments(token);\n",
    "    case 'advanced-experiments': return loadAdvancedExperiments(token);\n"
    "    case 'parity-capabilities': return loadParityCapabilities(token);\n",
))

LOADER = """async function loadParityCapabilities(token) {
  if (!can(P.contactRead)) {
    renderViewHtml(pageHead('Operations', 'Parity capabilities', '') +
      errorBlock('Your role does not include capability access.'));
    return;
  }
  loadingView('Parity capabilities', 'Local workspace-scoped capability records. No source project code, provider, deployment or external send is claimed.');
  const base = apiW('/parity-capabilities');
  let kinds, records;
  try {
    kinds = await api(base + '/kinds') || [];
    const kind = state.parityKind || (kinds[0] && kinds[0].kind) || '';
    state.parityKind = kind;
    records = kind ? (await api(base + '?kind=' + encodeURIComponent(kind)) || []) : [];
  } catch (err) {
    if (token !== state.viewToken) return;
    renderViewHtml(pageHead('Operations', 'Parity capabilities', '') + errorBlock(errMessage(err)));
    return;
  }
  if (token !== state.viewToken) return;
  const write = can(P.contactWrite);
  let html = pageHead('Operations', 'Parity capabilities', kinds.length + ' local capability kinds',
    '<button class="btn" data-action="parity-refresh">' + icon('activity', 15) + ' Refresh</button>');
  html += governanceNote('Local NOVARA capability records only; no source project code, provider, deployment or external send is claimed.');
  html += '<section class="card"><h2 class="page-title">Capability kind</h2>' +
    '<form data-form="parity-select-kind"><div class="form-grid">' +
    field('kind', 'Kind', { type: 'select', options: selectOptions(kinds.map(function (k) {
      return [k.kind, k.row_id + ' - ' + k.name]; }), state.parityKind), required: true }) +
    '</div><div class="form-actions"><button class="btn" type="submit">Select</button></div></form></section>';
  if (write) {
    html += '<section class="card"><h2 class="page-title">Create local record</h2>' +
      '<form data-form="parity-create"><div class="form-grid">' +
      field('name', 'Name', { value: 'Local capability', required: true }) +
      field('payload_json', 'Payload (JSON object)', { type: 'textarea', span: true, required: true, value: '{\"value\": \"probe\"}' }) +
      '</div><div class="form-actions"><button class="btn btn--primary" type="submit">Save record</button></div></form></section>';
    html += '<section class="card"><h2 class="page-title">Evaluate</h2>' +
      '<form data-form="parity-evaluate"><div class="form-grid">' +
      field('record_id', 'Record', { type: 'select', options: selectOptions(records.map(function (r) {
        return [r.record_id, r.name + ' - ' + r.record_id.slice(0, 8)]; })), required: true }) +
      field('input_json', 'Input (JSON object)', { type: 'textarea', span: true, required: true, value: '{\"value\": \"probe\"}' }) +
      '</div><div class="form-actions"><button class="btn btn--primary" type="submit">Evaluate locally</button></div></form></section>';
  }
  html += '<section class="card"><h2 class="page-title">Stored records</h2>' +
    (records.length ? '<div class="table-wrap"><table class="data"><thead><tr><th>Row</th><th>Kind</th><th>Name</th><th>Payload</th></tr></thead><tbody>' +
      records.map(function (r) { return '<tr><td>' + esc(r.row_id) + '</td><td>' + esc(r.kind) + '</td><td>' +
        esc(r.name) + '</td><td class="small">' + esc(JSON.stringify(r.payload)) + '</td></tr>'; }).join('') +
      '</tbody></table></div>' : '<p class="muted small">No local records for this kind yet.</p>') + '</section>';
  renderViewHtml(html);
}

"""
patches.append((
    "async function loadAdvancedExperiments(token) {\n",
    LOADER + "async function loadAdvancedExperiments(token) {\n",
))

ACTIONS = """    case 'parity-refresh': {
      await loadView();
      return;
    }
"""
patches.append((
    "    case 'view-adv-contract': {\n",
    ACTIONS + "    case 'view-adv-contract': {\n",
))

FORMS = """  if (name === 'parity-select-kind') {
    state.parityKind = text('kind');
    await loadView();
    return;
  }
  if (name === 'parity-create') {
    let payload;
    try { payload = JSON.parse(text('payload_json')); }
    catch (e) { toast('Payload must be a valid JSON object.', 'error'); return; }
    await api(apiW('/parity-capabilities') + '?kind=' + encodeURIComponent(state.parityKind || ''), {
      method: 'POST', body: { name: text('name'), payload: payload },
    });
    await loadView();
    toast('Local capability record saved.', 'success');
    return;
  }
  if (name === 'parity-evaluate') {
    let input;
    try { input = JSON.parse(text('input_json')); }
    catch (e) { toast('Input must be a valid JSON object.', 'error'); return; }
    const result = await api(apiW('/parity-capabilities') + '/' + encodeURIComponent(text('record_id')) +
      '/evaluate?kind=' + encodeURIComponent(state.parityKind || ''), { method: 'POST', body: { input: input } });
    openModal({ title: 'Local evaluation result', sub: 'external_action ' + String(result.external_action),
      body: '<pre class="small">' + esc(JSON.stringify(result.result, null, 2)) + '</pre>' });
    return;
  }

"""
patches.append((
    "  if (name === 'adv-analysis-create') {\n",
    FORMS + "  if (name === 'adv-analysis-create') {\n",
))

for anchor, replacement in patches:
    count = source.count(anchor)
    if count != 1:
        raise SystemExit(f"anchor count {count}: {anchor[:70]!r}")
    source = source.replace(anchor, replacement)
APP.write_text(source, encoding="utf-8")

test = '''"""Static wiring guard for the parity-capabilities SPA route.

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
        "api(base + '?kind=' + encodeURIComponent(state.parityKind || ''), {",
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
'''
TEST.write_text(test, encoding="utf-8")
print("patched SPA route and wrote UI contract test")
