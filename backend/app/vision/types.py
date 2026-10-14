from dataclasses import dataclass
from typing import Protocol

from PIL import Image

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
    limitations: tuple[str, ...]

    def predict(self, image: Image.Image) -> RoofPrediction: ...
