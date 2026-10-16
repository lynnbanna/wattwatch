"""Hourly solar output for a typical year.

The hourly *shape* comes from one real year of PVGIS data (2019, so clouds and
heat waves fall on real days); each month is then scaled so its total equals the
long-term (2005-2023) monthly yield the solar design already uses.
"""

import time
from collections.abc import Callable, Sequence
from typing import Literal

import httpx
import numpy as np
from sqlalchemy.orm import Session

from app.energy.calendar import HOURS, MONTH_OF_HOUR, monthly_sums, utc_offset_hours
from app.models import PvgisCache
from app.solar.pvgis import PvgisError, request_json

SERIES_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
SHAPE_YEAR = 2019


def parse_series(data: dict) -> np.ndarray:
    """PVGIS seriescalc hourly power (W per kWp, UTC) -> kWh per kWp per hour."""
    try:
        hourly = data["outputs"]["hourly"]
        values = np.array([float(row["P"]) for row in hourly]) / 1000.0
    except (KeyError, TypeError, ValueError) as exc:
        raise PvgisError("Unexpected hourly response from PVGIS") from exc
    if len(values) != HOURS:
        raise PvgisError(f"Expected {HOURS} hourly values from PVGIS, got {len(values)}")
    return values


def to_local(utc_series: np.ndarray, longitude_deg: float) -> np.ndarray:
    """Shift a UTC series to local standard time (the year wraps around)."""
    return np.roll(utc_series, utc_offset_hours(longitude_deg))


def scale_to_monthly(hourly: np.ndarray, monthly_target: Sequence[float]) -> np.ndarray:
    """Scale each month so it sums to the target; a month with no sun stays zero."""
    sums = monthly_sums(hourly)
    target = np.asarray(monthly_target, dtype=float)
    factors = np.divide(target, sums, out=np.zeros(12), where=sums > 0)
    return hourly * factors[MONTH_OF_HOUR]


def fetch_hourly_yield(
    session: Session,
    lat: float,
    lon: float,
    tilt_deg: float,
    azimuth_deg: float,
    mounting: Literal["free", "building"],
    client: httpx.Client,
    sleep: Callable[[float], None] = time.sleep,
) -> np.ndarray:
    """Loss-free hourly yield of 1 kWp for SHAPE_YEAR in local standard time, cached."""
    key = (
        f"seriescalc:v5_3:{lat:.2f}:{lon:.2f}:{tilt_deg:g}:{azimuth_deg:g}:{mounting}:{SHAPE_YEAR}"
    )
    cached = session.get(PvgisCache, key)
    if cached is not None:
        return to_local(np.array(cached.response["kwh_per_kwp_utc"]), lon)

    params = {
        "lat": round(lat, 2),
        "lon": round(lon, 2),
        "peakpower": 1,
        "loss": 0,
        "angle": tilt_deg,
        "aspect": azimuth_deg,
        "mountingplace": mounting,
        "usehorizon": 1,
        "pvcalculation": 1,
        "startyear": SHAPE_YEAR,
        "endyear": SHAPE_YEAR,
        "outputformat": "json",
    }
    data = request_json(params, client, sleep, url=SERIES_URL)
    series = parse_series(data)
    # Store only the values we use (about 60 KB instead of 800 KB).
    session.add(PvgisCache(key=key, response={"kwh_per_kwp_utc": np.round(series, 5).tolist()}))
    session.commit()
    return to_local(series, lon)
