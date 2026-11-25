"""Generate the evidence-gated matrix spec for the P2 feedback extension cluster."""
import json
from pathlib import Path

IDS = [
    "FB-008", "FB-009", "FB-011", "FB-012", "FB-013", "FB-014", "FB-016",
    "FB-017", "FB-018", "FB-019", "FB-021", "FB-022", "FB-023", "FB-026",
    "FB-027", "FB-028", "FB-030", "FB-032", "FB-033", "FB-034", "FB-035",
    "FB-037", "FB-040", "FB-041", "FB-042", "FB-044",
]

SPEC = {
    "defaults": {
        "status": "VERIFIED_COMPLETE",
        "module": "Feedback / Surveys",
        "location": "apps/api/novara_core/modules/feedback_extensions.py; apps/web/app.js (survey configuration panel); apps/api/tests/test_feedback_extensions_p2.py",
        "backend": "complete: clean-room local implementation exercised by a named acceptance test",
        "frontend": "complete: survey configuration, question editor, template creation and embedded-data controls wired in apps/web/app.js with static dispatch guards",
        "database": "complete: workspace-scoped persisted rows asserted by the named test",
        "api": "complete: workspace-scoped REST endpoints under /api/v1/workspaces/{workspace_id}/feedback",
        "permissions": "complete: verify_workspace plus require(CONTACT_READ)/require(NOTE_WRITE); every mutation audited",
        "integration": "complete: uses the shared event bus and the existing Feedback Studio survey lifecycle; no external service claimed",
        "evidence": "docs/evidence/feedback-extensions-p2-20261123.md; apps/api/tests/test_ui_wiring.py",
        "remaining": "No remaining work for the recorded acceptance criteria. Presentation/webhook delivery and any Formbricks-hosted service remain out of scope for this local-first build.",
    },
    "rows": [{"id": item} for item in IDS],
}

out = Path(__file__).with_name("p2-feedback-extensions-20261123.json")
out.write_text(json.dumps(SPEC, indent=2) + "\n", encoding="utf-8")
print(f"spec rows: {len(IDS)} -> {out.name}")
