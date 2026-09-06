"""Phase 2 — evidence photos must be downscaled before storage so they don't
bloat the database (passthrough mode) or the upload request (16 MB cap)."""
import base64
import io

from PIL import Image

from services import storage_service


def _b64(img: Image.Image, fmt="PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


def _decode(data_url: str) -> bytes:
    return base64.b64decode(data_url.split(",", 1)[1])


def test_oversized_photo_is_downscaled():
    big = Image.new("RGB", (4000, 3000), (120, 90, 60))
    original = _b64(big)
    out = storage_service.upload_image(original, "image/png")
    assert out.startswith("data:")
    img = Image.open(io.BytesIO(_decode(out)))
    assert max(img.size) <= storage_service.MAX_EDGE
    assert len(_decode(out)) < len(base64.b64decode(original)) / 2


def test_small_photo_stays_small():
    small = Image.new("RGB", (400, 300), (10, 20, 30))
    out = storage_service.upload_image(_b64(small), "image/png")
    img = Image.open(io.BytesIO(_decode(out)))
    assert img.size == (400, 300)


def test_empty_input_returns_empty():
    assert storage_service.upload_image("", "image/jpeg") == ""


def test_garbage_input_does_not_crash():
    out = storage_service.upload_image("not-valid-base64-!!!", "image/jpeg")
    assert isinstance(out, str)
