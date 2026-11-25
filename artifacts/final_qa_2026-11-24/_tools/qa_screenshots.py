"""Capture evidence screenshots of the visible NOVARA Chrome window.

Route changes are made through the local DevTools endpoint; PNG frames are
captured from the desktop with the bundled ffmpeg gdigrab (the built-in CDP
screenshot call timed out on this Chrome build).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, r"D:\NOVARA\artifacts\final_qa_2026-11-24\_tools")
from cdp_driver import CDP

FFMPEG = r"C:\Users\ganes\AppData\Local\Programs\Python\Python312\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v9.0.2.exe"
OUT = Path(r"D:\NOVARA\artifacts\final_qa_2026-11-24")
SHOTS = OUT / "screenshots"
LOG = OUT / "evidence" / "qa_screenshot_log.jsonl"
SHOTS.mkdir(parents=True, exist_ok=True)

ROUTES = {
    "01_dashboard": "#/dashboard",
    "02_contacts": "#/contacts",
    "03_leads": "#/leads",
    "04_campaign_studio": "#/campaigns",
    "05_customer_inbox": "#/inbox",
    "06_documents": "#/documents",
    "07_document_engagement": "#/document-engagement",
    "08_projects": "#/projects",
    "09_work_item_planning": "#/work-item-planning",
    "10_experimentation": "#/advanced-experiments",
    "11_agent_center": "#/agents",
    "12_automation": "#/notification-automation",
    "13_access_governance": "#/access-governance",
    "14_flag_governance": "#/flag-governance",
    "15_feedback_studio": "#/surveys",
    "16_settings": "#/settings",
}


def ts():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def grab(path: Path):
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "gdigrab",
           "-framerate", "1", "-i", "desktop", "-frames:v", "1", str(path)]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return done.returncode, done.stderr[:200]


def main():
    LOG.write_text("", encoding="utf-8")
    c = CDP()
    # Ensure a signed-in session.
    c.js("location.hash='#/dashboard'")
    time.sleep(1.0)
    rows = []
    for name, route in ROUTES.items():
        try:
            c.hash(route, 1.1)
        except Exception as exc:
            c = CDP()
            c.hash(route, 1.1)
        path = SHOTS / f"{name}.png"
        code, err = grab(path)
        size = path.stat().st_size if path.exists() else 0
        row = dict(ts=ts(), name=name, route=route, file=str(path.relative_to(OUT)),
                   ffmpeg_exit=code, bytes=size, stderr=err,
                   outcome="PASS" if code == 0 and size > 20000 else "FAIL")
        rows.append(row)
        print(f"[{row['outcome']:4s}] {name:24s} {size:>8d} bytes")
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    c.close()
    print("DONE", len(rows), "screenshots")


if __name__ == "__main__":
    main()
