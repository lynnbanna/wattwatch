import hashlib
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db import get_session
from app.measure.area import DEFAULT_EDGE_SETBACK_M, DEFAULT_OBSTACLE_CLEARANCE_M, measure
from app.measure.scale import Scale, ScaleError, scale_from_gsd, scale_from_reference
from app.models import Analysis
from app.storage import save_image
from app.vision.images import ImageValidationError, load_image
from app.vision.models import get_roof_model
from app.vision.resample import resample_to_gsd, resampled_size
from app.vision.types import Detection, RoofModel

router = APIRouter(tags=["vision"])

_STATUS_BY_CODE = {"unsupported_file_type": 415, "image_too_large": 413, "invalid_image": 400}
COARSE_IMAGE_RATIO = 1.5

MODEL_SCORE_NOTE = (
    "The model score (0-1) is the model's average pixel score for a region. It is not the "
    "probability that the outline is correct, and it can be high on images unlike the "
    "training data."
)
PLAN_VIEW_ASSUMPTION = (
    "Areas are plan-view (as seen from above); a pitched roof's surface is larger than its "
    "footprint."
)
AREA_ERROR_UNMEASURED = "The error of these area estimates has not been measured for this model."
# Measured on held-out RID2 test tiles with the correct scale (docs/METRICS.md).
AREA_ERROR_BY_MODEL = {
    ("roof-unet-r18", "0.1.0"): (
        "On held-out test images with the correct scale, roof area was within 7% for half of "
        "the tiles but off by 45% or more for one in ten; usable area within 10% and 56%. "
        "Expect larger errors on other imagery, and check outlines before relying on a number."
    ),
}


class ModelInfo(BaseModel):
    name: str
    version: str
    is_stub: bool
    gsd_m: float


class ImageInfo(BaseModel):
    width_px: int
    height_px: int


class ScaleInfo(BaseModel):
    gsd_m: float
    source: Literal["gsd", "reference_line"]
    model_gsd_m: float
    resample_factor: float


class RoofOut(BaseModel):
    label: str
    model_score: float
    polygon_px: list[tuple[float, float]]
    area_m2: float
    usable_area_m2: float


class ObstacleOut(BaseModel):
    label: str
    model_score: float
    polygon_px: list[tuple[float, float]]
    area_m2: float


class MeasurementsOut(BaseModel):
    roof_area_m2: float
    obstacle_area_m2: float
    usable_area_m2: float
    edge_setback_m: float
    obstacle_clearance_m: float


class RoofAnalysisResponse(BaseModel):
    id: str
    model: ModelInfo
    image: ImageInfo
    scale: ScaleInfo
    roofs: list[RoofOut]
    obstacles: list[ObstacleOut]
    measurements: MeasurementsOut
    model_score_note: str
    assumptions: list[str]
    limitations: list[str]


def _resolve_scale(
    width: int,
    height: int,
    gsd_m: float | None,
    line: tuple[float | None, ...],
    length_m: float | None,
) -> Scale:
    has_line = any(v is not None for v in (*line, length_m))
    if (gsd_m is None) == (not has_line):
        raise ApiError(
            422,
            "invalid_scale",
            "Provide exactly one scale: gsd_m, or a reference line "
            "(reference_x1, reference_y1, reference_x2, reference_y2, reference_length_m).",
        )
    try:
        if gsd_m is not None:
            return scale_from_gsd(gsd_m)
        if any(v is None for v in (*line, length_m)):
            raise ScaleError("A reference line needs both end points and its real length.")
        x1, y1, x2, y2 = line
        if not all(0 <= x <= width for x in (x1, x2)) or not all(
            0 <= y <= height for y in (y1, y2)
        ):
            raise ScaleError("Reference line end points must lie inside the image.")
        return scale_from_reference((x1, y1), (x2, y2), length_m)
    except ScaleError as exc:
        raise ApiError(422, "invalid_scale", exc.message) from exc


def _round_polygon(polygon) -> list[tuple[float, float]]:
    return [(round(x, 1), round(y, 1)) for x, y in polygon]


