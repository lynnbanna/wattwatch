import json
import math
from pathlib import Path

import httpx
import pytest
from shapely.geometry import box

from app.solar.layout import (
    Mounting,
    PanelSpec,
    footprint,
    layout_panels,
    winter_noon_sun_elevation_deg,
)
from app.solar.production import (
    SystemLosses,
    capacity_factor,
    monthly_energy_kwh,
    performance_factor,
    specific_yield_kwh_per_kwp,
    system_kwp,
)
from app.solar.pvgis import PvgisError, cache_key, fetch_resource, parse_pvcalc

FIXTURES = Path(__file__).parent / "fixtures"
BEIRUT_LAT = 33.8938
PANEL = PanelSpec(power_w=450, length_m=1.722, width_m=1.134, gap_m=0.02)


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# --- layout -------------------------------------------------------------


def test_winter_noon_sun_elevation_for_beirut():
    assert winter_noon_sun_elevation_deg(BEIRUT_LAT) == pytest.approx(32.67, abs=0.01)


def test_flat_roof_row_pitch_avoids_winter_noon_shading():
    fp = footprint(PANEL, Mounting("flat_tilted", 25, 0, "landscape"), BEIRUT_LAT)
    tilt, sun = math.radians(25), math.radians(32.6662)
    assert fp.depth_m == pytest.approx(1.134 * math.cos(tilt))
    assert fp.row_gap_m == pytest.approx(1.134 * math.sin(tilt) / math.tan(sun), rel=1e-3)
    assert fp.row_pitch_m == pytest.approx(1.775, abs=0.002)


def test_flush_mount_rows_only_need_the_panel_gap():
    fp = footprint(PANEL, Mounting("flush", 0, 0, "landscape"), BEIRUT_LAT)
    assert fp.row_gap_m == 0.02 and fp.depth_m == pytest.approx(1.134)


def test_hand_countable_roof_fits_three_by_two_panels():
    roof = box(0, 0, 3 * 1.722 + 2 * 0.02 + 0.01, 2 * 1.134 + 0.02 + 0.01)
    layout = layout_panels(roof, PANEL, Mounting("flush", 0, 0, "landscape"), BEIRUT_LAT)
    assert len(layout.panels) == 6
    assert all(roof.buffer(1e-6).contains(p) for p in layout.panels)


def test_one_millimetre_short_drops_a_column():
    roof = box(0, 0, 3 * 1.722 + 2 * 0.02 - 0.001, 1.2)
    layout = layout_panels(roof, PANEL, Mounting("flush", 0, 0, "landscape"), BEIRUT_LAT)
    assert len(layout.panels) == 2


def test_tilted_rows_fit_fewer_panels_than_flush():
    roof = box(0, 0, 10, 10)
    flat = layout_panels(roof, PANEL, Mounting("flat_tilted", 25), BEIRUT_LAT)
    flush = layout_panels(roof, PANEL, Mounting("flush", 0), BEIRUT_LAT)
    assert 0 < len(flat.panels) < len(flush.panels)
    assert flat.winter_noon_sun_elevation_deg == pytest.approx(32.67, abs=0.01)


def test_panels_avoid_holes_in_the_usable_area():
    roof = box(0, 0, 10, 10).difference(box(4, 4, 6, 6))
    layout = layout_panels(roof, PANEL, Mounting("flush", 0), BEIRUT_LAT)
    assert layout.panels and all(roof.buffer(1e-6).contains(p) for p in layout.panels)


def test_east_facing_rows_are_rotated_ninety_degrees():
    roof = box(0, 0, 10, 10)
    layout = layout_panels(roof, PANEL, Mounting("flush", 0, -90, "landscape"), BEIRUT_LAT)
    minx, miny, maxx, maxy = layout.panels[0].bounds
    # Rotated: the 1.722 m side now runs north-south.
    assert maxy - miny == pytest.approx(1.722) and maxx - minx == pytest.approx(1.134)
    assert all(roof.buffer(1e-6).contains(p) for p in layout.panels)


def test_empty_area_has_no_panels():
    assert layout_panels(box(0, 0, 1, 1), PANEL, Mounting(), BEIRUT_LAT).panels == []


# --- production: hand calculations ----------------------------------------


def test_default_performance_factor_is_the_product_of_stages():
    expected = 0.97 * 0.98 * 0.99 * 0.98 * 0.99 * 0.96
    assert performance_factor(SystemLosses()) == pytest.approx(expected)


