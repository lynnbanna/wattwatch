"""Costs, savings and payback. Every price is a user input: there is no built-in tariff.

Savings compare the household with the system against the same household without it
(same demand, grid hours and generator), using the hourly dispatch for both.
"""

from dataclasses import dataclass

from app.energy.dispatch import DispatchResult


@dataclass(frozen=True)
class Prices:
    grid_usd_per_kwh: float
    generator_usd_per_kwh: float
    grid_fixed_usd_per_month: float = 0.0
    generator_fixed_usd_per_month: float = 0.0

    def __post_init__(self) -> None:
        if min(self.grid_usd_per_kwh, self.generator_usd_per_kwh) < 0:
            raise ValueError("Prices cannot be negative")


@dataclass(frozen=True)
class SystemCosts:
    solar_usd_per_kwp: float  # panels, inverter, mounting and wiring
    battery_usd_per_kwh: float
    installation_usd: float = 0.0
    maintenance_usd_per_year: float = 0.0


@dataclass(frozen=True)
class FinanceAssumptions:
    years: int = 25
    discount_rate: float = 0.08
    price_escalation: float = 0.02  # yearly change in grid and generator prices
    solar_degradation: float = 0.005  # yearly loss of solar output
    battery_life_years: int = 10


def annual_energy_cost(result: DispatchResult, prices: Prices) -> float:
    """Energy bought in one year, including grid power used to charge the battery."""
    grid_kwh = result.total("grid_to_load") + result.total("grid_to_battery")
    variable = (
        grid_kwh * prices.grid_usd_per_kwh
        + result.total("generator_to_load") * prices.generator_usd_per_kwh
    )
    fixed = 12 * (prices.grid_fixed_usd_per_month + prices.generator_fixed_usd_per_month)
    return variable + fixed


def upfront_cost(kwp: float, battery_kwh: float, costs: SystemCosts) -> float:
    if kwp <= 0 and battery_kwh <= 0:
        return 0.0
    return (
        kwp * costs.solar_usd_per_kwp
        + battery_kwh * costs.battery_usd_per_kwh
        + costs.installation_usd
    )


@dataclass(frozen=True)
class CashFlow:
    upfront_usd: float
    year1_savings_usd: float
    yearly_net_usd: list[float]  # savings minus maintenance and replacements, years 1..N
    cumulative_usd: list[float]  # -upfront + running total, years 1..N
    simple_payback_years: float | None
    payback_year: int | None
    npv_usd: float


def cash_flow(
    baseline_cost_usd: float,
    system_cost_usd: float,
    upfront_usd: float,
    battery_kwh: float,
    costs: SystemCosts,
    a: FinanceAssumptions,
) -> CashFlow:
    """Yearly cash flow of owning the system.

    Approximation: year-1 savings scale with price escalation and with solar
    degradation (all savings are treated as solar-driven). The battery is replaced
    at its full current price every `battery_life_years` within the period.
    """
    year1 = baseline_cost_usd - system_cost_usd
    net, cumulative, npv = [], [], -upfront_usd
    running = -upfront_usd
    payback_year = None
    for year in range(1, a.years + 1):
        savings = (
            year1 * (1 + a.price_escalation) ** (year - 1) * (1 - a.solar_degradation) ** (year - 1)
        )
        replacement = (
            battery_kwh * costs.battery_usd_per_kwh
            if battery_kwh > 0 and year % a.battery_life_years == 0 and year < a.years
            else 0.0
        )
        flow = savings - costs.maintenance_usd_per_year - replacement
        net.append(flow)
        running += flow
        cumulative.append(running)
        npv += flow / (1 + a.discount_rate) ** year
        if payback_year is None and upfront_usd > 0 and running >= 0:
            payback_year = year
    year1_net = year1 - costs.maintenance_usd_per_year
    simple = upfront_usd / year1_net if upfront_usd > 0 and year1_net > 0 else None
    return CashFlow(
        upfront_usd=upfront_usd,
        year1_savings_usd=year1,
        yearly_net_usd=net,
        cumulative_usd=cumulative,
        simple_payback_years=simple,
        payback_year=payback_year,
        npv_usd=npv,
    )
