"""Resample images to the model's ground sampling distance and map polygons back."""

from dataclasses import dataclass

from PIL import Image

from app.vision.types import Point


@dataclass(frozen=True)
class Resampled:
    image: Image.Image
    scale_x: float  # resampled px per original px
    scale_y: float

    def to_original(self, polygon: list[Point]) -> list[Point]:
        return [(x / self.scale_x, y / self.scale_y) for x, y in polygon]


def resampled_size(size: tuple[int, int], source_gsd_m: float, target_gsd_m: float):
    factor = source_gsd_m / target_gsd_m
    return max(1, round(size[0] * factor)), max(1, round(size[1] * factor))


def resample_to_gsd(image: Image.Image, source_gsd_m: float, target_gsd_m: float) -> Resampled:
    """Area-average when shrinking, bicubic when enlarging (which adds no real detail)."""
    w, h = image.size
    new_w, new_h = resampled_size(image.size, source_gsd_m, target_gsd_m)
    if (new_w, new_h) == (w, h):
        return Resampled(image, 1.0, 1.0)
    method = Image.Resampling.BOX if new_w < w else Image.Resampling.BICUBIC
    return Resampled(image.resize((new_w, new_h), method), new_w / w, new_h / h)
