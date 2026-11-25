"""Generate the NOVARA desktop icon without any external asset files.

Draws a forest-green rounded square with the gold brand accent and a gold N.
Requires Pillow (python -m pip install Pillow).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SIZE = 512
FOREST = (23, 107, 85, 255)
DEEP = (20, 84, 58, 255)
GOLD = (196, 166, 106, 255)


def build() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=96, fill=FOREST, outline=GOLD, width=14)
    draw.rounded_rectangle((34, 34, SIZE - 34, SIZE - 34), radius=76, outline=DEEP, width=6)

    # A geometric "N" made only of polygons, so no font dependency is needed.
    left, right = 150, 362
    top, bottom = 138, 374
    thickness = 44
    draw.polygon(
        [(left, bottom), (left, top), (left + thickness, top),
         (right - thickness, bottom - 84), (right - thickness, bottom), (left, bottom)],
        fill=GOLD,
    )
    draw.polygon(
        [(right - thickness, bottom), (right - thickness, top + 84),
         (right, top), (right, bottom), (right - thickness, bottom)],
        fill=GOLD,
    )
    draw.polygon(
        [(left + thickness, top), (right - thickness, top + 84),
         (right - thickness, top + 84 + thickness), (left + thickness, top + thickness)],
        fill=GOLD,
    )
    return image


def main() -> None:
    image = build()
    png = HERE / "icon.png"
    image.save(png, format="PNG")
    image.resize((256, 256), Image.Resampling.LANCZOS).save(
        HERE / "icon.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    )
    print(f"wrote {png} ({png.stat().st_size} bytes) and icon.ico")


if __name__ == "__main__":
    main()
