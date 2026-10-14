from dataclasses import dataclass
from typing import Protocol

from PIL import Image

Point = tuple[float, float]


@dataclass(frozen=True)
class Detection:
    """A labelled region in image pixel coordinates (x right, y down)."""

    label: str
    score: float  # mean pixel score over the region; not a probability of being correct
    polygon: list[Point]


@dataclass(frozen=True)
class RoofPrediction:
    roofs: list[Detection]
    obstacles: list[Detection]


class RoofModel(Protocol):
    name: str
    version: str
    is_stub: bool
    gsd_m: float  # ground sampling distance the model expects, metres per pixel
    limitations: tuple[str, ...]

    def predict(self, image: Image.Image) -> RoofPrediction: ...
