"""Image scale (ground sampling distance, metres per pixel) from user input."""

import math
from dataclasses import dataclass
from typing import Literal

MIN_GSD_M = 0.02
MAX_GSD_M = 2.0
MIN_REFERENCE_PX = 10.0


class ScaleError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class Scale:
    gsd_m: float
    source: Literal["gsd", "reference_line"]
    description: str


def _check_range(gsd_m: float) -> None:
    if not MIN_GSD_M <= gsd_m <= MAX_GSD_M:
        raise ScaleError(
            f"Scale of {gsd_m:.3g} m per pixel is outside the supported range "
            f"{MIN_GSD_M}-{MAX_GSD_M} m per pixel; check the value or the reference line."
        )


def scale_from_gsd(gsd_m: float) -> Scale:
    _check_range(gsd_m)
    return Scale(gsd_m, "gsd", f"{gsd_m:.3g} m per pixel, as entered")


def scale_from_reference(
    start: tuple[float, float], end: tuple[float, float], length_m: float
) -> Scale:
    """Scale from a line drawn on the image whose real-world length is known."""
    pixels = math.dist(start, end)
    if pixels < MIN_REFERENCE_PX:
        raise ScaleError(
            f"Reference line is {pixels:.0f} px long; draw it at least "
            f"{MIN_REFERENCE_PX:.0f} px long, ideally along the longest known edge."
        )
    if length_m <= 0:
        raise ScaleError("Reference length must be greater than zero.")
    gsd_m = length_m / pixels
    _check_range(gsd_m)
    return Scale(
        gsd_m,
        "reference_line",
        f"{gsd_m:.3g} m per pixel, from a {length_m:g} m reference line of {pixels:.0f} px",
    )
