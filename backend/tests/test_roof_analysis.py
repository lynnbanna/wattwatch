from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.main import app
from app.vision.models import StubRoofModel

client = TestClient(app)


def _image_bytes(fmt: str, size: tuple[int, int] = (200, 100)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, (120, 120, 120)).save(buf, format=fmt)
    return buf.getvalue()


def _post(data: bytes, filename: str = "roof.png", content_type: str = "image/png"):
    return client.post("/api/v1/roof-analysis", files={"file": (filename, data, content_type)})


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_analysis_returns_pixel_polygons_with_limitations(fmt):
    res = _post(_image_bytes(fmt))
    assert res.status_code == 200
    body = res.json()
    assert body["model"] == {"name": "stub", "version": "0.1.0", "is_stub": True}
    assert body["image"] == {"width_px": 200, "height_px": 100}
    assert body["roofs"][0]["label"] == "roof"
    assert body["obstacles"][0]["label"] == "water_tank"
    assert any("pixels" in note for note in body["limitations"])
    assert any("Stub model" in note for note in body["limitations"])


def test_declared_content_type_is_not_trusted():
    res = _post(b"not an image at all", content_type="image/png")
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "unsupported_file_type"


def test_rejects_formats_other_than_png_and_jpeg():
    res = _post(_image_bytes("GIF"), filename="roof.gif", content_type="image/gif")
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "unsupported_file_type"


def test_rejects_files_over_upload_limit(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 100)
    res = _post(_image_bytes("PNG"))
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "file_too_large"


def test_rejects_images_over_pixel_limit(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_image_pixels", 10_000)
    res = _post(_image_bytes("PNG", size=(200, 100)))
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "image_too_large"


def test_rejects_truncated_image():
    res = _post(_image_bytes("PNG")[:-40])
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "invalid_image"


def test_missing_file_uses_standard_error_shape():
    res = client.post("/api/v1/roof-analysis")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_request"


def test_stub_polygons_lie_inside_the_image():
    width, height = 640, 480
    prediction = StubRoofModel().predict(Image.new("RGB", (width, height)))
    for detection in prediction.roofs + prediction.obstacles:
        assert 0 <= detection.confidence <= 1
        for x, y in detection.polygon:
            assert 0 <= x <= width and 0 <= y <= height
