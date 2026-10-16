"""Optimistic / baseline / conservative scenarios as transparent adjustments to the
user's own inputs. They show how sensitive the result is; they are not probabilities."""

from dataclasses import dataclass, replace

from app.energy.finance import FinanceAssumptions

MIN_BATTERY_LIFE_YEARS = 3


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    solar_factor: float = 1.0
    demand_factor: float = 1.0
    escalation_delta: float = 0.0
    degradation_delta: float = 0.0
    battery_life_delta: int = 0
    upfront_factor: float = 1.0

    def finance(self, base: FinanceAssumptions) -> FinanceAssumptions:
        return replace(
            base,
            price_escalation=base.price_escalation + self.escalation_delta,
            solar_degradation=max(base.solar_degradation + self.degradation_delta, 0.0),
            battery_life_years=max(
                base.battery_life_years + self.battery_life_delta, MIN_BATTERY_LIFE_YEARS
            ),
        )


SCENARIOS = (
    Scenario(
        "optimistic",
        "A sunny, efficient case: 5% more solar, 5% less demand, energy prices rising 2 points "
        "a year faster, slower panel ageing, a longer-lived battery and 5% lower upfront cost.",
        solar_factor=1.05,
        demand_factor=0.95,
        escalation_delta=0.02,
        degradation_delta=-0.001,
        battery_life_delta=2,
        upfront_factor=0.95,
    ),
    Scenario("baseline", "Your inputs as entered."),
    Scenario(
        "conservative",
        "A cautious case: 10% less solar (dust, shade, a poor year), 5% more demand, energy "
        "prices rising 2 points a year slower, faster panel ageing, a battery that lasts 3 years "
        "less and 15% higher upfront cost.",
        solar_factor=0.90,
        demand_factor=1.05,
        escalation_delta=-0.02,
        degradation_delta=0.003,
        battery_life_delta=-3,
        upfront_factor=1.15,
    ),
)
