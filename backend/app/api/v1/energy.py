"""Energy and financial study: compare system configurations under three scenarios."""

from datetime import UTC, datetime
from typing import Annotated, Literal

import httpx
import numpy as np
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.api.v1.deps import SessionDep, load_analysis
from app.api.v1.solar import get_pvgis_client
from app.core.errors import ApiError
from app.energy.demand import hourly_demand
from app.energy.dispatch import Battery, DispatchResult, dispatch, grid_schedule
from app.energy.finance import (
    FinanceAssumptions,
    Prices,
    SystemCosts,
    annual_energy_cost,
    cash_flow,
    upfront_cost,
)
from app.energy.hourly_solar import SHAPE_YEAR, fetch_hourly_yield, scale_to_monthly
from app.energy.scenarios import SCENARIOS
from app.outlines import current_outlines, outline_hash
from app.solar.production import SystemLosses, performance_factor
from app.solar.pvgis import PvgisError, fetch_resource

router = APIRouter(prefix="/analyses", tags=["energy"])

FLOWS = ("solar_to_load", "battery_to_load", "grid_to_load", "generator_to_load", "unmet")


# --- request -------------------------------------------------------------------


class HouseholdIn(BaseModel):
    monthly_kwh: list[float] = Field(min_length=12, max_length=12)
    daily_shape: Literal["evening_peak", "home_all_day", "flat"] = "evening_peak"

    @field_validator("monthly_kwh")
    @classmethod
    def in_range(cls, v: list[float]) -> list[float]:
        if any(not 0 <= x <= 20_000 for x in v):
            raise ValueError("each month must be between 0 and 20,000 kWh")
        return v


class SupplyIn(BaseModel):
    grid_hours_per_day: float = Field(ge=0, le=24)
    generator_kw: float = Field(ge=0, le=50)


class PricesIn(BaseModel):
    grid_usd_per_kwh: float = Field(ge=0, le=5)
    generator_usd_per_kwh: float = Field(ge=0, le=5)
    grid_fixed_usd_per_month: float = Field(0, ge=0, le=1000)
    generator_fixed_usd_per_month: float = Field(0, ge=0, le=1000)


class CostsIn(BaseModel):
    solar_usd_per_kwp: float = Field(ge=0, le=10_000)
    battery_usd_per_kwh: float = Field(ge=0, le=5_000)
    installation_usd: float = Field(0, ge=0, le=1_000_000)
    maintenance_usd_per_year: float = Field(0, ge=0, le=100_000)


class FinanceIn(BaseModel):
    years: int = Field(25, ge=5, le=40)
    discount_rate: float = Field(0.08, ge=0, le=0.3)
    price_escalation: float = Field(0.02, ge=-0.1, le=0.2)
    solar_degradation: float = Field(0.005, ge=0, le=0.03)
    battery_life_years: int = Field(10, ge=3, le=25)


class ConfigurationIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    solar: bool = True
    battery_kwh: float = Field(0, ge=0, le=200)
    battery_power_kw: float | None = Field(None, gt=0, le=100)
    usable_fraction: float = Field(0.9, ge=0.5, le=1)
    round_trip_efficiency: float = Field(0.9, ge=0.5, le=1)
    charge_from_grid: bool = False
    policy: Literal["backup_first", "self_consumption"] = "backup_first"


class EnergyStudyRequest(BaseModel):
    household: HouseholdIn
    supply: SupplyIn
    prices: PricesIn
    costs: CostsIn
    finance: FinanceIn = FinanceIn()
    configurations: list[ConfigurationIn] = Field(min_length=1, max_length=4)

    @field_validator("configurations")
    @classmethod
    def unique_names(cls, v: list[ConfigurationIn]) -> list[ConfigurationIn]:
        if len({c.name for c in v}) != len(v):
            raise ValueError("configuration names must be unique")
        return v


# --- response ------------------------------------------------------------------


class EnergyTotals(BaseModel):
    demand_kwh: float
    solar_kwh: float
    solar_to_load_kwh: float
    battery_to_load_kwh: float
    grid_to_load_kwh: float
    grid_to_battery_kwh: float
    generator_to_load_kwh: float
    unmet_kwh: float
    unmet_hours: int
    curtailed_kwh: float
    solar_and_battery_share: float
    solar_used_share: float
    battery_cycles: float


class FinanceOut(BaseModel):
    energy_cost_usd_per_year: float
    upfront_usd: float
    year1_savings_usd: float
    simple_payback_years: float | None
    payback_year: int | None
    npv_usd: float
    cumulative_usd: list[float]


class ScenarioResult(BaseModel):
    scenario: str
    energy: EnergyTotals
    finance: FinanceOut


class ReferenceResult(BaseModel):
    scenario: str
    energy: EnergyTotals
    energy_cost_usd_per_year: float


