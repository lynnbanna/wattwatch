from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def _jpeg_with_gps() -> bytes:
    image = Image.new("RGB", (200, 100), (120, 120, 120))
    exif = Image.Exif()
    exif[0x8825] = {2: (33.0, 53.0, 0.0)}  # GPSInfo: latitude
    buf = BytesIO()
    image.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _analyse(data: bytes | None = None) -> dict:
    res = client.post(
        "/api/v1/roof-analysis",
        files={"file": ("roof.jpg", data or _jpeg_with_gps(), "image/jpeg")},
        data={"imagery_type": "top_down", "gsd_m": "0.15"},
    )
    assert res.status_code == 200
    return res.json()


def _uploads() -> list[Path]:
    return sorted(Path(get_settings().upload_dir).glob("*"))


def test_analysis_is_saved_and_can_be_fetched():
    created = _analyse()
    res = client.get(f"/api/v1/analyses/{created['id']}")
    assert res.status_code == 200
    record = res.json()
    assert record["result"] == created
    assert record["corrections"] is None and record["corrected"] is None
    assert record["image_url"] == f"/api/v1/analyses/{created['id']}/image"


def test_stored_image_is_png_without_metadata():
    created = _analyse()
    res = client.get(f"/api/v1/analyses/{created['id']}/image")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    stored = Image.open(BytesIO(res.content))
    assert stored.size == (200, 100)
    assert not stored.getexif()
    assert "exif" not in stored.info


def test_same_upload_reuses_one_stored_file():
    data = _jpeg_with_gps()
    _analyse(data)
    _analyse(data)
    assert len(_uploads()) == 1


def test_corrections_are_measured_with_the_analysis_scale_and_saved():
    created = _analyse()
    body = {
        "roofs": [
            {
                "label": "roof",
                "source": "added",
                "polygon_px": [[0, 0], [100, 0], [100, 80], [0, 80]],
            }
        ],
        "obstacles": [],
    }
    res = client.put(f"/api/v1/analyses/{created['id']}/corrections", json=body)
    assert res.status_code == 200
    record = res.json()
    # 100 x 80 px at 0.15 m = 15 m x 12 m = 180 m2; usable with 0.5 m setback = 14 x 11.
    assert record["corrected"]["measurements"]["roof_area_m2"] == pytest.approx(180.0)
    assert record["corrected"]["measurements"]["usable_area_m2"] == pytest.approx(154.0)
    assert record["corrections"]["roofs"][0]["source"] == "added"
    assert client.get(f"/api/v1/analyses/{created['id']}").json()["corrected"] is not None


def test_corrections_outside_the_image_are_rejected():
    created = _analyse()
    body = {
        "roofs": [{"label": "roof", "source": "added", "polygon_px": [[0, 0], [900, 0], [0, 9]]}],
        "obstacles": [],
    }
    res = client.put(f"/api/v1/analyses/{created['id']}/corrections", json=body)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_polygon"


def test_delete_removes_record_and_unshared_image():
    data = _jpeg_with_gps()
    first, second = _analyse(data), _analyse(data)
    assert client.delete(f"/api/v1/analyses/{first['id']}").status_code == 204
    assert len(_uploads()) == 1  # still used by the second analysis
    assert client.delete(f"/api/v1/analyses/{second['id']}").status_code == 204
    assert _uploads() == []
    assert client.get(f"/api/v1/analyses/{second['id']}").status_code == 404


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_unknown_ids_are_404(bad_id):
    res = client.get(f"/api/v1/analyses/{bad_id}")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "analysis_not_found"
