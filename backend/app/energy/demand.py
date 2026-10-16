"""Household electricity demand for every hour of the modelled year.

The daily shapes are illustrative presets, not measured Lebanese load profiles:
they decide *when* in the day the user's monthly consumption happens, which
matters for how much solar is used directly and how much a battery must cover.
"""

from collections.abc import Sequence
from typing import Literal

import numpy as np

from app.energy.calendar import DAYS_IN_MONTH, HOUR_OF_DAY, MONTH_OF_HOUR

DailyShape = Literal["evening_peak", "home_all_day", "flat"]

# Relative use in each hour 00-23, local time. Normalised to sum to 1 below.
# fmt: off
_SHAPES: dict[str, list[float]] = {
    # Out during the day: a morning bump, low midday, a long evening peak.
    "evening_peak": [
        0.5, 0.4, 0.4, 0.4, 0.4, 0.5, 0.8, 1.1, 1.0, 0.7, 0.6, 0.6,  # 00-11
        0.6, 0.6, 0.6, 0.7, 0.9, 1.2, 1.5, 1.8, 1.8, 1.6, 1.2, 0.8,  # 12-23
    ],
    # Someone home all day: cooking and appliances spread through daylight hours.
    "home_all_day": [
        0.5, 0.4, 0.4, 0.4, 0.4, 0.5, 0.8, 1.0, 1.1, 1.1, 1.1, 1.2,  # 00-11
        1.3, 1.2, 1.1, 1.1, 1.1, 1.2, 1.4, 1.5, 1.4, 1.2, 0.9, 0.7,  # 12-23
    ],
    "flat": [1.0] * 24,
}
# fmt: on
SHAPES = {name: np.array(v) / np.sum(v) for name, v in _SHAPES.items()}


def hourly_demand(monthly_kwh: Sequence[float], shape: DailyShape) -> np.ndarray:
    """Spread each month's kWh evenly over its days, and each day by the shape."""
    monthly = np.asarray(monthly_kwh, dtype=float)
    if monthly.shape != (12,) or (monthly < 0).any():
        raise ValueError("monthly_kwh must be 12 non-negative values")
    per_day = monthly / DAYS_IN_MONTH
    return per_day[MONTH_OF_HOUR] * SHAPES[shape][HOUR_OF_DAY]
