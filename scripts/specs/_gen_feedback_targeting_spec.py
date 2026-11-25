"""Generate the evidence-gated matrix spec for feedback cluster C."""
import json
from pathlib import Path

IDS = [
    "FB-055", "FB-056", "FB-057", "FB-058", "FB-059", "FB-060", "FB-061",
    "FB-062", "FB-063", "FB-064", "FB-081", "FB-082", "FB-083", "FB-084",
    "FB-192", "FB-194", "FB-195", "FB-196", "FB-197", "FB-198", "FB-199",
    "FB-200", "FB-201", "FB-202", "FB-203", "FB-204",
]

SPEC = {
    "defaults": {
        "status": "VERIFIED_COMPLETE",
        "module": "Feedback / Surveys",
        "location": "apps/api/novara_core/modules/feedback_targeting.py; apps/api/novara_core/modules/feedback_extensions.py (templates); apps/web/app.js (targeting controls + template dropdown)",
        "backend": "complete: clean-room local implementation exercised by named acceptance tests",
        "frontend": "complete: targeting panel, trigger evaluation modal, submission controls and full template dropdown wired in apps/web/app.js with static dispatch guards",
        "database": "complete: five additive workspace-scoped tables (targeting) plus template-created survey/question rows, asserted by named tests",
        "api": "complete: workspace-scoped REST endpoints under /api/v1/workspaces/{workspace_id}/feedback/targeting and the existing from-template endpoint, migration a2b3c4d5e6f8",
        "permissions": "complete: verify_workspace plus require(CONTACT_READ)/require(NOTE_WRITE); every mutation and decision audited",
        "integration": "complete: decisions create shared SurveyDisplay rows and publish events through the shared event bus; no external service claimed",
        "evidence": "docs/evidence/feedback-targeting-p2c-20261123.md; apps/api/tests/test_ui_wiring.py",
        "remaining": "No remaining work for the recorded local acceptance criteria. Injected client scripts, real-time browser SDK events, external delivery and a background scheduler remain out of scope for this local-first build.",
    },
    "rows": [{"id": item} for item in IDS],
}

out = Path(__file__).with_name("feedback-targeting-p2c-20261123.json")
out.write_text(json.dumps(SPEC, indent=2) + "\n", encoding="utf-8")
print(f"spec rows: {len(IDS)} -> {out.name}")
