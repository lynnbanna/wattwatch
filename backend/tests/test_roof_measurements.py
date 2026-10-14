import math

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def test_measures_corrected_outlines_like_the_analysis():
    body = {
        "gsd_m": 0.1,
        "roofs": [rect(0, 0, 100, 80)],
        "obstacles": [rect(40, 30, 50, 40)],
        "edge_setback_m": 0.5,
        "obstacle_clearance_m": 0.3,
    }
    res = client.post("/api/v1/roof-measurements", json=body)
    assert res.status_code == 200
    data = res.json()
    keepout = 1 + 4 * 0.3 + math.pi * 0.09
    assert data["roofs"] == [
        {"area_m2": 80.0, "usable_area_m2": pytest.approx(63 - keepout, abs=0.01)}
    ]
    assert data["obstacles"] == [{"area_m2": 1.0, "usable_area_m2": None}]
    assert data["measurements"]["usable_area_m2"] == pytest.approx(63 - keepout, abs=0.01)
    assert any("0.1 m per pixel" in a for a in data["assumptions"])


def test_defaults_apply_and_empty_lists_are_allowed():
    res = client.post(
        "/api/v1/roof-measurements", json={"gsd_m": 0.15, "roofs": [], "obstacles": []}
    )
    assert res.status_code == 200
    m = res.json()["measurements"]
    assert m["roof_area_m2"] == 0 and m["edge_setback_m"] == 0.5


def test_rejects_polygons_with_too_few_points():
    body = {"gsd_m": 0.15, "roofs": [[[0, 0], [1, 1]]], "obstacles": []}
    res = client.post("/api/v1/roof-measurements", json=body)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_polygon"


@pytest.mark.parametrize("gsd", [0, 5])
def test_rejects_out_of_range_scale(gsd):
    res = client.post(
        "/api/v1/roof-measurements", json={"gsd_m": gsd, "roofs": [], "obstacles": []}
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_request"
