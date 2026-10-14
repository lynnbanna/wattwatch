"""Solar design for a saved analysis: panel layout on the usable roof and production."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from app.api.v1.deps import SessionDep, load_analysis
from app.core.errors import ApiError
from app.measure.area import usable_geometry
from app.outlines import current_outlines, outline_hash
from app.solar.layout import Mounting, PanelSpec, layout_panels
from app.solar.locations import LEBANESE_CITIES, MAX_LAT, MIN_LAT
from app.solar.production import (
    SystemLosses,
    capacity_factor,
    monthly_energy_kwh,
    performance_factor,
    specific_yield_kwh_per_kwp,
    system_kwp,
)
from app.solar.pvgis import ATTRIBUTION, PvgisError, fetch_resource

router = APIRouter(prefix="/analyses", tags=["solar"])


def get_pvgis_client() -> Iterator[httpx.Client]:
    with httpx.Client() as client:
        yield client


# --- request -------------------------------------------------------------------


class LocationIn(BaseModel):
    city: str | None = None
    lat: float | None = Field(None, ge=MIN_LAT, le=MAX_LAT)
    lon: float | None = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def one_kind(self) -> "LocationIn":
        has_coords = self.lat is not None and self.lon is not None
        if (self.city is None) == (not has_coords):
            raise ValueError("give either a city or both lat and lon")
        if self.city is not None and self.city.lower() not in LEBANESE_CITIES:
            names = ", ".join(c.name for c in LEBANESE_CITIES.values())
            raise ValueError(f"unknown city; choose one of {names}")
        return self


class PanelIn(BaseModel):
    power_w: float = Field(450, ge=100, le=800)
    length_m: float = Field(1.722, ge=0.5, le=3.0)
    width_m: float = Field(1.134, ge=0.3, le=2.0)
    gap_m: float = Field(0.02, ge=0, le=0.5)


class MountingIn(BaseModel):
    kind: Literal["flat_tilted", "flush"] = "flat_tilted"
    tilt_deg: float = Field(25, ge=0, le=60)
    azimuth_deg: float = Field(0, ge=-180, le=180)
    orientation: Literal["landscape", "portrait"] = "landscape"


class LossesIn(BaseModel):
    soiling: float = Field(0.03, ge=0, le=0.5)
    wiring: float = Field(0.02, ge=0, le=0.5)
    mismatch: float = Field(0.01, ge=0, le=0.5)
    shading: float = Field(0.02, ge=0, le=0.5)
    availability: float = Field(0.01, ge=0, le=0.5)
    inverter_efficiency: float = Field(0.96, ge=0.8, le=1.0)


class SolarDesignRequest(BaseModel):
    location: LocationIn
    panel: PanelIn = PanelIn()
    mounting: MountingIn = MountingIn()
    losses: LossesIn = LossesIn()


# --- response ------------------------------------------------------------------


class LocationOut(BaseModel):
    name: str | None
    lat: float
    lon: float


class LayoutOut(BaseModel):
    panel_count: int
    kwp: float
    panels_px: list[list[tuple[float, float]]]
    usable_area_m2: float
    panel_area_m2: float
    row_pitch_m: float
    row_gap_m: float
    winter_noon_sun_elevation_deg: float | None


class ProductionOut(BaseModel):
    monthly_kwh: list[float]
    annual_kwh: float
    specific_yield_kwh_per_kwp: float
    capacity_factor: float
    performance_factor: float
    year_to_year_sd_kwh: float


class ResourceOut(BaseModel):
    loss_free_yield_kwh_per_kwp: float
    monthly_irradiation_kwh_m2: list[float]
    loss_angle_pct: float
    loss_spectral_pct: float
    loss_temperature_irradiance_pct: float
    database: str
    years: str
    elevation_m: float
    attribution: str


class SolarDesign(BaseModel):
    created_at: datetime
    outline_hash: str
    uses_corrections: bool
    location: LocationOut
    panel: PanelIn
    mounting: MountingIn
    losses: LossesIn
    layout: LayoutOut
    production: ProductionOut
    resource: ResourceOut
    assumptions: list[str]
    limitations: list[str]


def _direction(azimuth: float) -> str:
    names = [
        "south",
        "south-west",
        "west",
        "north-west",
        "north",
        "north-east",
        "east",
        "south-east",
    ]
    return names[round((azimuth % 360) / 45) % 8]


def _resolve(location: LocationIn) -> LocationOut:
    if location.city is not None:
        city = LEBANESE_CITIES[location.city.lower()]
        return LocationOut(name=city.name, lat=city.lat, lon=city.lon)
    return LocationOut(name=None, lat=round(location.lat, 2), lon=round(location.lon, 2))


@router.post("/{analysis_id}/solar-design", response_model=SolarDesign)
def create_solar_design(
    analysis_id: str,
    body: SolarDesignRequest,
    session: SessionDep,
    client: Annotated[httpx.Client, Depends(get_pvgis_client)],
) -> SolarDesign:
    """Fit panels into the analysis's usable roof area and estimate monthly production.

    Uses the user's corrected outlines when present. The design is saved with the analysis.
    """
    analysis = load_analysis(session, analysis_id)
    result = analysis.result
    gsd = result["scale"]["gsd_m"]
    margins = result["measurements"]
    roofs, obstacles, uses_corrections = current_outlines(analysis)
    location = _resolve(body.location)

    usable = usable_geometry(
        roofs, obstacles, gsd, margins["edge_setback_m"], margins["obstacle_clearance_m"]
    )
    panel = PanelSpec(**body.panel.model_dump())
    mounting = Mounting(**body.mounting.model_dump())
    try:
        layout = layout_panels(usable, panel, mounting, location.lat)
    except ValueError as exc:
        raise ApiError(422, "invalid_location", str(exc)) from exc

    try:
        resource = fetch_resource(
            session,
            location.lat,
            location.lon,
            mounting.tilt_deg,
            mounting.azimuth_deg,
            "free" if mounting.kind == "flat_tilted" else "building",
            client=client,
        )
    except PvgisError as exc:
        raise ApiError(502, "solar_data_unavailable", str(exc)) from exc

    losses = SystemLosses(**body.losses.model_dump())
    factor = performance_factor(losses)
    kwp = system_kwp(len(layout.panels), panel.power_w)
    monthly = monthly_energy_kwh(kwp, resource.monthly_yield_kwh_per_kwp, factor)
    annual = sum(monthly)

    fp = layout.footprint
    place = (
        f"{location.name} (city centre, {location.lat:.2f}, {location.lon:.2f})"
        if location.name
        else f"coordinates {location.lat:.2f}, {location.lon:.2f} (rounded to about 1 km)"
    )
    facing = (
        f"{mounting.tilt_deg:g}° facing {_direction(mounting.azimuth_deg)} "
        f"(azimuth {mounting.azimuth_deg:g}°)"
    )
    if mounting.kind == "flat_tilted":
        sun = layout.winter_noon_sun_elevation_deg
        mount_text = (
            f"Flat roof: racks tilted {facing}; rows {fp.row_pitch_m:.2f} m apart so they do "
            f"not shade each other at winter-solstice noon (sun {sun:.1f}° high)."
        )
    else:
        mount_text = f"Flush on a roof pitched {facing}."
    sd_pct = 100 * resource.year_to_year_sd_kwh_per_kwp / resource.annual_yield_kwh_per_kwp
    assumptions = [
        f"Location: {place}.",
        f"Panels: {panel.power_w:g} W, {panel.length_m:g} × {panel.width_m:g} m, "
        f"{mounting.orientation}, {100 * panel.gap_m:g} cm apart.",
        mount_text,
        f"Losses: soiling {losses.soiling:.0%}, wiring {losses.wiring:.0%}, mismatch "
        f"{losses.mismatch:.0%}, shading {losses.shading:.0%}, availability "
        f"{losses.availability:.0%}; inverter efficiency {losses.inverter_efficiency:.0%}. "
        f"{factor:.1%} of the loss-free yield is delivered.",
        f"Solar data: {resource.radiation_database} {resource.years}, terrain shading included. "
        f"PVGIS-modelled effects: temperature and low light "
        f"{resource.loss_temperature_irradiance_pct:+.1f}%, "
        f"reflection {resource.loss_angle_pct:+.1f}%, spectrum {resource.loss_spectral_pct:+.2f}%.",
        "Roof outlines: "
        + (
            "your corrected outlines." if uses_corrections else "the model's outlines, uncorrected."
        ),
    ]
    limitations = [
        f"Long-term average for {resource.years}; a single year typically differs by about "
        f"±{sd_pct:.0f}%.",
        "The image is assumed to have north at the top; panel direction is relative to that.",
        f"Shade from neighbouring buildings, tanks and parapets is only covered by the "
        f"{losses.shading:.0%} shading loss.",
        "Panels are placed on a simple grid; an installer may fit more or fewer.",
        "Errors in the roof outlines carry into the panel count; check them first.",
    ]
    if mounting.kind == "flush":
        limitations.insert(
            0, "Roof pitch and direction are your inputs; a top-down image cannot measure them."
        )
    if not layout.panels:
        limitations.insert(0, "No whole panel fits in the usable area with these settings.")

    def to_px(poly) -> list[tuple[float, float]]:
        return [(round(x / gsd, 1), round(y / gsd, 1)) for x, y in list(poly.exterior.coords)[:-1]]

    design = SolarDesign(
        created_at=datetime.now(UTC),
        outline_hash=outline_hash(roofs, obstacles),
        uses_corrections=uses_corrections,
        location=location,
        panel=body.panel,
        mounting=body.mounting,
        losses=body.losses,
        layout=LayoutOut(
            panel_count=len(layout.panels),
            kwp=round(kwp, 3),
            panels_px=[to_px(p) for p in layout.panels],
            usable_area_m2=round(usable.area, 2),
            panel_area_m2=round(len(layout.panels) * panel.length_m * panel.width_m, 2),
            row_pitch_m=round(fp.row_pitch_m, 3),
            row_gap_m=round(fp.row_gap_m, 3),
            winter_noon_sun_elevation_deg=(
                None
                if layout.winter_noon_sun_elevation_deg is None
                else round(layout.winter_noon_sun_elevation_deg, 2)
            ),
        ),
        production=ProductionOut(
            monthly_kwh=[round(m, 1) for m in monthly],
            annual_kwh=round(annual, 1),
            specific_yield_kwh_per_kwp=round(specific_yield_kwh_per_kwp(annual, kwp), 1),
            capacity_factor=round(capacity_factor(annual, kwp), 4),
            performance_factor=round(factor, 4),
            year_to_year_sd_kwh=round(kwp * resource.year_to_year_sd_kwh_per_kwp * factor, 1),
        ),
        resource=ResourceOut(
            loss_free_yield_kwh_per_kwp=resource.annual_yield_kwh_per_kwp,
            monthly_irradiation_kwh_m2=resource.monthly_irradiation_kwh_m2,
            loss_angle_pct=resource.loss_angle_pct,
            loss_spectral_pct=resource.loss_spectral_pct,
            loss_temperature_irradiance_pct=resource.loss_temperature_irradiance_pct,
            database=resource.radiation_database,
            years=resource.years,
            elevation_m=resource.elevation_m,
            attribution=ATTRIBUTION,
        ),
        assumptions=assumptions,
        limitations=limitations,
    )
    analysis.solar_design = design.model_dump(mode="json")
    session.commit()
    return design
