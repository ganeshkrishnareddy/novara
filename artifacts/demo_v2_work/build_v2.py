"""Assemble NOVARA Product Demo 2.0 from the observed connected-journey capture.

Only a locally recorded screen capture, generated cards and synthesized
narration are combined. No frame is fabricated and no claim is added beyond
the recorded UI actions.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FFMPEG = r"C:\Users\ganes\AppData\Local\Programs\Python\Python312\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v9.0.2.exe"
OUT = Path(r'D:\NOVARA\artifacts\demo_v2_work')
VIDEOS = OUT / 'videos'
VIDEOS.mkdir(parents=True, exist_ok=True)
RAW = OUT / '_raw_journey_v2.mp4'
PS1 = r'D:\NOVARA\artifacts\demo_v2_work\make_narration_v21.ps1'
EVIDENCE = OUT / 'journey_evidence.json'

W, H = 1920, 1080
BG = (247, 248, 247)
INK = (25, 45, 39)
ACCENT = (23, 107, 85)
GOLD = (196, 166, 106)
MUTED = (86, 105, 94)

NARRATION = (
    "NOVARA Product Demo two point zero, extended cut. One customer, one connected journey. "
    "This is a local recording with synthetic data. Nothing is sent outside the machine. "
    "We begin at the command centre, where every count comes from a stored workspace row. "
    "We submit one website form through the real interface. One workflow run creates a contact, a lead, "
    "a follow up task, an outreach draft and a notification, all under one correlation id. "
    "Opening the contact shows the unified timeline, with each event attached to the same identity. "
    "In Leads we qualify and then convert that exact lead using the controls on its row. "
    "In Feedback intelligence we create an audience segment from a real contact attribute, then refresh "
    "the view and confirm the stored segment count increased. "
    "In Campaign Studio we record a campaign draft for that audience, with a goal that states no outbound send. "
    "In Outreach drafts we find the draft created by intake and use the human approval control. "
    "The toast confirms the draft is approved and nothing was sent externally. "
    "In the customer inbox we open a support ticket linked to the same contact. "
    "In Tasks we complete the exact follow up created by intake. "
    "Insights is refreshed from stored rows, with no external analytics service. "
    "Finally the activity view shows the append only audit trail of these actions. "
    "This video is evidence of connected workflows in a local SQLite workspace. "
    "It is not proof that all one thousand four hundred eighty eight feature ids were individually accepted. "
    "The registry records twenty eight pass, nine hundred thirty two partial, seventy replacement verified, "
    "four hundred thirty two not applicable, twenty six not tested and zero fail."
)


def font(size, bold=False):
    name = 'segoeuib.ttf' if bold else 'segoeui.ttf'
    p = Path('C:/Windows/Fonts') / name
    return ImageFont.truetype(str(p), size) if p.exists() else ImageFont.load_default()


def card(path, lines, footer=None):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 12], fill=ACCENT)
    d.rectangle([0, 12, W, 16], fill=GOLD)
    d.rounded_rectangle([110, 130, 190, 210], radius=18, fill=INK)
    d.text((150, 170), 'N', font=font(52, True), fill=BG, anchor='mm')
    y = 300
    for text, size, bold, color in lines:
        d.text((110, y), text, font=font(size, bold), fill=color)
        y += int(size * 1.5)
    if footer:
        d.line([110, H - 190, W - 110, H - 190], fill=ACCENT, width=3)
        d.text((110, H - 160), footer, font=font(26), fill=MUTED)
    img.save(path)


def run(cmd, timeout=600):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f'ffmpeg failed: {p.stderr[-1200:]}')
    return p


def png_to_mp4(png, out, seconds):
    run([FFMPEG, '-y', '-hide_banner', '-loglevel', 'error', '-loop', '1', '-framerate', '30',
         '-i', str(png), '-t', str(seconds), '-c:v', 'libx264', '-preset', 'veryfast',
         '-pix_fmt', 'yuv420p', '-crf', '22', str(out)])


def concat(clips, out):
    lst = OUT / 'v2_list.txt'
    lst.write_text('\n'.join("file '" + str(p).replace('\\', '/') + "'" for p in clips), encoding='utf-8')
    run([FFMPEG, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
         '-i', str(lst), '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
         '-crf', '22', '-an', '-r', '30', str(out)])


def narrate(wav):
    txt = OUT / 'narration.txt'
    txt.write_text(NARRATION, encoding='utf-8')
    p = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', PS1,
                        '-TextFile', str(txt), '-OutFile', str(wav), '-Voice', 'Microsoft Zira Desktop'],
                       capture_output=True, text=True, timeout=240)
    if p.returncode != 0 or not wav.exists():
        raise RuntimeError(f'narration failed: {p.stdout[-400:]} {p.stderr[-400:]}')
    print(p.stdout.strip())


def verify(path):
    p = subprocess.run([FFMPEG, '-hide_banner', '-i', str(path), '-f', 'null', '-'],
                       capture_output=True, text=True, timeout=600)
    lines = [l.strip() for l in p.stderr.splitlines()
             if 'Duration:' in l or 'Stream #' in l or 'Video:' in l or 'Audio:' in l]
    return dict(file=str(path), bytes=path.stat().st_size, media_lines=lines[:8], decode_exit=p.returncode)


def main():
    title_png = OUT / 'title_v2.png'
    card(title_png, [
        ('NOVARA', 96, True, INK),
        ('Product Demo 2.0 — extended cut', 58, True, ACCENT),
        ('One customer. One connected journey.', 44, False, INK),
        ('Eleven real actions · one shared identity · one correlation id', 30, False, MUTED),
        ('Recorded locally with synthetic data · no external delivery', 30, False, MUTED),
    ], footer='Local QA workspace · 2026-11-25')
    end_png = OUT / 'end_v2.png'
    card(end_png, [
        ('What this demonstrated', 66, True, INK),
        ('Website form → contact + lead + task + draft + notification', 30, False, INK),
        ('Unified timeline · lead qualified and converted', 30, False, INK),
        ('Audience segment from real contact attributes', 30, False, INK),
        ('Campaign draft in that audience · human approval gate used', 30, False, INK),
        ('Linked support ticket · task completed · insights refreshed', 30, False, INK),
        ('Append-only audit trail · no email, message or provider call', 30, False, MUTED),
        ('Workflow evidence, not 1,488 individual feature acceptances', 30, False, MUTED),
    ], footer='Full evidence: docs/QA/PRODUCT_DEMO_2_EVIDENCE.md')

    title = OUT / '_title_v2.mp4'
    end = OUT / '_end_v2.mp4'
    png_to_mp4(title_png, title, 4)
    png_to_mp4(end_png, end, 16)
    silent = OUT / '_silent_v2.mp4'
    concat([title, RAW, end], silent)
    wav = OUT / '_narration_v2.wav'
    narrate(wav)
    final = VIDEOS / 'NOVARA_Product_Demo_2.0.mp4'
    run([FFMPEG, '-y', '-hide_banner', '-loglevel', 'error', '-i', str(silent), '-i', str(wav),
         '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-af', 'apad', '-shortest', str(final)])
    report = verify(final)
    report['evidence'] = json.loads(EVIDENCE.read_text(encoding='utf-8'))
    (OUT / 'demo_v2_verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
