"""Energy production from a PV system: independent, unit-tested functions.

PVGIS supplies the monthly yield of 1 kWp with no system losses; its modelled
temperature, angle-of-incidence and spectral effects are already included. This
module applies the remaining losses as separate, visible factors.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass

MONTHS = 12


@dataclass(frozen=True)
class SystemLosses:
    """Fractions lost (0-1) at each stage, and inverter efficiency (0-1)."""

    soiling: float = 0.03
    wiring: float = 0.02
    mismatch: float = 0.01
    shading: float = 0.02
    availability: float = 0.01
    inverter_efficiency: float = 0.96

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1, got {value}")
        if self.inverter_efficiency == 0:
            raise ValueError("inverter_efficiency must be greater than 0")


def system_kwp(panel_count: int, panel_power_w: float) -> float:
    return panel_count * panel_power_w / 1000.0


def performance_factor(losses: SystemLosses) -> float:
    """Share of the PVGIS (loss-free) yield delivered as AC energy."""
    factor = losses.inverter_efficiency
    for loss in (
        losses.soiling,
        losses.wiring,
        losses.mismatch,
        losses.shading,
        losses.availability,
    ):
        factor *= 1 - loss
    return factor


def monthly_energy_kwh(
    kwp: float, monthly_yield_kwh_per_kwp: Sequence[float], factor: float
) -> list[float]:
    if len(monthly_yield_kwh_per_kwp) != MONTHS:
        raise ValueError("Expected 12 monthly values")
    return [kwp * y * factor for y in monthly_yield_kwh_per_kwp]


def specific_yield_kwh_per_kwp(annual_kwh: float, kwp: float) -> float:
    return annual_kwh / kwp if kwp > 0 else 0.0


def capacity_factor(annual_kwh: float, kwp: float) -> float:
    """Average output as a share of rated power over a year (8,760 h)."""
    return annual_kwh / (kwp * 8760) if kwp > 0 else 0.0
