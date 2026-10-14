"""Roof, obstacle and usable areas in square metres from pixel polygons."""

from collections.abc import Sequence
from dataclasses import dataclass

from shapely import make_valid, unary_union
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

DEFAULT_EDGE_SETBACK_M = 0.5
DEFAULT_OBSTACLE_CLEARANCE_M = 0.3

PixelPolygon = Sequence[tuple[float, float]]


@dataclass(frozen=True)
class Measurements:
    roof_areas_m2: list[float]
    roof_usable_areas_m2: list[float]
    obstacle_areas_m2: list[float]
    roof_area_m2: float
    obstacle_area_m2: float
    usable_area_m2: float
    edge_setback_m: float
    obstacle_clearance_m: float


def _polygonal(geom: BaseGeometry) -> BaseGeometry:
    """Keep only area-bearing parts (make_valid can emit lines or points)."""
    if isinstance(geom, Polygon | MultiPolygon):
        return geom
    parts = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon | MultiPolygon)]
    return unary_union(parts) if parts else Polygon()


def to_metres(polygon_px: PixelPolygon, gsd_m: float) -> BaseGeometry:
    """Pixel polygon -> valid plan-view geometry in metres."""
    if len(polygon_px) < 3:
        return Polygon()
    return _polygonal(make_valid(Polygon([(x * gsd_m, y * gsd_m) for x, y in polygon_px])))


def _usable(roof: BaseGeometry, keepout: BaseGeometry, setback_m: float) -> BaseGeometry:
    inset = roof.buffer(-setback_m, join_style="mitre") if setback_m > 0 else roof
    return inset.difference(keepout)


def measure(
    roofs_px: Sequence[PixelPolygon],
    obstacles_px: Sequence[PixelPolygon],
    gsd_m: float,
    edge_setback_m: float = DEFAULT_EDGE_SETBACK_M,
    obstacle_clearance_m: float = DEFAULT_OBSTACLE_CLEARANCE_M,
) -> Measurements:
    """Usable area = roof inset by the edge setback, minus obstacles grown by the clearance.

    Totals use the union of roofs, so overlapping roof polygons are not double
    counted; obstacle area counts only the part on a roof.
    """
    roofs = [to_metres(p, gsd_m) for p in roofs_px]
    obstacles = [to_metres(p, gsd_m) for p in obstacles_px]
    roof_union = unary_union(roofs) if roofs else Polygon()
    keepout = (
        unary_union([o.buffer(obstacle_clearance_m) for o in obstacles]) if obstacles else Polygon()
    )
    obstacle_union = unary_union(obstacles) if obstacles else Polygon()
    return Measurements(
        roof_areas_m2=[r.area for r in roofs],
        roof_usable_areas_m2=[_usable(r, keepout, edge_setback_m).area for r in roofs],
        obstacle_areas_m2=[o.area for o in obstacles],
        roof_area_m2=roof_union.area,
        obstacle_area_m2=obstacle_union.intersection(roof_union).area,
        usable_area_m2=_usable(roof_union, keepout, edge_setback_m).area,
        edge_setback_m=edge_setback_m,
        obstacle_clearance_m=obstacle_clearance_m,
    )