def test_hand_calculated_system():
    kwp = system_kwp(10, 450)
    monthly = monthly_energy_kwh(kwp, [100.0] * 12, 0.9)
    annual = sum(monthly)
    assert kwp == 4.5
    assert monthly[0] == pytest.approx(405.0)
    assert annual == pytest.approx(4860.0)
    assert specific_yield_kwh_per_kwp(annual, kwp) == pytest.approx(1080.0)
    assert capacity_factor(annual, kwp) == pytest.approx(4860 / (4.5 * 8760))


def test_invalid_losses_are_rejected():
    with pytest.raises(ValueError):
        SystemLosses(soiling=1.5)
    with pytest.raises(ValueError):
        SystemLosses(inverter_efficiency=0)


def test_monthly_energy_needs_twelve_months():
    with pytest.raises(ValueError):
        monthly_energy_kwh(1.0, [1.0] * 11, 1.0)


# --- validation against PVGIS ------------------------------------------------


def test_engine_reproduces_pvgis_with_an_equivalent_total_loss():
    """PVGIS with 14% system loss == our engine on the loss-free yield with factor 0.86."""
    lossless = parse_pvcalc(fixture("pvgis_pvcalc_beirut_25s_loss0.json"))
    reference = parse_pvcalc(fixture("pvgis_pvcalc_beirut_25s_loss14.json"))
    losses = SystemLosses(0, 0, 0, 0, 0, inverter_efficiency=0.86)
    ours = monthly_energy_kwh(1.0, lossless.monthly_yield_kwh_per_kwp, performance_factor(losses))
    for mine, theirs in zip(ours, reference.monthly_yield_kwh_per_kwp, strict=True):
        assert mine == pytest.approx(theirs, abs=0.01)
    assert sum(ours) == pytest.approx(reference.annual_yield_kwh_per_kwp, abs=0.1)


def test_parse_pvcalc_reads_yield_losses_and_metadata():
    r = parse_pvcalc(fixture("pvgis_pvcalc_beirut_25s_loss0.json"))
    assert len(r.monthly_yield_kwh_per_kwp) == 12
    assert r.annual_yield_kwh_per_kwp == pytest.approx(1854.45)
    assert r.loss_temperature_irradiance_pct == pytest.approx(-8.64)
    assert r.radiation_database == "PVGIS-SARAH3" and r.years == "2005-2023"


# --- PVGIS client --------------------------------------------------------------


class Recorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, Exception):
            raise item
        return item


def ok() -> httpx.Response:
    return httpx.Response(200, json=fixture("pvgis_pvcalc_beirut_25s_loss0.json"))


def client_for(recorder: Recorder) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(recorder))


def test_fetch_uses_loss_free_one_kwp_and_caches(isolated_storage):
    rec = Recorder([ok()])
    with isolated_storage() as session, client_for(rec) as client:
        first = fetch_resource(session, 33.8938, 35.5018, 25, 0, "free", client=client)
        again = fetch_resource(session, 33.894, 35.502, 25, 0, "free", client=client)
        other = fetch_resource(session, 33.8938, 35.5018, 30, 0, "free", client=client)
    assert first == again == other
    assert len(rec.requests) == 2  # second call served from cache (same rounded key)
    params = rec.requests[0].url.params
    assert params["peakpower"] == "1" and params["loss"] == "0" and params["usehorizon"] == "1"
    assert params["lat"] == "33.89"


def test_retries_when_pvgis_is_busy(isolated_storage):
    rec = Recorder([httpx.Response(529), ok()])
    waits = []
    with isolated_storage() as session, client_for(rec) as client:
        r = fetch_resource(session, 34.43, 35.84, 25, 0, "free", client=client, sleep=waits.append)
    assert r.annual_yield_kwh_per_kwp > 0
    assert waits == [1]


def test_rejected_request_reports_pvgis_message(isolated_storage):
    rec = Recorder([httpx.Response(400, json={"message": "Location over the sea"})])
    with (
        isolated_storage() as session,
        client_for(rec) as client,
        pytest.raises(PvgisError, match="Location over the sea"),
    ):
        fetch_resource(session, 34.0, 35.0, 25, 0, "free", client=client)


def test_unreachable_pvgis_raises_after_retries(isolated_storage):
    rec = Recorder([httpx.ConnectError("down")])
    with (
        isolated_storage() as session,
        client_for(rec) as client,
        pytest.raises(PvgisError, match="could not be reached"),
    ):
        fetch_resource(session, 34.0, 35.5, 25, 0, "free", client=client, sleep=lambda s: None)
    assert len(rec.requests) == 3


def test_cache_key_rounds_to_about_a_kilometre():
    assert cache_key(33.89381, 35.50179, 25, 0, "free") == cache_key(
        33.8941, 35.5022, 25, 0, "free"
    )
