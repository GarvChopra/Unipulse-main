"""Generate flat GL-Bajaj-navy PWA icons without Pillow. Run once."""
import struct
import zlib
from pathlib import Path

NAVY = (11, 42, 91)  # #0b2a5b


def _png(size: int, rgb) -> bytes:
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    row = bytes((0,)) + bytes(rgb) * size          # filter byte + RGB pixels
    raw = row * size
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


out = Path(__file__).resolve().parent.parent / "static" / "icons"
out.mkdir(parents=True, exist_ok=True)
for s in (192, 512):
    (out / f"icon-{s}.png").write_bytes(_png(s, NAVY))
    print("wrote", out / f"icon-{s}.png")
