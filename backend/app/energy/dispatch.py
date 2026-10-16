"""Hourly energy dispatch for one modelled year (time step: 1 hour, so kW == kWh).

Each hour, demand is met in this order:
1. solar, directly;
2. the battery, either only while the grid is off ("backup_first", the default, which
   saves stored energy for outages because grid power is usually far cheaper than
   generator power) or whenever solar falls short ("self_consumption");
3. the grid, when it is available;
4. the generator, when the grid is off, up to its capacity;
5. otherwise the demand goes unmet.
Surplus solar charges the battery; what is left is curtailed (no export credit is
assumed). Optionally the battery also charges from the grid when the grid is on.
"""

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from app.energy.calendar import HOUR_OF_DAY, HOURS, monthly_sums

Policy = Literal["backup_first", "self_consumption"]


@dataclass(frozen=True)
class Battery:
    capacity_kwh: float
    usable_fraction: float = 0.9  # share of capacity that may be used (depth of discharge)
    round_trip_efficiency: float = 0.9
    max_charge_kw: float | None = None  # None: capacity / 2 (0.5C)
    max_discharge_kw: float | None = None
    charge_from_grid: bool = False
    policy: Policy = "backup_first"

    def __post_init__(self) -> None:
        if self.capacity_kwh < 0:
            raise ValueError("Battery capacity cannot be negative")
        if not 0 < self.usable_fraction <= 1 or not 0 < self.round_trip_efficiency <= 1:
            raise ValueError("Usable fraction and round-trip efficiency must be in (0, 1]")

    @property
    def charge_kw(self) -> float:
        return self.capacity_kwh / 2 if self.max_charge_kw is None else self.max_charge_kw

    @property
    def discharge_kw(self) -> float:
        return self.capacity_kwh / 2 if self.max_discharge_kw is None else self.max_discharge_kw


NO_BATTERY = Battery(capacity_kwh=0)


def grid_schedule(hours_per_day: float) -> np.ndarray:
    """Grid availability: `hours_per_day` hours a day, spread evenly over the 24 hours.

    Real rationing schedules vary and rotate; spreading the hours evenly avoids
    assuming the grid is always on at a convenient time (such as the evening peak).
    """
    if not 0 <= hours_per_day <= 24:
        raise ValueError("Grid hours per day must be between 0 and 24")
    on = np.zeros(24, dtype=bool)
    n = round(hours_per_day)
    if n:
        on[np.floor(np.arange(n) * 24 / n).astype(int)] = True
    return on[HOUR_OF_DAY]


@dataclass
class DispatchResult:
    solar_to_load: np.ndarray
    battery_to_load: np.ndarray
    grid_to_load: np.ndarray
    generator_to_load: np.ndarray
    unmet: np.ndarray
    solar_to_battery: np.ndarray
    grid_to_battery: np.ndarray
    curtailed: np.ndarray
    state_of_charge: np.ndarray
    demand: np.ndarray
    solar: np.ndarray
    battery_usable_kwh: float = 0.0
    _monthly: dict = field(default_factory=dict, repr=False)

    def total(self, name: str) -> float:
        return float(getattr(self, name).sum())

    def monthly(self, name: str) -> np.ndarray:
        if name not in self._monthly:
            self._monthly[name] = monthly_sums(getattr(self, name))
        return self._monthly[name]

    @property
    def unmet_hours(self) -> int:
        return int((self.unmet > 1e-6).sum())

    @property
    def battery_cycles(self) -> float:
        if self.battery_usable_kwh <= 0:
            return 0.0
        return self.total("battery_to_load") / self.battery_usable_kwh


def dispatch(
    demand_kwh: np.ndarray,
    solar_kwh: np.ndarray,
    grid_on: np.ndarray,
    generator_kw: float,
    battery: Battery = NO_BATTERY,
) -> DispatchResult:
    """Simulate every hour of the year. All inputs are 8,760-hour arrays (kWh per hour)."""
    for name, series in (("demand", demand_kwh), ("solar", solar_kwh), ("grid", grid_on)):
        if len(series) != HOURS:
            raise ValueError(f"{name} must have {HOURS} hourly values")
    if generator_kw < 0:
        raise ValueError("Generator capacity cannot be negative")

    out = {
        k: np.zeros(HOURS)
        for k in (
            "solar_to_load",
            "battery_to_load",
            "grid_to_load",
            "generator_to_load",
            "unmet",
            "solar_to_battery",
            "grid_to_battery",
            "curtailed",
            "state_of_charge",
        )
    }
    eta = math.sqrt(battery.round_trip_efficiency)  # same loss charging and discharging
    soc_max = battery.capacity_kwh
    soc_min = battery.capacity_kwh * (1 - battery.usable_fraction)
    soc = soc_min  # start empty; the year's result barely depends on it
    charge_kw, discharge_kw = battery.charge_kw, battery.discharge_kw

    for h in range(HOURS):
        load, sun, grid = demand_kwh[h], solar_kwh[h], bool(grid_on[h])

        direct = min(load, sun)
        need = load - direct
        surplus = sun - direct

        charge = min(surplus, charge_kw, max(soc_max - soc, 0.0) / eta) if eta else 0.0
        soc += charge * eta
        surplus -= charge

        from_battery = 0.0
        if need > 0 and (battery.policy == "self_consumption" or not grid):
            from_battery = min(need, discharge_kw, max(soc - soc_min, 0.0) * eta)
            soc -= from_battery / eta if eta else 0.0
            need -= from_battery

        from_grid = from_gen = grid_charge = 0.0
        if grid:
            from_grid = need
            need = 0.0
            if battery.charge_from_grid and eta:
                grid_charge = min(charge_kw - charge, max(soc_max - soc, 0.0) / eta)
                soc += grid_charge * eta
        elif need > 0:
            from_gen = min(need, generator_kw)
            need -= from_gen

        out["solar_to_load"][h] = direct
        out["battery_to_load"][h] = from_battery
        out["grid_to_load"][h] = from_grid
        out["generator_to_load"][h] = from_gen
        out["unmet"][h] = need
        out["solar_to_battery"][h] = charge
        out["grid_to_battery"][h] = grid_charge
        out["curtailed"][h] = surplus
        out["state_of_charge"][h] = soc

    return DispatchResult(
        **out,
        demand=np.asarray(demand_kwh, dtype=float),
        solar=np.asarray(solar_kwh, dtype=float),
        battery_usable_kwh=soc_max - soc_min,
    )