class MonthlyFlows(BaseModel):
    solar_to_load_kwh: list[float]
    battery_to_load_kwh: list[float]
    grid_to_load_kwh: list[float]
    generator_to_load_kwh: list[float]
    unmet_kwh: list[float]


class ConfigurationResult(BaseModel):
    configuration: ConfigurationIn
    kwp: float
    scenarios: list[ScenarioResult]
    monthly_baseline: MonthlyFlows


class ScenarioInfo(BaseModel):
    name: str
    description: str


class EnergyStudy(BaseModel):
    created_at: datetime
    design_outline_hash: str
    design_stale: bool
    kwp: float
    inputs: EnergyStudyRequest
    scenarios: list[ScenarioInfo]
    reference: list[ReferenceResult]
    reference_monthly_baseline: MonthlyFlows
    results: list[ConfigurationResult]
    assumptions: list[str]
    limitations: list[str]


def _totals(r: DispatchResult) -> EnergyTotals:
    demand, solar = r.total("demand"), r.total("solar")
    covered = r.total("solar_to_load") + r.total("battery_to_load")
    used = r.total("solar_to_load") + r.total("solar_to_battery")
    return EnergyTotals(
        demand_kwh=round(demand, 1),
        solar_kwh=round(solar, 1),
        solar_to_load_kwh=round(r.total("solar_to_load"), 1),
        battery_to_load_kwh=round(r.total("battery_to_load"), 1),
        grid_to_load_kwh=round(r.total("grid_to_load"), 1),
        grid_to_battery_kwh=round(r.total("grid_to_battery"), 1),
        generator_to_load_kwh=round(r.total("generator_to_load"), 1),
        unmet_kwh=round(r.total("unmet"), 1),
        unmet_hours=r.unmet_hours,
        curtailed_kwh=round(r.total("curtailed"), 1),
        solar_and_battery_share=round(covered / demand, 4) if demand else 0.0,
        solar_used_share=round(used / solar, 4) if solar else 0.0,
        battery_cycles=round(r.battery_cycles, 1),
    )


def _monthly(r: DispatchResult) -> MonthlyFlows:
    return MonthlyFlows(**{f"{name}_kwh": [round(v, 1) for v in r.monthly(name)] for name in FLOWS})


