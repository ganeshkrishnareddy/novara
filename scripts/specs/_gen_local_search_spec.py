"""Generate the evidence-gated matrix spec for the local search engine cluster."""
import json
from pathlib import Path

IDS = [
    "MS-004", "MS-007", "MS-008", "MS-012", "MS-013", "MS-016", "MS-017",
    "MS-018", "MS-019", "MS-020", "MS-021", "MS-023", "MS-024", "MS-025",
    "MS-026", "MS-027", "MS-029", "MS-030", "MS-031", "MS-032", "MS-033",
    "MS-034", "MS-035", "MS-040", "MS-041", "MS-043", "MS-044", "MS-045",
    "MS-046", "MS-047", "MS-057", "MS-061",
]

SPEC = {
    "defaults": {
        "status": "VERIFIED_COMPLETE",
        "module": "search",
        "location": "apps/api/novara_core/modules/search_engine.py; apps/web/app.js (search-indexes Operations route); apps/api/tests/test_search_engine_p2.py",
        "backend": "complete: clean-room local search engine exercised by named acceptance tests",
        "frontend": "complete: dedicated search-indexes route with index list, create/delete and query panel, guarded by a static dispatch test",
        "database": "complete: two additive workspace-scoped tables asserted by named tests",
        "api": "complete: workspace-scoped index, document, settings, version and search endpoints with migration b3c4d5e6f7a9",
        "permissions": "complete: verify_workspace plus require(CONTACT_READ)/require(NOTE_WRITE); every mutation audited",
        "integration": "complete: uses the shared event bus and workspace identity; no external service claimed",
        "evidence": "docs/evidence/local-search-engine-p2-20261123.md; apps/api/tests/test_ui_wiring.py",
        "remaining": "No remaining work for the recorded local acceptance criteria. Vector/hybrid search, LMDB, task webhooks, remote export, Prometheus, SDKs/MCP, TLS/HTTP2 and LLM integration remain out of scope and are not claimed.",
    },
    "rows": [{"id": item} for item in IDS],
}

out = Path(__file__).with_name("local-search-engine-p2-20261123.json")
out.write_text(json.dumps(SPEC, indent=2) + "\n", encoding="utf-8")
print(f"spec rows: {len(IDS)} -> {out.name}")
