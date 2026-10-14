"""Fit solar panels into the usable roof area.

Coordinates are plan-view metres with x pointing east and y pointing south, which is
what image pixels times the ground sampling distance give for a north-up image.
Azimuth follows PVGIS: 0 = facing south, -90 = east, 90 = west.
"""

import math
from dataclasses import dataclass
from typing import Literal

from shapely import affinity, prepared
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry

SOLSTICE_DECLINATION_DEG = 23.44
OFFSET_STEPS = 4  # grid offsets tried per axis; the best of 16 placements is kept


@dataclass(frozen=True)
class PanelSpec:
    power_w: float = 450.0
    length_m: float = 1.722
    width_m: float = 1.134
    gap_m: float = 0.02


@dataclass(frozen=True)
class Mounting:
    kind: Literal["flat_tilted", "flush"] = "flat_tilted"
    tilt_deg: float = 25.0
    azimuth_deg: float = 0.0
    orientation: Literal["landscape", "portrait"] = "landscape"


@dataclass(frozen=True)
class Footprint:
    across_m: float  # panel size along the row, horizontal
    depth_m: float  # plan-view depth of one tilted panel
    row_pitch_m: float  # distance between the fronts of consecutive rows
    row_gap_m: float  # free space between rows


@dataclass(frozen=True)
class Layout:
    panels: list[Polygon]
    footprint: Footprint
    winter_noon_sun_elevation_deg: float | None


def winter_noon_sun_elevation_deg(latitude_deg: float) -> float:
    """Sun elevation at solar noon on the winter solstice (lowest noon sun of the year)."""
    return 90.0 - abs(latitude_deg) - SOLSTICE_DECLINATION_DEG


def footprint(panel: PanelSpec, mounting: Mounting, latitude_deg: float) -> Footprint:
    """Plan-view size of a panel and the row pitch.

    Flat roofs: rows are spaced so they do not shade each other at solar noon on the
    winter solstice. Flush mounting: panels lie in the roof plane, rows touch (plus gap).
    """
    if mounting.orientation == "landscape":
        across, slope = panel.length_m, panel.width_m
    else:
        across, slope = panel.width_m, panel.length_m
    tilt = math.radians(mounting.tilt_deg)
    depth = slope * math.cos(tilt)
    if mounting.kind == "flat_tilted":
        elevation = winter_noon_sun_elevation_deg(latitude_deg)
        if elevation <= 5:
            raise ValueError("Winter sun is too low at this latitude for row spacing")
        shadow = slope * math.sin(tilt) / math.tan(math.radians(elevation))
        row_gap = max(shadow, panel.gap_m)
    else:
        row_gap = panel.gap_m
    return Footprint(across_m=across, depth_m=depth, row_pitch_m=depth + row_gap, row_gap_m=row_gap)


def _grid(area: BaseGeometry, fp: Footprint, gap_m: float) -> list[Polygon]:
    minx, miny, maxx, maxy = area.bounds
    step_x = fp.across_m + gap_m
    test = prepared.prep(area)
    best: list[Polygon] = []
    for i in range(OFFSET_STEPS):
        for j in range(OFFSET_STEPS):
            x0 = minx + step_x * i / OFFSET_STEPS
            y0 = miny + fp.row_pitch_m * j / OFFSET_STEPS
            placed = []
            y = y0
            while y + fp.depth_m <= maxy + 1e-9:
                x = x0
                while x + fp.across_m <= maxx + 1e-9:
                    cell = box(x, y, x + fp.across_m, y + fp.depth_m)
                    if test.contains(cell):
                        placed.append(cell)
                    x += step_x
                y += fp.row_pitch_m
            if len(placed) > len(best):
                best = placed
    return best


def layout_panels(
    usable: BaseGeometry, panel: PanelSpec, mounting: Mounting, latitude_deg: float
) -> Layout:
    """Place as many whole panels as fit inside `usable`, rows facing the azimuth."""
    fp = footprint(panel, mounting, latitude_deg)
    elevation = (
        winter_noon_sun_elevation_deg(latitude_deg) if mounting.kind == "flat_tilted" else None
    )
    if usable.is_empty:
        return Layout([], fp, elevation)
    # Rotate so panels face +y (south), pack an axis-aligned grid, rotate back.
    turned = affinity.rotate(usable, -mounting.azimuth_deg, origin=(0, 0))
    cells = _grid(turned, fp, panel.gap_m)
    panels = [affinity.rotate(c, mounting.azimuth_deg, origin=(0, 0)) for c in cells]
    return Layout(panels, fp, elevation)
