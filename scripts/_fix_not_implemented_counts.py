"""Correct historical/current NOT_IMPLEMENTED counts in the execution records.

The matrix source of truth after T-112 has 381 NOT_IMPLEMENTED rows (387 after
T-111; T-112 closed six of them plus two restricted rows). Earlier record edits
used a wrong 377/369 figure and are corrected here without touching the matrix.
"""
from pathlib import Path

ROOT = Path(r"D:\NOVARA\docs")


def apply(path, replacements):
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        count = text.count(old)
        if count == 0:
            raise SystemExit(f"missing expected text in {path.name}: {old!r}")
        text = text.replace(old, new)
        print(f"{path.name}: {count} x {old!r} -> {new!r}")
    path.write_text(text, encoding="utf-8")


apply(ROOT / "MASTER_TASK_BOARD.md", [
    ("377 NOT_IMPLEMENTED; complete-like 699/1,488 = 46.98%",
     "387 NOT_IMPLEMENTED; complete-like 699/1,488 = 46.98%"),
    ("369 NOT_IMPLEMENTED; complete-like 707/1,488 = 47.51%",
     "381 NOT_IMPLEMENTED; complete-like 707/1,488 = 47.51%"),
])

apply(ROOT / "TEST_RESULTS.md", [
    ("377 NOT_IMPLEMENTED; complete-like 699/1,488 = 46.98%",
     "387 NOT_IMPLEMENTED; complete-like 699/1,488 = 46.98%"),
    ("369 NOT_IMPLEMENTED; complete-like 707/1,488 = 47.51%",
     "381 NOT_IMPLEMENTED; complete-like 707/1,488 = 47.51%"),
])

apply(ROOT / "NOVARA_AUTONOMOUS_EXECUTION.md", [
    ("| NOT_IMPLEMENTED | 369 |", "| NOT_IMPLEMENTED | 381 |"),
    ("LICENSING_RESTRICTED, 377 NOT_IMPLEMENTED, 80",
     "LICENSING_RESTRICTED, 387 NOT_IMPLEMENTED, 80"),
    ("LICENSING_RESTRICTED, 369 NOT_IMPLEMENTED, 80",
     "LICENSING_RESTRICTED, 381 NOT_IMPLEMENTED, 80"),
])
