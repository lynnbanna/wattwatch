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


TOP_DOWN_AT_MODEL_SCALE = {"imagery_type": "top_down", "gsd_m": "0.15"}


def _post(
    data: bytes,
    filename: str = "roof.png",
    content_type: str = "image/png",
    form: dict | None = None,
):
    return client.post(
        "/api/v1/roof-analysis",
        files={"file": (filename, data, content_type)},
        data=TOP_DOWN_AT_MODEL_SCALE if form is None else form,
    )


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_analysis_returns_areas_with_assumptions(fmt):
    res = _post(_image_bytes(fmt))
    assert res.status_code == 200
    body = res.json()
    assert body["model"] == {"name": "stub", "version": "0.1.0", "is_stub": True, "gsd_m": 0.15}
    assert body["image"] == {"width_px": 200, "height_px": 100}
    assert body["scale"] == {
        "gsd_m": 0.15,
        "source": "gsd",
        "model_gsd_m": 0.15,
        "resample_factor": 1.0,
    }
    roof, obstacle = body["roofs"][0], body["obstacles"][0]
    # Stub roof: central 120 x 60 px = 18 m x 9 m; tank 8 x 8 px = 1.2 m x 1.2 m.
    assert roof["area_m2"] == pytest.approx(162.0)
    assert obstacle["area_m2"] == pytest.approx(1.44)
    assert 0 < roof["usable_area_m2"] < 162.0
    assert "model_score" in roof and "confidence" not in roof
    assert body["measurements"]["roof_area_m2"] == pytest.approx(162.0)
    assert body["measurements"]["edge_setback_m"] == 0.5
    assert "not the probability" in body["model_score_note"]
    assert any("Scale: 0.15 m per pixel, as entered" in a for a in body["assumptions"])
    assert any("Stub model" in note for note in body["limitations"])


def test_coarse_image_is_enlarged_and_flagged():
    res = _post(_image_bytes("PNG"), form={"imagery_type": "top_down", "gsd_m": "0.3"})
    body = res.json()
    assert body["scale"]["resample_factor"] == 2.0
    # Same pixel outline in the original image, but each pixel is 0.3 m.
    assert body["roofs"][0]["polygon_px"][0] == [40.0, 20.0]
    assert body["roofs"][0]["area_m2"] == pytest.approx(648.0)
    assert "coarser than the model" in body["limitations"][0]


def test_scale_from_reference_line():
    form = {
        "imagery_type": "top_down",
        "reference_x1": "0",
        "reference_y1": "50",
        "reference_x2": "100",
        "reference_y2": "50",
        "reference_length_m": "15",
    }
    body = _post(_image_bytes("PNG"), form=form).json()
    assert body["scale"]["source"] == "reference_line"
    assert body["scale"]["gsd_m"] == pytest.approx(0.15)


def test_oblique_photos_are_refused_with_explanation():
    res = _post(_image_bytes("PNG"), form={"imagery_type": "oblique_or_ground", "gsd_m": "0.15"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "unsupported_imagery"


@pytest.mark.parametrize(
    "form",
    [
        {"imagery_type": "top_down"},
        {"imagery_type": "top_down", "gsd_m": "0.15", "reference_length_m": "10"},
        {"imagery_type": "top_down", "reference_length_m": "10"},
        {
            "imagery_type": "top_down",
            "reference_x1": "0",
            "reference_y1": "0",
            "reference_x2": "900",
            "reference_y2": "0",
            "reference_length_m": "10",
        },
        {"imagery_type": "top_down", "gsd_m": "9"},
    ],
    ids=["missing", "both", "incomplete-line", "line-outside-image", "out-of-range"],
)
def test_invalid_scale_is_rejected(form):
    res = _post(_image_bytes("PNG"), form=form)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_scale"


def test_rejects_images_too_large_at_model_resolution(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_image_pixels", 50_000)
    res = _post(_image_bytes("PNG"), form={"imagery_type": "top_down", "gsd_m": "1.0"})
    assert res.status_code == 413
    assert "Crop it" in res.json()["error"]["message"]


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
        assert 0 <= detection.score <= 1
        for x, y in detection.polygon:
            assert 0 <= x <= width and 0 <= y <= height


def test_area_error_note_depends_on_the_model():
    from app.api.v1.roof_analysis import AREA_ERROR_BY_MODEL

    body = _post(_image_bytes("PNG")).json()
    assert any("not been measured for this model" in n for n in body["limitations"])
    assert "within 7%" in AREA_ERROR_BY_MODEL[("roof-unet-r18", "0.1.0")]
