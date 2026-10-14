from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import ApiError
from app.vision.images import ImageValidationError, load_image
from app.vision.models import get_roof_model
from app.vision.types import Detection, RoofModel

router = APIRouter(tags=["vision"])

_STATUS_BY_CODE = {"unsupported_file_type": 415, "image_too_large": 413, "invalid_image": 400}

PIXEL_LIMITATION = (
    "Coordinates are in image pixels. Real-world area needs a scale or georeferenced "
    "imagery and is not estimated here."
)


class ModelInfo(BaseModel):
    name: str
    version: str
    is_stub: bool


class ImageInfo(BaseModel):
    width_px: int
    height_px: int


class DetectionOut(BaseModel):
    label: str
    confidence: float
    polygon_px: list[tuple[float, float]]


class RoofAnalysisResponse(BaseModel):
    model: ModelInfo
    image: ImageInfo
    roofs: list[DetectionOut]
    obstacles: list[DetectionOut]
    limitations: list[str]


def _to_out(detection: Detection) -> DetectionOut:
    return DetectionOut(
        label=detection.label,
        confidence=round(detection.confidence, 3),
        polygon_px=[(round(x, 1), round(y, 1)) for x, y in detection.polygon],
    )


@router.post("/roof-analysis", response_model=RoofAnalysisResponse)
def analyze_roof(
    file: UploadFile, model: Annotated[RoofModel, Depends(get_roof_model)]
) -> RoofAnalysisResponse:
    """Segment the roof and detect obstacles in an uploaded PNG or JPEG image."""
    settings = get_settings()
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / (1024 * 1024)
        raise ApiError(413, "file_too_large", f"File exceeds the {limit_mb:g} MB upload limit")

    try:
        image = load_image(data, settings.max_image_pixels)
    except ImageValidationError as exc:
        raise ApiError(_STATUS_BY_CODE[exc.code], exc.code, exc.message) from exc

    prediction = model.predict(image)
    limitations = [PIXEL_LIMITATION, *model.limitations]
    return RoofAnalysisResponse(
        model=ModelInfo(name=model.name, version=model.version, is_stub=model.is_stub),
        image=ImageInfo(width_px=image.width, height_px=image.height),
        roofs=[_to_out(d) for d in prediction.roofs],
        obstacles=[_to_out(d) for d in prediction.obstacles],
        limitations=limitations,
    )