@router.post("/{analysis_id}/energy-study", response_model=EnergyStudy)
def create_energy_study(
    analysis_id: str,
    body: EnergyStudyRequest,
    session: SessionDep,
    client: Annotated[httpx.Client, Depends(get_pvgis_client)],
) -> EnergyStudy:
    """Simulate a typical year hour by hour for each configuration and scenario,
    compare costs with the same household without solar, and save the study."""
    analysis = load_analysis(session, analysis_id)
    design = analysis.solar_design
    if design is None:
        raise ApiError(
            409, "solar_design_required", "Estimate solar production for this roof first."
        )
    roofs, obstacles, _ = current_outlines(analysis)
    stale = design["outline_hash"] != outline_hash(roofs, obstacles)

    loc, mount = design["location"], design["mounting"]
    mounting = "free" if mount["kind"] == "flat_tilted" else "building"
    try:
        shape = fetch_hourly_yield(
            session,
            loc["lat"],
            loc["lon"],
            mount["tilt_deg"],
            mount["azimuth_deg"],
            mounting,
            client,
        )
        resource = fetch_resource(
            session,
            loc["lat"],
            loc["lon"],
            mount["tilt_deg"],
            mount["azimuth_deg"],
            mounting,
            client=client,
        )
    except PvgisError as exc:
        raise ApiError(502, "solar_data_unavailable", str(exc)) from exc

    kwp = design["layout"]["kwp"]
    factor = performance_factor(SystemLosses(**design["losses"]))
    solar_per_kwp = scale_to_monthly(shape, resource.monthly_yield_kwh_per_kwp) * factor
    base_demand = hourly_demand(body.household.monthly_kwh, body.household.daily_shape)
    grid = grid_schedule(body.supply.grid_hours_per_day)
    gen_kw = body.supply.generator_kw
    prices = Prices(**body.prices.model_dump())
    costs = SystemCosts(**body.costs.model_dump())
    base_finance = FinanceAssumptions(**body.finance.model_dump())
    no_solar = np.zeros_like(solar_per_kwp)

    reference: list[ReferenceResult] = []
    reference_monthly = None
    per_config: dict[str, list[ScenarioResult]] = {c.name: [] for c in body.configurations}
    monthly_baseline: dict[str, MonthlyFlows] = {}

    for scenario in SCENARIOS:
        demand = base_demand * scenario.demand_factor
        ref = dispatch(demand, no_solar, grid, gen_kw)
        ref_cost = annual_energy_cost(ref, prices)
        reference.append(
            ReferenceResult(
                scenario=scenario.name,
                energy=_totals(ref),
                energy_cost_usd_per_year=round(ref_cost, 2),
            )
        )
        if scenario.name == "baseline":
            reference_monthly = _monthly(ref)
        finance = scenario.finance(base_finance)

        for config in body.configurations:
            config_kwp = kwp if config.solar else 0.0
            battery = Battery(
                capacity_kwh=config.battery_kwh,
                usable_fraction=config.usable_fraction,
                round_trip_efficiency=config.round_trip_efficiency,
                max_charge_kw=config.battery_power_kw,
                max_discharge_kw=config.battery_power_kw,
                charge_from_grid=config.charge_from_grid,
                policy=config.policy,
            )
            solar = solar_per_kwp * config_kwp * scenario.solar_factor
            result = dispatch(demand, solar, grid, gen_kw, battery)
            cost = annual_energy_cost(result, prices)
            upfront = upfront_cost(config_kwp, config.battery_kwh, costs) * scenario.upfront_factor
            cf = cash_flow(ref_cost, cost, upfront, config.battery_kwh, costs, finance)
            per_config[config.name].append(
                ScenarioResult(
                    scenario=scenario.name,
                    energy=_totals(result),
                    finance=FinanceOut(
                        energy_cost_usd_per_year=round(cost, 2),
                        upfront_usd=round(cf.upfront_usd, 2),
                        year1_savings_usd=round(cf.year1_savings_usd, 2),
                        simple_payback_years=(
                            None
                            if cf.simple_payback_years is None
                            else round(cf.simple_payback_years, 2)
                        ),
                        payback_year=cf.payback_year,
                        npv_usd=round(cf.npv_usd, 2),
                        cumulative_usd=[round(v, 2) for v in cf.cumulative_usd],
                    ),
                )
            )
            if scenario.name == "baseline":
                monthly_baseline[config.name] = _monthly(result)

    f = body.finance
    p = body.prices
    assumptions = [
        f"Household: {sum(body.household.monthly_kwh):,.0f} kWh a year as entered, spread over "
        f"each day by the '{body.household.daily_shape.replace('_', ' ')}' pattern (an "
        "illustrative preset, not a measured profile).",
        f"Grid power {body.supply.grid_hours_per_day:g} hours a day, spread evenly through the "
        f"day; a generator supplies up to {gen_kw:g} kW when the grid is off.",
        f"Solar: {kwp:g} kWp from the saved design. Hourly pattern from PVGIS {SHAPE_YEAR}, "
        f"scaled to the {resource.years} monthly average; {factor:.1%} of the loss-free yield "
        "is delivered.",
        "Each hour, demand is met by solar, then the battery, then the grid when on, then the "
        "generator up to its capacity. Surplus solar charges the battery; the rest is not paid "
        "for (no export credit).",
        "Battery 'backup first' discharges only when the grid is off, saving stored energy for "
        "outages; 'self consumption' discharges whenever solar falls short.",
        f"Prices as entered: grid ${p.grid_usd_per_kwh:g}/kWh, generator "
        f"${p.generator_usd_per_kwh:g}/kWh; fixed monthly fees (${p.grid_fixed_usd_per_month:g} "
        f"grid, ${p.generator_fixed_usd_per_month:g} generator) are paid with and without solar.",
        f"Finance: {f.years} years, {f.discount_rate:.0%} discount rate, energy prices changing "
        f"{f.price_escalation:+.0%} a year, solar output falling {f.solar_degradation:.1%} a "
        f"year, battery replaced every {f.battery_life_years} years at today's price.",
        "Savings are compared with the same household without solar: same demand, grid hours "
        "and generator.",
    ]
    limitations = [
        "Real rationing schedules vary and rotate; when outages actually happen changes how "
        "much a battery helps.",
        "A generator subscription is assumed to continue; cancelling it would add savings but "
        "risk outages when solar and battery run out.",
        "Yearly savings are scaled by panel ageing as if all savings came from solar (an "
        "approximation).",
        "Not included: inverter replacement (often after 10-15 years), taxes, financing costs, "
        "insurance, and any payment for exported solar.",
        "Scenarios show sensitivity to the inputs; they are not probabilities.",
    ]
    if stale:
        limitations.insert(
            0, "The solar design was made from earlier roof outlines; re-estimate production."
        )

    study = EnergyStudy(
        created_at=datetime.now(UTC),
        design_outline_hash=design["outline_hash"],
        design_stale=stale,
        kwp=kwp,
        inputs=body,
        scenarios=[ScenarioInfo(name=s.name, description=s.description) for s in SCENARIOS],
        reference=reference,
        reference_monthly_baseline=reference_monthly,
        results=[
            ConfigurationResult(
                configuration=c,
                kwp=kwp if c.solar else 0.0,
                scenarios=per_config[c.name],
                monthly_baseline=monthly_baseline[c.name],
            )
            for c in body.configurations
        ],
        assumptions=assumptions,
        limitations=limitations,
    )
    analysis.energy_study = study.model_dump(mode="json")
    session.commit()
    return study
