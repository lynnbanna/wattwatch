"""Saved analyses: fetch, save corrections, serve the stored image, delete.

There are no user accounts yet (Week 6): anyone with an analysis id can open it,
so ids are random UUIDs and are never listed.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.v1.deps import SessionDep, load_analysis
from app.api.v1.roof_analysis import RoofAnalysisResponse
from app.api.v1.roof_measurements import (
    MAX_REGIONS,
    MAX_VERTICES,
    MeasurementTotals,
    RegionAreas,
)
from app.api.v1.solar import SolarDesign
from app.core.errors import ApiError
from app.measure.area import measure
from app.models import Analysis
from app.outlines import current_outlines, outline_hash
from app.storage import delete_image, image_path

router = APIRouter(prefix="/analyses", tags=["analyses"])

EDGE_TOLERANCE_PX = 1.0


class CorrectedRegion(BaseModel):
    label: str = Field(max_length=40)
    source: Literal["model", "edited", "added"]
    model_score: float | None = None
    polygon_px: list[tuple[float, float]] = Field(min_length=3, max_length=MAX_VERTICES)


class Corrections(BaseModel):
    roofs: list[CorrectedRegion] = Field(max_length=MAX_REGIONS)
    obstacles: list[CorrectedRegion] = Field(max_length=MAX_REGIONS)


class CorrectedAreas(BaseModel):
    roofs: list[RegionAreas]
    obstacles: list[RegionAreas]
    measurements: MeasurementTotals


class AnalysisRecord(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    image_url: str
    result: RoofAnalysisResponse
    corrections: Corrections | None
    corrected: CorrectedAreas | None
    outline_hash: str
    solar_design: SolarDesign | None


def _record(a: Analysis) -> AnalysisRecord:
    roofs, obstacles, _ = current_outlines(a)
    return AnalysisRecord(
        id=a.id,
        created_at=a.created_at,
        updated_at=a.updated_at,
        image_url=f"/api/v1/analyses/{a.id}/image",
        result=RoofAnalysisResponse.model_validate(a.result),
        corrections=Corrections.model_validate(a.corrections) if a.corrections else None,
        corrected=(
            CorrectedAreas.model_validate(a.corrected_measurements)
            if a.corrected_measurements
            else None
        ),
        outline_hash=outline_hash(roofs, obstacles),
        solar_design=SolarDesign.model_validate(a.solar_design) if a.solar_design else None,
    )


@router.get("/{analysis_id}", response_model=AnalysisRecord)
def get_analysis(analysis_id: str, session: SessionDep) -> AnalysisRecord:
    return _record(load_analysis(session, analysis_id))


@router.get("/{analysis_id}/image", response_class=FileResponse)
def get_analysis_image(analysis_id: str, session: SessionDep) -> FileResponse:
    analysis = load_analysis(session, analysis_id)
    path = image_path(analysis.image_key)
    if not path.is_file():
        raise ApiError(404, "image_not_found", "The stored image for this analysis is missing.")
    return FileResponse(
        path, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"}
    )


@router.put("/{analysis_id}/corrections", response_model=AnalysisRecord)
def save_corrections(analysis_id: str, body: Corrections, session: SessionDep) -> AnalysisRecord:
    """Replace the corrected outlines; areas use the analysis's own scale and margins."""
    analysis = load_analysis(session, analysis_id)
    result = analysis.result
    width, height = result["image"]["width_px"], result["image"]["height_px"]
    for region in [*body.roofs, *body.obstacles]:
        if not all(
            -EDGE_TOLERANCE_PX <= x <= width + EDGE_TOLERANCE_PX
            and -EDGE_TOLERANCE_PX <= y <= height + EDGE_TOLERANCE_PX
            for x, y in region.polygon_px
        ):
            raise ApiError(422, "invalid_polygon", "Outline points must lie inside the image.")

    margins = result["measurements"]
    m = measure(
        [r.polygon_px for r in body.roofs],
        [o.polygon_px for o in body.obstacles],
        result["scale"]["gsd_m"],
        margins["edge_setback_m"],
        margins["obstacle_clearance_m"],
    )
    corrected = CorrectedAreas(
        roofs=[
            RegionAreas(area_m2=round(a, 2), usable_area_m2=round(u, 2))
            for a, u in zip(m.roof_areas_m2, m.roof_usable_areas_m2, strict=True)
        ],
        obstacles=[RegionAreas(area_m2=round(a, 2)) for a in m.obstacle_areas_m2],
        measurements=MeasurementTotals(
            roof_area_m2=round(m.roof_area_m2, 2),
            obstacle_area_m2=round(m.obstacle_area_m2, 2),
            usable_area_m2=round(m.usable_area_m2, 2),
            edge_setback_m=m.edge_setback_m,
            obstacle_clearance_m=m.obstacle_clearance_m,
        ),
    )
    analysis.corrections = body.model_dump(mode="json")
    analysis.corrected_measurements = corrected.model_dump(mode="json")
    session.commit()
    session.refresh(analysis)
    return _record(analysis)


@router.delete("/{analysis_id}", status_code=204, response_class=Response)
def delete_analysis(analysis_id: str, session: SessionDep) -> Response:
    """Delete the analysis, and its stored image unless another analysis uses the same file."""
    analysis = load_analysis(session, analysis_id)
    key = analysis.image_key
    session.delete(analysis)
    session.commit()
    still_used = session.scalar(
        select(func.count()).select_from(Analysis).where(Analysis.image_key == key)
    )
    if not still_used:
        delete_image(key)
    return Response(status_code=204)
