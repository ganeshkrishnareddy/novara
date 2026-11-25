"""Record the real connected-journey UI actions from the local desktop."""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

FFMPEG = r"C:\Users\ganes\AppData\Local\Programs\Python\Python312\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v9.0.2.exe"
OUT = Path(r'D:\NOVARA\artifacts\demo_v2_work')
RAW = OUT / '_raw_journey_v2.mp4'


def ts():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def main():
    cmd = [FFMPEG, '-y', '-hide_banner', '-loglevel', 'error',
           '-f', 'gdigrab', '-framerate', '30', '-i', 'desktop',
           '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
           '-pix_fmt', 'yuv420p', '-crf', '24', str(RAW)]
    print('START', ts(), RAW, flush=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    time.sleep(2.5)
    sys.path.insert(0, str(OUT))
    import journey
    # Run the real journey at normal speed while the desktop is being captured.
    journey.main()
    try:
        proc.stdin.write(b'q')
        proc.stdin.flush()
    except Exception:
        pass
    try:
        _, err = proc.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, err = proc.communicate()
    print('STOP', ts(), 'exit', proc.returncode, err.decode('utf-8', 'replace')[:300], flush=True)
    print('RAW_BYTES', RAW.stat().st_size if RAW.exists() else 0, flush=True)


if __name__ == '__main__':
    main()
