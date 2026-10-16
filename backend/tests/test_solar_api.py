import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.solar import get_pvgis_client
from app.main import app
from app.solar.production import SystemLosses, performance_factor

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "pvgis_pvcalc_beirut_25s_loss0.json").read_text()
)
client = TestClient(app)


@pytest.fixture
def pvgis():
    """Fake PVGIS: records requests; responds with the recorded Beirut response or `status`."""
    state = {"requests": [], "status": 200}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        if state["status"] != 200:
            return httpx.Response(state["status"], json={"message": "Location over the sea"})
        return httpx.Response(200, json=FIXTURE)

    def override():
        with httpx.Client(transport=httpx.MockTransport(handler)) as c:
            yield c

    app.dependency_overrides[get_pvgis_client] = override
    yield state
    app.dependency_overrides.pop(get_pvgis_client, None)


def _analysis(size=(200, 100)) -> str:
    buf = BytesIO()
    Image.new("RGB", size, (120, 120, 120)).save(buf, format="PNG")
    res = client.post(
        "/api/v1/roof-analysis",
        files={"file": ("roof.png", buf.getvalue(), "image/png")},
        data={"imagery_type": "top_down", "gsd_m": "0.15"},
    )
    return res.json()["id"]


def _design(analysis_id: str, **body) -> httpx.Response:
    body.setdefault("location", {"city": "Beirut"})
    return client.post(f"/api/v1/analyses/{analysis_id}/solar-design", json=body)


def _clean_roof(analysis_id: str) -> None:
    """Replace outlines with one 200 x 100 px roof (30 m x 15 m at 0.15 m/px), no obstacles."""
    roof = {
        "label": "roof",
        "source": "added",
        "polygon_px": [[0, 0], [200, 0], [200, 100], [0, 100]],
    }
    client.put(
        f"/api/v1/analyses/{analysis_id}/corrections", json={"roofs": [roof], "obstacles": []}
    )


def test_hand_countable_flat_roof_design(pvgis):
    analysis_id = _analysis()
    _clean_roof(analysis_id)
    res = _design(analysis_id)
    assert res.status_code == 200
    d = res.json()
    # Usable 29 x 14 m: 16 columns of 1.742 m; 8 rows at 1.775 m pitch (last row 1.028 m deep).
    assert d["layout"]["panel_count"] == 128
    assert d["layout"]["kwp"] == pytest.approx(57.6)
    assert d["layout"]["usable_area_m2"] == pytest.approx(29 * 14)
    factor = performance_factor(SystemLosses())
    assert d["production"]["annual_kwh"] == pytest.approx(57.6 * 1854.45 * factor, rel=1e-3)
    assert len(d["production"]["monthly_kwh"]) == 12
    assert d["production"]["performance_factor"] == pytest.approx(factor, abs=1e-4)
    assert d["uses_corrections"] is True
    assert d["resource"]["attribution"].startswith("PVGIS ©")
    assert any("Beirut (city centre" in a for a in d["assumptions"])
    assert any("winter-solstice noon" in a for a in d["assumptions"])
    params = pvgis["requests"][0].url.params
    assert params["mountingplace"] == "free" and float(params["angle"]) == 25


def test_panels_are_returned_in_image_pixels_inside_the_image(pvgis):
    analysis_id = _analysis()
    _clean_roof(analysis_id)
    panels = _design(analysis_id).json()["layout"]["panels_px"]
    xs = [x for p in panels for x, _ in p]
    ys = [y for p in panels for _, y in p]
    assert min(xs) >= 0 and max(xs) <= 200 and min(ys) >= 0 and max(ys) <= 100
    assert all(len(p) == 4 for p in panels)


def test_design_is_saved_and_flags_outline_changes(pvgis):
    analysis_id = _analysis()
    design = _design(analysis_id).json()
    record = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert record["solar_design"]["layout"] == design["layout"]
    assert record["outline_hash"] == design["outline_hash"]
    assert design["uses_corrections"] is False

    _clean_roof(analysis_id)
    record = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert record["outline_hash"] != record["solar_design"]["outline_hash"]


def test_flush_mount_uses_building_mounting_and_notes_user_inputs(pvgis):
    analysis_id = _analysis()
    d = _design(analysis_id, mounting={"kind": "flush", "tilt_deg": 30, "azimuth_deg": -90}).json()
    assert pvgis["requests"][0].url.params["mountingplace"] == "building"
    assert "facing east" in " ".join(d["assumptions"])
    assert "cannot measure them" in d["limitations"][0]


def test_coordinates_are_rounded_and_reported(pvgis):
    d = _design(_analysis(), location={"lat": 34.43671, "lon": 35.84972}).json()
    assert d["location"] == {"name": None, "lat": 34.44, "lon": 35.85}


def test_too_small_roof_gives_zero_panels_with_explanation(pvgis):
    d = _design(_analysis(size=(20, 10))).json()
    assert d["layout"]["panel_count"] == 0
    assert d["production"]["annual_kwh"] == 0
    assert "No whole panel fits" in d["limitations"][0]


@pytest.mark.parametrize(
    "location",
    [{"city": "Atlantis"}, {"city": "Beirut", "lat": 33.9, "lon": 35.5}, {"lat": 33.9}, {}],
    ids=["unknown-city", "both", "lat-only", "empty"],
)
def test_invalid_locations_are_rejected(pvgis, location):
    res = _design(_analysis(), location=location)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_request"


def test_pvgis_failure_is_reported_as_unavailable(pvgis):
    pvgis["status"] = 400
    res = _design(_analysis())
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "solar_data_unavailable"
    assert "Location over the sea" in res.json()["error"]["message"]


def test_unknown_analysis_is_404(pvgis):
    res = _design("00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
