"""Generate UNIFIX PWA / Android launcher icons from the GL Bajaj crest.

Outputs (static/icons/):
    icon-192.png, icon-512.png          — "any" purpose, full-bleed navy + crest
    maskable-192.png, maskable-512.png  — "maskable", crest inside the ~80% safe zone

Run once (or whenever the source logo changes):  python scripts/make_icons.py
"""
from pathlib import Path

from PIL import Image

NAVY = (14, 47, 92)          # #0e2f5c — matches the app + manifest theme_color
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "static" / "img" / "glb-logo.webp"
OUT = ROOT / "static" / "icons"


def _canvas(size: int, logo: Image.Image, logo_frac: float) -> Image.Image:
    img = Image.new("RGB", (size, size), NAVY)
    target = int(size * logo_frac)
    l = logo.copy()
    l.thumbnail((target, target), Image.LANCZOS)
    x = (size - l.width) // 2
    y = (size - l.height) // 2
    img.paste(l, (x, y), l if l.mode == "RGBA" else None)
    return img


def _drop_white(img: Image.Image, thresh: int = 238) -> Image.Image:
    """Make the near-white studio background of the source crest transparent so
    it sits on the navy tile cleanly. A logo that already has an alpha channel
    is left alone."""
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r >= thresh and g >= thresh and b >= thresh:
                px[x, y] = (r, g, b, 0)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    logo = _drop_white(Image.open(SRC))
    for size in (192, 512):
        _canvas(size, logo, 0.66).save(OUT / f"icon-{size}.png")
        # maskable: keep the crest within the 80% safe circle
        _canvas(size, logo, 0.52).save(OUT / f"maskable-{size}.png")
        print("wrote", OUT / f"icon-{size}.png", "+ maskable")


if __name__ == "__main__":
    main()
