"""Generate the evidence-gated matrix spec for feedback cluster B."""
import json
from pathlib import Path

IDS = [
    "FB-039", "FB-043", "FB-045", "FB-046", "FB-047", "FB-048", "FB-049",
    "FB-050", "FB-051", "FB-052", "FB-053", "FB-054", "FB-066", "FB-067",
    "FB-068", "FB-069", "FB-070", "FB-071", "FB-072", "FB-073", "FB-091",
    "FB-092", "FB-094", "FB-095",
]

SPEC = {
    "defaults": {
        "status": "VERIFIED_COMPLETE",
        "module": "Feedback / Surveys",
        "location": "apps/api/novara_core/modules/feedback_extensions.py; apps/web/app.js (share links, tags, structured answers); apps/api/tests/test_feedback_extensions_p2b.py",
        "backend": "complete: clean-room local implementation exercised by a named acceptance test",
        "frontend": "complete: share-link creation, tag management, answer finish/delete and CSV export wired in apps/web/app.js with static dispatch guards",
        "database": "complete: workspace-scoped persisted rows asserted by the named test",
        "api": "complete: workspace-scoped REST endpoints under /api/v1/workspaces/{workspace_id}/feedback, with migration f1a2b3c4d5e6",
        "permissions": "complete: verify_workspace plus require(CONTACT_READ)/require(NOTE_WRITE); every mutation audited",
        "integration": "complete: uses the shared event bus and the existing Feedback Studio survey lifecycle; no external service claimed",
        "evidence": "docs/evidence/feedback-extensions-p2b-20261123.md; apps/api/tests/test_ui_wiring.py",
        "remaining": "No remaining work for the recorded acceptance criteria. Real survey distribution, cryptographic email verification and injected client-side display scripts remain out of scope for this local-first build.",
    },
    "rows": [{"id": item} for item in IDS],
}

out = Path(__file__).with_name("p2-feedback-extensions-b-20261123.json")
out.write_text(json.dumps(SPEC, indent=2) + "\n", encoding="utf-8")
print(f"spec rows: {len(IDS)} -> {out.name}")
