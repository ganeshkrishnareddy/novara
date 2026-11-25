"""Record a live NOVARA UI walkthrough from the desktop with ffmpeg gdigrab.

Usage: python record_raw.py walkthrough|demo
Drives only the local QA instance through its DevTools endpoint. The raw MP4
is an unedited capture of what was actually on screen.
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
VIDEOS = OUT / "videos"
VIDEOS.mkdir(parents=True, exist_ok=True)
EVIDENCE = OUT / "evidence"

WALKTHROUGH = [
    ("Overview / Command Center", "#/dashboard", 8),
    ("Universal search", "#/search", 6),
    ("Insights", "#/insights", 6),
    ("Agent activity / audit spine", "#/activity", 6),
    ("Contacts / CRM", "#/contacts", 8),
    ("Companies", "#/companies", 5),
    ("Leads", "#/leads", 7),
    ("Sales pipeline", "#/deals", 6),
    ("Campaign Studio", "#/campaigns", 8),
    ("Customer inbox", "#/inbox", 8),
    ("Documents", "#/documents", 7),
    ("Document engagement", "#/document-engagement", 7),
    ("Tasks", "#/tasks", 5),
    ("Projects", "#/projects", 8),
    ("Work-item planning", "#/work-item-planning", 7),
    ("Advanced experimentation", "#/advanced-experiments", 8),
    ("Survey delivery", "#/survey-delivery", 6),
    ("Agent center", "#/agents", 7),
    ("Notification automation", "#/notification-automation", 7),
    ("Access governance", "#/access-governance", 7),
    ("Settings", "#/settings", 5),
]

DEMO = [
    ("One connected workspace", "#/dashboard", 9),
    ("Customer records", "#/contacts", 9),
    ("Leads and conversion", "#/leads", 9),
    ("Campaign Studio", "#/campaigns", 9),
    ("Customer inbox", "#/inbox", 9),
    ("Projects and work items", "#/projects", 9),
    ("Experimentation", "#/advanced-experiments", 9),
    ("Agent center with approval gate", "#/agents", 9),
]


def ts():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "walkthrough"
    chapters = WALKTHROUGH if kind == "walkthrough" else DEMO
    raw = VIDEOS / f"_raw_{kind}.mp4"
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "gdigrab", "-framerate", "15", "-i", "desktop",
           "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
           "-pix_fmt", "yuv420p", "-crf", "26", str(raw)]
    print("START", ts(), raw)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    time.sleep(2.0)  # let the encoder establish the output file
    c = CDP()
    c.js("location.hash='#/dashboard'")
    time.sleep(1.0)

    marks = []
    elapsed = 3.0  # approx from process start to first route
    for label, route, seconds in chapters:
        c.hash(route, 0.5)
        marks.append(dict(label=label, route=route, start=round(elapsed, 2),
                          end=round(elapsed + seconds, 2), duration=seconds))
        print(f"  {elapsed:6.1f}s {label}")
        time.sleep(seconds)
        elapsed += seconds
    c.close()

    try:
        proc.stdin.write(b"q")
        proc.stdin.flush()
    except Exception:
        pass
    try:
        _, err = proc.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, err = proc.communicate()
    print("STOP", ts(), "exit", proc.returncode, err.decode("utf-8", "replace")[:300])

    meta = dict(kind=kind, recorded_at=ts(), source="local NOVARA QA instance",
                synthetic_data=True, chapters=marks,
                raw_file=str(raw.relative_to(OUT)), raw_bytes=raw.stat().st_size if raw.exists() else 0)
    path = EVIDENCE / f"video_{kind}_raw.json"
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("META", path)


if __name__ == "__main__":
    main()
