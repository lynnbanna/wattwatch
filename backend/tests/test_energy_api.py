import json
import math
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.solar import get_pvgis_client
from app.main import app

client = TestClient(app)
PVCALC = json.loads(
    (Path(__file__).parent / "fixtures" / "pvgis_pvcalc_beirut_25s_loss0.json").read_text()
)


def _hourly_series() -> dict:
    """A clear-sky-like day shape in UTC (sun 04:00-16:00 UTC), repeated for 365 days."""
    rows = []
    for h in range(8760):
        hod = h % 24
        p = max(math.sin(math.pi * (hod - 4) / 12), 0) * 800 if 4 <= hod <= 16 else 0.0
        rows.append({"time": "", "P": p})
    return {"outputs": {"hourly": rows}}


@pytest.fixture
def pvgis():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("seriescalc"):
            return httpx.Response(200, json=_hourly_series())
        return httpx.Response(200, json=PVCALC)

    def override():
        with httpx.Client(transport=httpx.MockTransport(handler)) as c:
            yield c

    app.dependency_overrides[get_pvgis_client] = override
    yield calls
    app.dependency_overrides.pop(get_pvgis_client, None)


def _analysis_with_design() -> str:
    buf = BytesIO()
    Image.new("RGB", (200, 100), (120, 120, 120)).save(buf, format="PNG")
    analysis_id = client.post(
        "/api/v1/roof-analysis",
        files={"file": ("roof.png", buf.getvalue(), "image/png")},
        data={"imagery_type": "top_down", "gsd_m": "0.15"},
    ).json()["id"]
    # A small roof: 40 x 40 px = 6 m x 6 m.
    roof = {"label": "roof", "source": "added", "polygon_px": [[0, 0], [40, 0], [40, 40], [0, 40]]}
    client.put(
        f"/api/v1/analyses/{analysis_id}/corrections", json={"roofs": [roof], "obstacles": []}
    )
    res = client.post(
        f"/api/v1/analyses/{analysis_id}/solar-design", json={"location": {"city": "Beirut"}}
    )
    assert res.status_code == 200
    return analysis_id


def _study(analysis_id: str, **overrides) -> httpx.Response:
    body = {
        "household": {"monthly_kwh": [100.0] * 12, "daily_shape": "evening_peak"},
        "supply": {"grid_hours_per_day": 6, "generator_kw": 2.2},
        "prices": {"grid_usd_per_kwh": 0.2, "generator_usd_per_kwh": 0.5},
        "costs": {"solar_usd_per_kwp": 600, "battery_usd_per_kwh": 250, "installation_usd": 300},
        "configurations": [
            {"name": "Solar only"},
            {"name": "Solar + battery", "battery_kwh": 5},
        ],
    }
    body.update(overrides)
    return client.post(f"/api/v1/analyses/{analysis_id}/energy-study", json=body)


def test_requires_a_solar_design_first(pvgis):
    buf = BytesIO()
    Image.new("RGB", (50, 50)).save(buf, format="PNG")
    analysis_id = client.post(
        "/api/v1/roof-analysis",
        files={"file": ("r.png", buf.getvalue(), "image/png")},
        data={"imagery_type": "top_down", "gsd_m": "0.15"},
    ).json()["id"]
    res = _study(analysis_id)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "solar_design_required"


def test_study_compares_configurations_across_three_scenarios(pvgis):
    res = _study(_analysis_with_design())
    assert res.status_code == 200
    s = res.json()
    assert [x["name"] for x in s["scenarios"]] == ["optimistic", "baseline", "conservative"]
    assert [r["configuration"]["name"] for r in s["results"]] == ["Solar only", "Solar + battery"]
    assert s["kwp"] > 0 and s["design_stale"] is False
    for config in s["results"]:
        assert [x["scenario"] for x in config["scenarios"]] == [
            "optimistic",
            "baseline",
            "conservative",
        ]
        for x in config["scenarios"]:
            e = x["energy"]
            served = (
                e["solar_to_load_kwh"]
                + e["battery_to_load_kwh"]
                + e["grid_to_load_kwh"]
                + e["generator_to_load_kwh"]
                + e["unmet_kwh"]
            )
            assert served == pytest.approx(e["demand_kwh"], abs=0.5)
        assert len(config["monthly_baseline"]["generator_to_load_kwh"]) == 12
        assert len(config["scenarios"][1]["finance"]["cumulative_usd"]) == 25


def test_battery_reduces_generator_use_and_scenarios_are_ordered(pvgis):
    s = _study(_analysis_with_design()).json()
    only, battery = (r["scenarios"][1] for r in s["results"])
    assert battery["energy"]["generator_to_load_kwh"] < only["energy"]["generator_to_load_kwh"]
    assert battery["energy"]["battery_cycles"] > 0
    npvs = [x["finance"]["npv_usd"] for x in s["results"][0]["scenarios"]]
    assert npvs[0] > npvs[1] > npvs[2]
    upfront = [x["finance"]["upfront_usd"] for x in s["results"][0]["scenarios"]]
    assert upfront[0] == pytest.approx(upfront[1] * 0.95)
    assert upfront[2] == pytest.approx(upfront[1] * 1.15)


def test_reference_cost_by_hand_with_grid_all_day(pvgis):
    s = _study(_analysis_with_design(), supply={"grid_hours_per_day": 24, "generator_kw": 0}).json()
    baseline = next(r for r in s["reference"] if r["scenario"] == "baseline")
    # 1,200 kWh a year, all from the grid at $0.20.
    assert baseline["energy_cost_usd_per_year"] == pytest.approx(240.0)
    assert baseline["energy"]["generator_to_load_kwh"] == 0


def test_battery_only_configuration_has_no_solar(pvgis):
    configs = [{"name": "Battery only", "solar": False, "battery_kwh": 5, "charge_from_grid": True}]
    s = _study(_analysis_with_design(), configurations=configs).json()
    r = s["results"][0]
    assert r["kwp"] == 0 and r["scenarios"][1]["energy"]["solar_kwh"] == 0
    assert r["scenarios"][1]["energy"]["grid_to_battery_kwh"] > 0


def test_study_is_saved_with_inputs_and_assumptions(pvgis):
    analysis_id = _analysis_with_design()
    s = _study(analysis_id).json()
    record = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert record["energy_study"]["results"] == s["results"]
    assert s["inputs"]["prices"]["generator_usd_per_kwh"] == 0.5
    text = " ".join(s["assumptions"])
    assert "6 hours a day" in text and "no export credit" in text and "$0.5/kWh" in text


def test_outline_change_after_design_marks_the_study_stale(pvgis):
    analysis_id = _analysis_with_design()
    roof = {"label": "roof", "source": "added", "polygon_px": [[0, 0], [60, 0], [60, 60], [0, 60]]}
    client.put(
        f"/api/v1/analyses/{analysis_id}/corrections", json={"roofs": [roof], "obstacles": []}
    )
    s = _study(analysis_id).json()
    assert s["design_stale"] is True
    assert "earlier roof outlines" in s["limitations"][0]


@pytest.mark.parametrize(
    "override",
    [
        {"configurations": [{"name": "A"}, {"name": "A"}]},
        {"configurations": []},
        {"prices": {"grid_usd_per_kwh": 0.2}},
        {"household": {"monthly_kwh": [100] * 11}},
        {"supply": {"grid_hours_per_day": 30, "generator_kw": 1}},
    ],
    ids=["duplicate-names", "no-configs", "missing-generator-price", "eleven-months", "30-hours"],
)
def test_invalid_requests_are_rejected(pvgis, override):
    res = _study(_analysis_with_design(), **override)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_request"
