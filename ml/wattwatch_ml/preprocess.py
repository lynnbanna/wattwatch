"""Resample imagery and masks to a fixed ground sampling distance (GSD)."""

import math

import numpy as np
from PIL import Image

IGNORE_INDEX = 255
MODEL_STRIDE = 32  # U-Net input sides must be multiples of this


def resampled_size(size_px: int, source_gsd_m: float, target_gsd_m: float) -> int:
    return max(1, round(size_px * source_gsd_m / target_gsd_m))


def padded_size(size_px: int, stride: int = MODEL_STRIDE) -> int:
    return math.ceil(size_px / stride) * stride


def resample_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Area-averaging resize (antialiased) for RGB imagery."""
    return image.convert("RGB").resize(size, Image.Resampling.BOX)


def resample_mask(mask: np.ndarray, size: tuple[int, int], num_classes: int) -> np.ndarray:
    """Resize a class-index mask by area-weighted majority vote.

    Each class's coverage is area-averaged, then every output pixel takes the
    class covering most of its footprint. Unlike nearest-neighbour sampling,
    this does not depend on which source pixel happens to land on the grid.
    """
    shares = np.stack(
        [
            np.asarray(
                Image.fromarray((mask == c).astype(np.float32)).resize(size, Image.Resampling.BOX)
            )
            for c in range(num_classes)
        ]
    )
    return shares.argmax(axis=0).astype(np.uint8)


def pad_to_stride(
    image: np.ndarray, mask: np.ndarray, stride: int = MODEL_STRIDE
) -> tuple[np.ndarray, np.ndarray]:
    """Pad bottom/right to multiples of `stride`; padded mask pixels are IGNORE_INDEX."""
    h, w = mask.shape
    ph, pw = padded_size(h, stride) - h, padded_size(w, stride) - w
    image = np.pad(image, ((0, ph), (0, pw), (0, 0)), mode="reflect")
    mask = np.pad(mask, ((0, ph), (0, pw)), constant_values=IGNORE_INDEX)
    return image, mask
