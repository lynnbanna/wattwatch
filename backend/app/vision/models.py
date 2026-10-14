"""Roof models behind one small interface so the implementation stays replaceable."""

from collections.abc import Callable
from functools import lru_cache

from PIL import Image

from app.core.config import get_settings
from app.vision.types import Detection, Point, RoofModel, RoofPrediction


def _rectangle(x0: float, y0: float, x1: float, y1: float) -> list[Point]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class StubRoofModel:
    """Placeholder geometry so the upload → overlay pipeline works without a model file.

    It does not look at image content: the roof is the central 60% of the image
    and one water tank sits in its upper-left corner.
    """

    name = "stub"
    version = "0.1.0"
    is_stub = True
    gsd_m = 0.15
    limitations = (
        "Stub model: placeholder geometry for testing the pipeline, not an analysis of this image.",
    )

    def predict(self, image: Image.Image) -> RoofPrediction:
        w, h = image.size
        roof = _rectangle(0.2 * w, 0.2 * h, 0.8 * w, 0.8 * h)
        side = 0.08 * min(w, h)
        tank_x, tank_y = 0.25 * w, 0.25 * h
        tank = _rectangle(tank_x, tank_y, tank_x + side, tank_y + side)
        return RoofPrediction(
            roofs=[Detection("roof", 0.5, roof)],
            obstacles=[Detection("water_tank", 0.5, tank)],
        )


def _onnx_model() -> RoofModel:
    from app.vision.unet import OnnxRoofModel  # imports onnxruntime only when selected

    return OnnxRoofModel.from_path(get_settings().vision_model_path)


_MODELS: dict[str, Callable[[], RoofModel]] = {"stub": StubRoofModel, "unet": _onnx_model}


@lru_cache
def get_roof_model() -> RoofModel:
    name = get_settings().vision_model
    if name not in _MODELS:
        raise ValueError(f"Unknown VISION_MODEL {name!r}; expected one of {sorted(_MODELS)}")
    return _MODELS[name]()
