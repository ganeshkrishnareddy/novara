"""Evidence-gated integration: close the eight clean-room share-link rows.

Source of truth is MASTER_FEATURE_MATRIX.csv, matching the established practice
for prior batches (narrative deliverables are regenerated from that CSV).
The full-suite evidence string is read from the recorded run so the matrix can
never claim a result that was not actually produced.
"""
from pathlib import Path
import csv
import re

BASE = Path(r"D:\NOVARA\docs\FEATURE_PARITY")
CSV = BASE / "MASTER_FEATURE_MATRIX.csv"
EVIDENCE = Path(r"D:\NOVARA\docs\evidence")

ROWS = {
    "PM-023": (
        "complete: a multi-file share link respects per-item visibility; hidden documents never appear in a resolve",
        "complete: share-set create/item/visibility/revoke and public set resolve routes",
    ),
    "PM-035": (
        "complete: a verified domain serves a link slug and revoking the link frees that slug for reuse",
        "complete: domain register/verify, link slug assign/release and public domain+slug resolve routes",
    ),
    "PM-036": (
        "complete: only a domain with a matching one-time token is marked verified",
        "complete: domain verification route with hashed token comparison and fail-closed 403/404",
    ),
    "PM-037": (
        "complete: an Open Graph preview contains only owner-approved, HTML-escaped metadata",
        "complete: og save/approve routes and public preview route that hides unapproved metadata",
    ),
    "PM-043": (
        "complete: a custom password-screen message renders as escaped text without HTML injection",
        "complete: password-screen configure and public read routes with html.escape on output",
    ),
    "PM-044": (
        "complete: detectable screenshot attempts are logged locally and the mobile/OS limitation is stated honestly",
        "complete: screenshot config, public attempt logging and workspace-scoped report routes",
    ),
    "PM-046": (
        "complete: each configured watermark variable renders correctly and user text cannot inject markup",
        "complete: watermark profile config and render routes with validated variables, style and escaping",
    ),
    "PM-071": (
        "complete: room/link branding resolves default, pinned and custom modes in that precedence order",
        "complete: branding config, pinned config and effective-resolution routes with workspace scoping",
    ),
}


def read_text_any(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


exit_code = read_text_any(EVIDENCE / "t113-fullsuite-exit.txt").lstrip("\ufeff").strip()
log = read_text_any(EVIDENCE / "t113-fullsuite-20261124.txt")
match = re.search(r"(\d+) passed[^\n]*", log)
assert match, "full-suite log has no passing summary"
if exit_code != "0" or int(match.group(1)) < 859:
    raise SystemExit(f"refusing to close rows: full suite EXIT={exit_code}, summary={match.group(0)!r}")
suite = f"full suite docs/evidence/t113-fullsuite-20261124.txt EXIT={exit_code}, {match.group(0)}"

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
    backend, api = ROWS[rid]
    row["Current status"] = "VERIFIED_COMPLETE"
    row["NOVARA module"] = "share_link_presentation"
    row["NOVARA implementation location"] = "apps/api/novara_core/modules/share_link_presentation.py"
    row["Backend status"] = backend
    row["Frontend status"] = "n/a: API-level acceptance criteria; no dedicated SPA view claimed for this row"
    row["Database status"] = (
        "complete: ten additive workspace-scoped slp_* tables created by migration c8d9e0f1a2b3"
    )
    row["API status"] = api
    row["Permissions / security status"] = (
        "complete: verify_workspace on every workspace route plus require() with DOCUMENT_READ/"
        "DOCUMENT_WRITE as appropriate; hashed verification tokens are returned once, revoked links "
        "and unverified domains fail closed, and all rendered user text is HTML-escaped"
    )
    row["Integration status"] = (
        "complete: publishes share_link_presentation.changed events on NOVARA's shared event spine; "
        "reuses existing document, link and room records by reference; no Papermark source, hosted "
        "instance, paid plan configuration, outbound HTTP or external delivery contacted"
    )
    row["Tests / evidence"] = (
        "apps/api/tests/test_share_link_presentation_p2.py (8 named tests); "
        "docs/evidence/share-link-presentation-p2-20261124.md; " + suite
    )
    row["Licensing constraint"] = (
        "Clean-room implementation from documented public behaviour; no Papermark source, paid tier or hosted service copied"
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
