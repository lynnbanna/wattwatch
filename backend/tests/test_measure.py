import math

import pytest
from PIL import Image

from app.measure.area import measure, to_metres
from app.measure.scale import ScaleError, scale_from_gsd, scale_from_reference
from app.vision.resample import resample_to_gsd, resampled_size


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# --- scale ---------------------------------------------------------------


def test_scale_from_reference_line():
    s = scale_from_reference((0, 0), (300, 400), 50.0)  # 500 px
    assert s.gsd_m == pytest.approx(0.1)
    assert s.source == "reference_line"
    assert "50 m reference line of 500 px" in s.description


def test_short_reference_line_is_rejected():
    with pytest.raises(ScaleError, match="at least 10 px"):
        scale_from_reference((0, 0), (5, 0), 1.0)


def test_low_altitude_drone_scale_is_accepted():
    assert scale_from_gsd(0.011).gsd_m == 0.011


@pytest.mark.parametrize("gsd", [0.001, 5.0])
def test_out_of_range_scale_is_rejected(gsd):
    with pytest.raises(ScaleError, match="outside the supported range"):
        scale_from_gsd(gsd)


# --- area: hand-calculated examples -----------------------------------


def test_rectangle_area_from_pixels():
    # 100 x 80 px at 0.1 m/px = 10 m x 8 m = 80 m2
    assert to_metres(rect(0, 0, 100, 80), 0.1).area == pytest.approx(80.0)


def test_usable_area_with_setback_and_round_obstacle_clearance():
    # Roof 10 x 8 m; 0.5 m setback -> 9 x 7 = 63 m2.
    # Obstacle 1 x 1 m well inside; 0.3 m clearance -> 1 + 4(0.3)(1) + pi(0.3)^2 m2.
    m = measure([rect(0, 0, 100, 80)], [rect(40, 30, 50, 40)], 0.1, 0.5, 0.3)
    keepout = 1 + 4 * 0.3 + math.pi * 0.09
    assert m.roof_area_m2 == pytest.approx(80.0)
    assert m.obstacle_area_m2 == pytest.approx(1.0)
    assert m.usable_area_m2 == pytest.approx(63 - keepout, rel=1e-3)
    assert m.roof_usable_areas_m2[0] == pytest.approx(m.usable_area_m2)


def test_zero_margins_leave_roof_minus_obstacles():
    m = measure([rect(0, 0, 100, 80)], [rect(40, 30, 50, 40)], 0.1, 0.0, 0.0)
    assert m.usable_area_m2 == pytest.approx(79.0)


def test_overlapping_roofs_are_not_double_counted():
    m = measure([rect(0, 0, 100, 100), rect(50, 0, 150, 100)], [], 0.1, 0.0, 0.0)
    assert m.roof_areas_m2 == [pytest.approx(100.0), pytest.approx(100.0)]
    assert m.roof_area_m2 == pytest.approx(150.0)


def test_obstacle_area_counts_only_the_part_on_a_roof():
    m = measure([rect(0, 0, 100, 100)], [rect(90, 0, 110, 10)], 0.1, 0.0, 0.0)
    assert m.obstacle_areas_m2 == [pytest.approx(2.0)]
    assert m.obstacle_area_m2 == pytest.approx(1.0)


def test_setback_larger_than_roof_leaves_no_usable_area():
    m = measure([rect(0, 0, 10, 10)], [], 0.1, 1.0, 0.0)  # 1 x 1 m roof
    assert m.usable_area_m2 == 0.0


def test_self_intersecting_polygon_is_repaired():
    bowtie = [(0, 0), (100, 100), (100, 0), (0, 100)]
    assert to_metres(bowtie, 0.1).area == pytest.approx(50.0)


def test_degenerate_polygon_has_no_area():
    assert to_metres([(0, 0), (10, 10)], 0.1).area == 0.0


# --- resampling ----------------------------------------------------------


def test_resampled_size_follows_ground_footprint():
    assert resampled_size((1000, 500), 0.3, 0.15) == (2000, 1000)
    assert resampled_size((1000, 500), 0.075, 0.15) == (500, 250)


def test_polygons_map_back_to_original_pixels():
    r = resample_to_gsd(Image.new("RGB", (1000, 500)), 0.075, 0.15)
    assert r.image.size == (500, 250)
    assert r.to_original([(250.0, 125.0)]) == [(500.0, 250.0)]


def test_matching_gsd_skips_resampling():
    image = Image.new("RGB", (10, 10))
    r = resample_to_gsd(image, 0.15, 0.15)
    assert r.image is image and (r.scale_x, r.scale_y) == (1.0, 1.0)
