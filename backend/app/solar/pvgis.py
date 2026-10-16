"""Solar resource from PVGIS 5.3 (EU JRC), called server-side and cached in the database.

PVGIS forbids browser (CORS) calls and limits clients to 30 requests per second.
Attribution: "PVGIS © European Communities, 2001-2026".
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from sqlalchemy.orm import Session

from app.models import PvgisCache

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
ATTRIBUTION = "PVGIS © European Communities, 2001-2026"
TIMEOUT_S = 20.0
RETRIES = 3
RETRY_STATUSES = {429, 500, 502, 503, 504, 529}


class PvgisError(Exception):
    pass


@dataclass(frozen=True)
class SolarResource:
    monthly_yield_kwh_per_kwp: list[float]  # 1 kWp, no system losses
    monthly_irradiation_kwh_m2: list[float]  # on the panel plane
    annual_yield_kwh_per_kwp: float
    year_to_year_sd_kwh_per_kwp: float
    loss_angle_pct: float
    loss_spectral_pct: float
    loss_temperature_irradiance_pct: float
    radiation_database: str
    years: str
    elevation_m: float


def cache_key(lat: float, lon: float, tilt: float, azimuth: float, mounting: str) -> str:
    # About 1 km of rounding: solar resource changes far more slowly than that.
    return f"pvcalc:v5_3:{lat:.2f}:{lon:.2f}:{tilt:g}:{azimuth:g}:{mounting}"


def parse_pvcalc(data: dict[str, Any]) -> SolarResource:
    try:
        months = data["outputs"]["monthly"]["fixed"]
        totals = data["outputs"]["totals"]["fixed"]
        meteo = data["inputs"]["meteo_data"]
        return SolarResource(
            monthly_yield_kwh_per_kwp=[float(m["E_m"]) for m in months],
            monthly_irradiation_kwh_m2=[float(m["H(i)_m"]) for m in months],
            annual_yield_kwh_per_kwp=float(totals["E_y"]),
            year_to_year_sd_kwh_per_kwp=float(totals["SD_y"]),
            loss_angle_pct=float(totals["l_aoi"]),
            loss_spectral_pct=float(totals["l_spec"]),
            loss_temperature_irradiance_pct=float(totals["l_tg"]),
            radiation_database=str(meteo["radiation_db"]),
            years=f"{meteo['year_min']}-{meteo['year_max']}",
            elevation_m=float(data["inputs"]["location"]["elevation"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PvgisError("Unexpected response from PVGIS") from exc


def request_json(
    params: dict[str, Any],
    client: httpx.Client,
    sleep: Callable[[float], None] = time.sleep,
    url: str = PVGIS_URL,
) -> dict[str, Any]:
    """GET a PVGIS endpoint with retries on rate limiting and server errors."""
    for attempt in range(RETRIES):
        try:
            response = client.get(url, params=params, timeout=TIMEOUT_S)
        except httpx.HTTPError as exc:
            if attempt == RETRIES - 1:
                raise PvgisError("PVGIS could not be reached") from exc
        else:
            if response.status_code == 200:
                return response.json()
            if response.status_code not in RETRY_STATUSES:
                message = response.json().get("message") if response.content else None
                raise PvgisError(f"PVGIS rejected the request: {message or response.status_code}")
            if attempt == RETRIES - 1:
                raise PvgisError("PVGIS is busy or unavailable; try again later")
        sleep(2**attempt)
    raise AssertionError("unreachable")


def fetch_resource(
    session: Session,
    lat: float,
    lon: float,
    tilt_deg: float,
    azimuth_deg: float,
    mounting: Literal["free", "building"],
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> SolarResource:
    """Monthly yield of 1 kWp with no system losses, from the cache or PVGIS."""
    key = cache_key(lat, lon, tilt_deg, azimuth_deg, mounting)
    cached = session.get(PvgisCache, key)
    if cached is not None:
        return parse_pvcalc(cached.response)

    params = {
        "lat": round(lat, 2),
        "lon": round(lon, 2),
        "peakpower": 1,
        "loss": 0,
        "angle": tilt_deg,
        "aspect": azimuth_deg,
        "mountingplace": mounting,
        "usehorizon": 1,
        "outputformat": "json",
    }
    owns_client = client is None
    client = client or httpx.Client()
    try:
        data = request_json(params, client, sleep)
    finally:
        if owns_client:
            client.close()
    resource = parse_pvcalc(data)  # validate before caching
    session.add(PvgisCache(key=key, response=data))
    session.commit()
    return resource
