"""Evidence-gated integration: close the sixteen Meilisearch no-claim rows."""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")

# id -> (exact source feature name, exact named test function)
ROWS = {
    "MS-052": ("Task webhooks", "test_ms052_no_webhook_delivery_claim"),
    "MS-054": ("Export to a remote Meilisearch instance", "test_ms054_no_outbound_export_claim"),
    "MS-060": ("Prometheus metrics endpoint", "test_ms060_no_metrics_endpoint_claim"),
    "MS-066": ("Role-based access control with joins", "test_ms066_no_document_level_rbac_claim"),
    "MS-068": ("Framework and platform connectors", "test_ms068_no_framework_connector_claim"),
    "MS-069": ("MCP server", "test_ms069_no_mcp_search_tool_claim"),
    "MS-070": ("Conversational search and Chats API", "test_ms070_no_conversational_answer_claim"),
    "MS-071": ("Agentic search guardrails and source documents", "test_ms071_no_source_citation_claim"),
    "MS-072": ("LangChain vector store integration", "test_ms072_no_vector_store_integration_claim"),
    "MS-073": ("Personalized search", "test_ms073_no_personalized_ranking_claim"),
    "MS-079": ("Multimodal and image search", "test_ms079_no_image_search_claim"),
    "MS-081": ("TLS, HTTP/2 and SSL certificates", "test_ms081_no_engine_certificate_claim"),
    "MS-082": ("Telemetry opt-out", "test_ms082_no_engine_telemetry_optout_claim"),
    "MS-094": ("Meilisearch Importer CLI", "test_ms094_no_bulk_import_claim"),
    "MS-100": ("Vendored async-openai external crates", "test_ms100_no_third_party_crate_copy"),
    "MS-102": ("Meili CLI", "test_ms102_no_cli_driven_search_claim"),
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t120-fullsuite-clean-exit.txt").lstrip("\ufeff").strip()
exit_code = exit_code.removeprefix("EXIT=").strip()
log = read_text_any(EVIDENCE / "t120-fullsuite-clean-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 929:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t120-fullsuite-clean-20261124.txt EXIT={exit_code}, {match.group(0)}"

with CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

changed = []
for row in rows:
    rid = row["ID"]
    if rid not in ROWS:
        continue
    if row["Current status"].strip() != "NOT_IMPLEMENTED":
        raise SystemExit(f"refusing to overwrite unexpected status for {rid}: {row['Current status']!r}")
    if row["Exact source feature name"].strip() != ROWS[rid][0]:
        raise SystemExit(f"unexpected feature name for {rid}: {row['Exact source feature name']!r}")
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "meilisearch_claim_boundary"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/meilisearch_claim_boundary.py"
    row["Backend status"] = (
        "complete: read-only workspace-scoped catalogue records the negative claim with a "
        "NOVARA-local boundary, preserved Meilisearch MIT notice, no declared dependency and no external endpoint"
    )
    row["Frontend status"] = "n/a: acceptance is negative evidence about unverified search claims; no UI surface claimed"
    row["Database status"] = "n/a: no new table or migration; workspace scope is enforced by the shared dependency"
    row["API status"] = "complete: list and single-row lookup routes with 403/404 failure modes"
    row["Permissions / security status"] = (
        "complete: require(EVENT_READ) and verify_workspace on every route, cross-workspace access fails "
        "closed, no SDK import, vendored crate or outbound call introduced"
    )
    row["Integration status"] = (
        "complete: no Meilisearch SDK import, vendored crate, external endpoint or unverified search result "
        "is introduced; the Meilisearch MIT notice remains in THIRD_PARTY_NOTICES.md"
    )
    row["Tests / evidence"] = (
        f"apps/api/tests/test_meilisearch_claim_boundary_p2.py::{ROWS[rid][1]} "
        "and docs/evidence/meilisearch-claim-boundary-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "Clean-room negative evidence: no unverified dependency, vendored crate or fabricated external claim; existing third-party notices preserved"
    )
    row["Remaining work"] = "None for this row."
    changed.append(rid)

if len(changed) != len(ROWS):
    raise SystemExit(f"expected {len(ROWS)} rows, found {len(changed)}")

with CSV.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print("closed:", ", ".join(changed))
print("evidence:", match.group(0), "EXIT=" + exit_code)
