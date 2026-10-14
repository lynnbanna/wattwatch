from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.v1.roof_analysis import PLAN_VIEW_ASSUMPTION
from app.core.errors import ApiError
from app.measure.area import DEFAULT_EDGE_SETBACK_M, DEFAULT_OBSTACLE_CLEARANCE_M, measure
from app.measure.scale import MAX_GSD_M, MIN_GSD_M

router = APIRouter(tags=["measurements"])

MAX_REGIONS = 500
MAX_VERTICES = 2000

Polygon = list[tuple[float, float]]


class RoofMeasurementsRequest(BaseModel):
    gsd_m: float = Field(ge=MIN_GSD_M, le=MAX_GSD_M)
    roofs: list[Polygon] = Field(max_length=MAX_REGIONS)
    obstacles: list[Polygon] = Field(max_length=MAX_REGIONS)
    edge_setback_m: float = Field(DEFAULT_EDGE_SETBACK_M, ge=0, le=5)
    obstacle_clearance_m: float = Field(DEFAULT_OBSTACLE_CLEARANCE_M, ge=0, le=3)


class RegionAreas(BaseModel):
    area_m2: float
    usable_area_m2: float | None = None


class MeasurementTotals(BaseModel):
    roof_area_m2: float
    obstacle_area_m2: float
    usable_area_m2: float
    edge_setback_m: float
    obstacle_clearance_m: float


class RoofMeasurementsResponse(BaseModel):
    roofs: list[RegionAreas]
    obstacles: list[RegionAreas]
    measurements: MeasurementTotals
    assumptions: list[str]


@router.post("/roof-measurements", response_model=RoofMeasurementsResponse)
def measure_roofs(body: RoofMeasurementsRequest) -> RoofMeasurementsResponse:
    """Recompute areas for outlines in image pixels, e.g. after manual correction.

    Uses the same geometry as /roof-analysis, so corrected and predicted outlines
    are measured identically.
    """
    for polygon in [*body.roofs, *body.obstacles]:
        if not 3 <= len(polygon) <= MAX_VERTICES:
            raise ApiError(
                422,
                "invalid_polygon",
                f"Each outline needs between 3 and {MAX_VERTICES} points.",
            )
    m = measure(
        body.roofs, body.obstacles, body.gsd_m, body.edge_setback_m, body.obstacle_clearance_m
    )
    return RoofMeasurementsResponse(
        roofs=[
            RegionAreas(area_m2=round(a, 2), usable_area_m2=round(u, 2))
            for a, u in zip(m.roof_areas_m2, m.roof_usable_areas_m2, strict=True)
        ],
        obstacles=[RegionAreas(area_m2=round(a, 2)) for a in m.obstacle_areas_m2],
        measurements=MeasurementTotals(
            roof_area_m2=round(m.roof_area_m2, 2),
            obstacle_area_m2=round(m.obstacle_area_m2, 2),
            usable_area_m2=round(m.usable_area_m2, 2),
            edge_setback_m=body.edge_setback_m,
            obstacle_clearance_m=body.obstacle_clearance_m,
        ),
        assumptions=[
            f"Scale: {body.gsd_m:.3g} m per pixel.",
            f"Usable area keeps {body.edge_setback_m:g} m from roof edges and "
            f"{body.obstacle_clearance_m:g} m around obstacles.",
            PLAN_VIEW_ASSUMPTION,
        ],
    )
