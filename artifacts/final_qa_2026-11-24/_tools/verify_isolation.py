"""Read-only verification that synthetic QA records stayed in the QA database."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\NOVARA")
OUT = ROOT / "artifacts" / "final_qa_2026-11-24"
DBS = {
    "development": ROOT / "novara_dev.sqlite3",
    "qa": OUT / "qa_db" / "novara_qa.sqlite3",
}


def scan(path: Path):
    uri = "file:" + path.as_posix() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    markers = 0
    for table in tables:
        cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
        for col in cols:
            if col in {"email", "full_name", "name", "subject", "body"}:
                n = con.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE CAST("{col}" AS TEXT) LIKE ?',
                    ("%novara.invalid%",),
                ).fetchone()[0]
                markers += n
    con.close()
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "last_write_local": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "tables": len(tables),
        "synthetic_novara_invalid_markers": markers,
    }


def main():
    results = {name: scan(path) for name, path in DBS.items()}
    qa_started = "2026-11-24T22:40:00"
    dev_untouched = results["development"]["last_write_local"] < qa_started
    qa_contains = results["qa"]["synthetic_novara_invalid_markers"] > 0
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "qa_started_after": qa_started,
        "databases": results,
        "development_db_untouched_during_qa": dev_untouched,
        "qa_db_contains_synthetic_markers": qa_contains,
        "conclusion": "PASS" if dev_untouched and qa_contains else "REVIEW",
    }
    path = OUT / "evidence" / "data_isolation_check.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
