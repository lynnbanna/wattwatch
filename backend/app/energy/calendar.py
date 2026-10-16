"""The modelled year: 365 days x 24 hours in local standard time (no leap day, no DST)."""

import numpy as np

HOURS = 8760
DAYS_IN_MONTH = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])

# Month (0-11) and hour of day (0-23) of every hour of the year.
MONTH_OF_HOUR = np.repeat(np.arange(12), DAYS_IN_MONTH * 24)
HOUR_OF_DAY = np.tile(np.arange(24), 365)


def monthly_sums(hourly: np.ndarray) -> np.ndarray:
    """Sum an 8,760-hour series into 12 months."""
    return np.bincount(MONTH_OF_HOUR, weights=hourly, minlength=12)


def utc_offset_hours(longitude_deg: float) -> int:
    """Standard-time offset from longitude (Lebanon, 35.5°E: UTC+2)."""
    return round(longitude_deg / 15)
