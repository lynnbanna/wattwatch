"""Roof models behind one small interface so the implementation stays replaceable."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from PIL import Image

from app.core.config import get_settings

Point = tuple[float, float]


@dataclass(frozen=True)
class Detection:
    """A labelled region in image pixel coordinates (x right, y down)."""

    label: str
    confidence: float
    polygon: list[Point]


@dataclass(frozen=True)
class RoofPrediction:
    roofs: list[Detection]
    obstacles: list[Detection]


class RoofModel(Protocol):
    name: str
    version: str
    is_stub: bool

    def predict(self, image: Image.Image) -> RoofPrediction: ...


def _rectangle(x0: float, y0: float, x1: float, y1: float) -> list[Point]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class StubRoofModel:
    """Placeholder geometry so the upload → overlay pipeline works before training.

    It does not look at image content: the roof is the central 60% of the image
    and one water tank sits in its upper-left corner.
    """

    name = "stub"
    version = "0.1.0"
    is_stub = True

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


_MODELS: dict[str, type] = {"stub": StubRoofModel}


@lru_cache
def get_roof_model() -> RoofModel:
    name = get_settings().vision_model
    if name not in _MODELS:
        raise ValueError(f"Unknown VISION_MODEL {name!r}; expected one of {sorted(_MODELS)}")
    return _MODELS[name]()