@router.post("/roof-analysis", response_model=RoofAnalysisResponse)
def analyze_roof(
    file: UploadFile,
    model: Annotated[RoofModel, Depends(get_roof_model)],
    session: Annotated[Session, Depends(get_session)],
    imagery_type: Annotated[Literal["top_down", "oblique_or_ground"], Form()],
    gsd_m: Annotated[float | None, Form(gt=0)] = None,
    reference_x1: Annotated[float | None, Form()] = None,
    reference_y1: Annotated[float | None, Form()] = None,
    reference_x2: Annotated[float | None, Form()] = None,
    reference_y2: Annotated[float | None, Form()] = None,
    reference_length_m: Annotated[float | None, Form(gt=0)] = None,
    edge_setback_m: Annotated[float, Form(ge=0, le=5)] = DEFAULT_EDGE_SETBACK_M,
    obstacle_clearance_m: Annotated[float, Form(ge=0, le=3)] = DEFAULT_OBSTACLE_CLEARANCE_M,
) -> RoofAnalysisResponse:
    """Detect roofs and obstacles in a top-down image, measure them, and save the analysis.

    Scale is required: either `gsd_m` (metres per pixel) or a reference line drawn on
    the image with its real length. The image is resampled to the model's resolution
    and outlines are returned in the original image's pixel coordinates.
    """
    if imagery_type != "top_down":
        raise ApiError(
            422,
            "unsupported_imagery",
            "Only top-down aerial, drone or satellite images can be analysed. Photos taken "
            "at an angle or from the ground distort shapes and areas.",
        )

    settings = get_settings()
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / (1024 * 1024)
        raise ApiError(413, "file_too_large", f"File exceeds the {limit_mb:g} MB upload limit")

    try:
        image = load_image(data, settings.max_image_pixels)
    except ImageValidationError as exc:
        raise ApiError(_STATUS_BY_CODE[exc.code], exc.code, exc.message) from exc

    scale = _resolve_scale(
        image.width,
        image.height,
        gsd_m,
        (reference_x1, reference_y1, reference_x2, reference_y2),
        reference_length_m,
    )
    model_w, model_h = resampled_size(image.size, scale.gsd_m, model.gsd_m)
    if model_w * model_h > settings.max_image_pixels:
        raise ApiError(
            413,
            "image_too_large",
            f"At the model's {model.gsd_m:g} m per pixel this image becomes {model_w}x{model_h} "
            f"px, over the {settings.max_image_pixels:,} pixel limit. Crop it to the roof.",
        )

    resampled = resample_to_gsd(image, scale.gsd_m, model.gsd_m)
    prediction = model.predict(resampled.image)
    roofs = [(d, resampled.to_original(d.polygon)) for d in prediction.roofs]
    obstacles = [(d, resampled.to_original(d.polygon)) for d in prediction.obstacles]
    m = measure(
        [p for _, p in roofs],
        [p for _, p in obstacles],
        scale.gsd_m,
        edge_setback_m,
        obstacle_clearance_m,
    )

    factor = scale.gsd_m / model.gsd_m
    assumptions = [
        f"Scale: {scale.description}.",
        (
            f"Image resampled from {scale.gsd_m:.3g} to {model.gsd_m:g} m per pixel for the model."
            if resampled.image is not image
            else f"No resampling needed; the image matches the model's {model.gsd_m:g} m per pixel."
        ),
        f"Usable area keeps {edge_setback_m:g} m from roof edges and {obstacle_clearance_m:g} m "
        "around obstacles. These are defaults; adjust them to local rules and installer advice.",
        PLAN_VIEW_ASSUMPTION,
    ]
    area_error = AREA_ERROR_BY_MODEL.get((model.name, model.version), AREA_ERROR_UNMEASURED)
    limitations = [*model.limitations, area_error]
    if factor > COARSE_IMAGE_RATIO:
        limitations.insert(
            0,
            f"This image ({scale.gsd_m:.2g} m per pixel) is coarser than the model's "
            f"{model.gsd_m:g} m; enlarging it adds no detail, so small obstacles are likely "
            "missed and usable area overstated.",
        )

    def score(d: Detection) -> float:
        return round(d.score, 3)

    response = RoofAnalysisResponse(
        id=str(uuid4()),
        model=ModelInfo(
            name=model.name, version=model.version, is_stub=model.is_stub, gsd_m=model.gsd_m
        ),
        image=ImageInfo(width_px=image.width, height_px=image.height),
        scale=ScaleInfo(
            gsd_m=round(scale.gsd_m, 5),
            source=scale.source,
            model_gsd_m=model.gsd_m,
            resample_factor=round(factor, 4),
        ),
        roofs=[
            RoofOut(
                label=d.label,
                model_score=score(d),
                polygon_px=_round_polygon(p),
                area_m2=round(a, 2),
                usable_area_m2=round(u, 2),
            )
            for (d, p), a, u in zip(roofs, m.roof_areas_m2, m.roof_usable_areas_m2, strict=True)
        ],
        obstacles=[
            ObstacleOut(
                label=d.label,
                model_score=score(d),
                polygon_px=_round_polygon(p),
                area_m2=round(a, 2),
            )
            for (d, p), a in zip(obstacles, m.obstacle_areas_m2, strict=True)
        ],
        measurements=MeasurementsOut(
            roof_area_m2=round(m.roof_area_m2, 2),
            obstacle_area_m2=round(m.obstacle_area_m2, 2),
            usable_area_m2=round(m.usable_area_m2, 2),
            edge_setback_m=edge_setback_m,
            obstacle_clearance_m=obstacle_clearance_m,
        ),
        model_score_note=MODEL_SCORE_NOTE,
        assumptions=assumptions,
        limitations=limitations,
    )

    upload_sha256 = hashlib.sha256(data).hexdigest()
    session.add(
        Analysis(
            id=response.id,
            upload_sha256=upload_sha256,
            image_key=save_image(image, upload_sha256),
            model_name=model.name,
            model_version=model.version,
            result=response.model_dump(mode="json"),
        )
    )
    session.commit()
    return response
