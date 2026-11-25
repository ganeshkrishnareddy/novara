"""Assemble the two final MP4 deliverables from observed screen recordings.

Adds title cards, chapter cards, SAPI narration and an explicit limitations
card. Nothing in the footage is fabricated: only locally recorded screen
capture, generated cards and synthesized narration are combined.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FFMPEG = r"C:\Users\ganes\AppData\Local\Programs\Python\Python312\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v9.0.2.exe"
OUT = Path(r"D:\NOVARA\artifacts\final_qa_2026-11-24")
VIDEOS = OUT / "videos"
CARDS = VIDEOS / "cards"
WORK = VIDEOS / "_segments"
CARDS.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)
EVIDENCE = OUT / "evidence"
PS1 = OUT / "_tools" / "make_narration.ps1"

W, H = 1920, 1080
BG = (245, 247, 245)
INK = (14, 45, 32)
ACCENT = (31, 122, 84)
MUTED = (86, 105, 94)


def font(size: int, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    p = Path("C:/Windows/Fonts") / name
    if p.exists():
        return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def card(path: Path, lines, accent_label=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 14], fill=ACCENT)
    d.rounded_rectangle([110, 150, 180, 220], radius=18, fill=INK)
    d.text((145, 185), "N", font=font(46, True), fill=BG, anchor="mm")
    y = 290
    for text, size, bold, color in lines:
        d.text((110, y), text, font=font(size, bold), fill=color)
        y += int(size * 1.55)
    if accent_label:
        d.text((110, H - 140), accent_label, font=font(30), fill=MUTED)
    d.line([110, H - 180, W - 110, H - 180], fill=ACCENT, width=3)
    img.save(path)


def run(cmd, timeout=300):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{p.stderr[-1200:]}")
    return p


def png_to_mp4(png: Path, out: Path, seconds: float):
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-framerate", "15",
         "-i", str(png), "-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", "-crf", "26", str(out)], timeout=180)


def cut(raw: Path, out: Path, start: float, duration: float):
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-ss", str(start), "-i", str(raw),
         "-t", str(duration), "-an", "-c:v", "libx264", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", "-crf", "26", str(out)], timeout=300)


def concat(clips, out: Path):
    listfile = WORK / (out.stem + "_list.txt")
    listfile.write_text("\n".join("file '" + str(p).replace("\\", "/") + "'" for p in clips),
                        encoding="utf-8")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listfile), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-crf", "26", "-an", str(out)], timeout=900)


def narrate(text: str, wav: Path, voice: str):
    txt = WORK / (wav.stem + ".txt")
    txt.write_text(text, encoding="utf-8")
    p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(PS1), "-TextFile", str(txt), "-OutFile", str(wav), "-Voice", voice],
                       capture_output=True, text=True, timeout=180)
    if p.returncode != 0 or not wav.exists():
        raise RuntimeError(f"narration failed: {p.stdout[-500:]} {p.stderr[-500:]}")
    print(p.stdout.strip())


def mux(silent: Path, wav: Path, out: Path):
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(silent), "-i", str(wav),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-af", "apad", "-shortest", str(out)],
        timeout=300)


def verify(path: Path):
    p = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path), "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    lines = [l.strip() for l in p.stderr.splitlines()
             if "Duration:" in l or "Stream #" in l or "Video:" in l or "Audio:" in l]
    return dict(file=str(path.relative_to(OUT)), bytes=path.stat().st_size,
                media_lines=lines[:8], decode_exit=p.returncode)


WALK_NARRATION = (
    "NOVARA complete Q A walkthrough. Recorded locally on twenty fourth November twenty twenty six, "
    "against a fresh isolated QA database. Every record shown is synthetic. Nothing was sent to any "
    "external provider, email address, phone number or payment system. "
    "We begin at the command center overview, with live counts from the QA workspace. "
    "Universal search, insights and the agent activity audit spine follow. "
    "Customer records, companies and leads are created and converted through the real application. "
    "Campaign Studio shows a draft and scheduled campaign; delivery was deliberately not executed. "
    "The customer inbox, document rooms, engagement analytics, tasks, projects and work item planning "
    "are then reviewed. Advanced experimentation, survey delivery, the agent center with its approval "
    "gate, notification automation, access governance and settings complete the module sweep. "
    "Two genuine frontend defects were found during browser testing and corrected in the working tree: "
    "a corrupted trailing JavaScript statement, and an access governance view that wrote to a missing "
    "element. Both were verified after correction. The full feature execution registry records one "
    "honest disposition for each of one thousand four hundred eighty eight feature IDs; a screen "
    "recording is evidence of a route or workflow, not proof that every feature passed. "
)

DEMO_NARRATION = (
    "NOVARA product demo one point zero. This is a local product walkthrough using synthetic QA data. "
    "No real customer record, message, campaign or external integration is involved. "
    "The demo opens on the command center, then shows one shared customer identity in contacts. "
    "Leads move through qualification and conversion without any outbound communication. "
    "Campaign Studio demonstrates draft and scheduling controls only; no send is performed. "
    "The customer inbox, projects and work item planning show the shared audit spine and workspace "
    "isolation. Advanced experimentation runs local statistical analysis, and the agent center shows "
    "a simulated run held at a human approval gate. "
    "The accompanying QA report records limitations openly: local SQLite rather than a production "
    "Postgres deployment, no mobile installers, no hosted external providers, and screen capture at "
    "nineteen twenty by one thousand eighty. "
)


def build(kind: str, title: str, final_name: str, narration: str, voice: str, title_seconds=5, end_seconds=7):
    meta = json.loads((EVIDENCE / f"video_{kind}_raw.json").read_text(encoding="utf-8"))
    raw = OUT / meta["raw_file"]
    prefix = kind
    title_png = CARDS / f"{prefix}_title.png"
    card(title_png, [
        ("NOVARA", 96, True, INK),
        (title, 54, True, ACCENT),
        ("Local QA evidence  ·  2026-11-24", 34, False, MUTED),
        ("Synthetic data only  ·  no external delivery", 34, False, MUTED),
        ("Recorded from the running application at 127.0.0.1:8765", 28, False, MUTED),
    ], accent_label="OpenCode QA workspace")
    end_png = CARDS / f"{prefix}_end.png"
    card(end_png, [
        ("Evidence & limitations", 72, True, INK),
        ("Screen capture: 1920x1080, 15 fps, local desktop.", 30, False, MUTED),
        ("Backend: fresh isolated SQLite QA database.", 30, False, MUTED),
        ("No real email, SMS, WhatsApp, payment or provider call.", 30, False, MUTED),
        ("Campaign delivery and hosted integrations were not executed.", 30, False, MUTED),
        ("Route visibility is not per-feature acceptance; see the registry.", 30, False, MUTED),
    ], accent_label="Full evidence: docs/QA/ and artifacts/final_qa_2026-11-24/")

    clips = []
    title_mp4 = WORK / f"{prefix}_title.mp4"
    png_to_mp4(title_png, title_mp4, title_seconds)
    clips.append(title_mp4)

    for idx, ch in enumerate(meta["chapters"], start=1):
        ch_png = CARDS / f"{prefix}_chapter_{idx:02d}.png"
        card(ch_png, [
            (f"CHAPTER {idx:02d} / {len(meta['chapters']):02d}", 34, True, ACCENT),
            (ch["label"], 66, True, INK),
            (ch["route"], 36, False, MUTED),
            ("Observed on the local NOVARA QA instance", 28, False, MUTED),
        ], accent_label=f"Timestamp {ch['start']:.0f}s in the unedited capture")
        ch_mp4 = WORK / f"{prefix}_chapter_{idx:02d}.mp4"
        png_to_mp4(ch_png, ch_mp4, 2)
        clips.append(ch_mp4)
        seg = WORK / f"{prefix}_seg_{idx:02d}.mp4"
        cut(raw, seg, ch["start"], ch["duration"])
        clips.append(seg)

    end_mp4 = WORK / f"{prefix}_end.mp4"
    png_to_mp4(end_png, end_mp4, end_seconds)
    clips.append(end_mp4)

    silent = VIDEOS / f"_{prefix}_silent.mp4"
    concat(clips, silent)
    wav = VIDEOS / f"_{prefix}_narration.wav"
    narrate(narration, wav, voice)
    final = VIDEOS / final_name
    mux(silent, wav, final)
    report = verify(final)
    (EVIDENCE / f"video_{prefix}_verification.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    build("walkthrough", "Complete QA Walkthrough", "NOVARA_Complete_QA_Walkthrough.mp4",
          WALK_NARRATION, "Microsoft David Desktop")
    build("demo", "Product Demo 1.0", "NOVARA_Product_Demo_1.0.mp4",
          DEMO_NARRATION, "Microsoft Zira Desktop")
