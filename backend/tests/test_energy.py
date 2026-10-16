import httpx
import numpy as np
import pytest

from app.energy.calendar import HOUR_OF_DAY, HOURS, MONTH_OF_HOUR, monthly_sums, utc_offset_hours
from app.energy.demand import SHAPES, hourly_demand
from app.energy.dispatch import Battery, dispatch, grid_schedule
from app.energy.finance import (
    FinanceAssumptions,
    Prices,
    SystemCosts,
    annual_energy_cost,
    cash_flow,
    upfront_cost,
)
from app.energy.hourly_solar import (
    fetch_hourly_yield,
    parse_series,
    scale_to_monthly,
    to_local,
)
from app.solar.pvgis import PvgisError

MONTHLY = [300, 280, 260, 250, 300, 450, 600, 620, 450, 300, 260, 300]


def at_hour(hour: int, value: float) -> np.ndarray:
    """An 8,760-hour series that is `value` at one hour of every day, else 0."""
    return np.where(HOUR_OF_DAY == hour, value, 0.0)


# --- calendar and demand ---------------------------------------------------------


def test_calendar_covers_a_non_leap_year():
    assert HOURS == 8760 and MONTH_OF_HOUR[-1] == 11 and HOUR_OF_DAY[25] == 1
    assert utc_offset_hours(35.5) == 2


def test_demand_preserves_monthly_totals():
    demand = hourly_demand(MONTHLY, "evening_peak")
    np.testing.assert_allclose(monthly_sums(demand), MONTHLY)


def test_shapes_are_normalised_and_evening_peaks_in_the_evening():
    for shape in SHAPES.values():
        assert shape.sum() == pytest.approx(1.0)
    assert SHAPES["evening_peak"].argmax() in (19, 20)


def test_flat_shape_spreads_evenly():
    demand = hourly_demand([24 * 31] + [0] * 11, "flat")
    assert demand[0] == pytest.approx(1.0) and demand[31 * 24] == 0


def test_demand_rejects_bad_input():
    with pytest.raises(ValueError):
        hourly_demand([100] * 11, "flat")
    with pytest.raises(ValueError):
        hourly_demand([-1] + [100] * 11, "flat")


# --- hourly solar ----------------------------------------------------------------


def test_scaling_matches_long_term_monthly_yield():
    rng = np.random.default_rng(1)
    shape = rng.random(HOURS)
    target = np.linspace(100, 200, 12)
    np.testing.assert_allclose(monthly_sums(scale_to_monthly(shape, target)), target)


def test_month_without_sun_stays_zero():
    hourly = np.where(MONTH_OF_HOUR == 0, 0.0, 1.0)
    scaled = scale_to_monthly(hourly, [50] * 12)
    assert monthly_sums(scaled)[0] == 0 and monthly_sums(scaled)[1] == pytest.approx(50)


def test_utc_series_is_shifted_to_local_time():
    utc = np.zeros(HOURS)
    utc[10] = 1.0  # 10:00 UTC on 1 January
    assert to_local(utc, 35.5).argmax() == 12  # 12:00 in Beirut (UTC+2)


def _series_response(watts: float = 100.0, n: int = HOURS) -> dict:
    return {"outputs": {"hourly": [{"time": "", "P": watts} for _ in range(n)]}}


def test_parse_series_converts_watts_and_checks_length():
    assert parse_series(_series_response(500.0))[0] == pytest.approx(0.5)
    with pytest.raises(PvgisError):
        parse_series(_series_response(n=8784))


def test_hourly_yield_is_cached_compactly(isolated_storage):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=_series_response(250.0))

    with isolated_storage() as session, httpx.Client(transport=httpx.MockTransport(handler)) as c:
        first = fetch_hourly_yield(session, 33.89, 35.5, 25, 0, "free", c)
        second = fetch_hourly_yield(session, 33.89, 35.5, 25, 0, "free", c)
    assert len(calls) == 1
    np.testing.assert_allclose(first, second)
    assert first.sum() == pytest.approx(0.25 * HOURS)
    params = calls[0].url.params
    assert params["pvcalculation"] == "1" and params["startyear"] == "2019"


# --- grid schedule ----------------------------------------------------------------


@pytest.mark.parametrize("hours", [0, 4, 6, 12, 24])
def test_grid_schedule_has_the_requested_hours_each_day(hours):
    on = grid_schedule(hours)
    assert on.reshape(365, 24).sum(axis=1).tolist() == [hours] * 365


def test_grid_hours_are_spread_through_the_day():
    assert np.flatnonzero(grid_schedule(6)[:24]).tolist() == [0, 4, 8, 12, 16, 20]


# --- dispatch -------------------------------------------------------------------


def test_energy_balance_holds_every_hour():
    rng = np.random.default_rng(7)
    demand = rng.random(HOURS) * 2
    solar = rng.random(HOURS) * 3 * (HOUR_OF_DAY >= 7) * (HOUR_OF_DAY <= 17)
    battery = Battery(capacity_kwh=8, charge_from_grid=True)
    r = dispatch(demand, solar, grid_schedule(8), generator_kw=1.0, battery=battery)
    served = r.solar_to_load + r.battery_to_load + r.grid_to_load + r.generator_to_load + r.unmet
    np.testing.assert_allclose(served, demand, atol=1e-9)
    np.testing.assert_allclose(r.solar_to_load + r.solar_to_battery + r.curtailed, solar, atol=1e-9)
    soc_min = 8 * (1 - battery.usable_fraction)
    assert r.state_of_charge.min() >= soc_min - 1e-9 and r.state_of_charge.max() <= 8 + 1e-9


def test_grid_always_on_covers_what_solar_does_not():
    demand, solar = np.full(HOURS, 1.0), at_hour(12, 3.0)
    r = dispatch(demand, solar, np.ones(HOURS, bool), generator_kw=0)
    assert r.total("grid_to_load") == pytest.approx(365 * 23)
    assert r.total("curtailed") == pytest.approx(365 * 2)
    assert r.unmet_hours == 0


def test_generator_capacity_limits_supply_and_leaves_unmet_demand():
    r = dispatch(np.full(HOURS, 2.0), np.zeros(HOURS), np.zeros(HOURS, bool), generator_kw=1.0)
    assert r.total("generator_to_load") == pytest.approx(HOURS)
    assert r.total("unmet") == pytest.approx(HOURS)
    assert r.unmet_hours == HOURS


def test_battery_moves_midday_surplus_to_the_evening():
    # 5 kWh of sun at noon, 1 kWh of demand at 20:00, no grid or generator.
    battery = Battery(capacity_kwh=10, usable_fraction=1.0, round_trip_efficiency=0.81)
    r = dispatch(at_hour(20, 1.0), at_hour(12, 5.0), np.zeros(HOURS, bool), 0, battery)
    assert r.total("battery_to_load") == pytest.approx(365.0)
    assert r.unmet_hours == 0
    # Charging is capped at 0.5C = 5 kW and by free capacity; 0.9 x 0.9 = 0.81 round trip.
    assert r.state_of_charge[12] == pytest.approx(4.5)
    assert r.state_of_charge[20] == pytest.approx(4.5 - 1 / 0.9)
    assert r.battery_cycles == pytest.approx(365 / 10)


def test_backup_first_keeps_the_battery_for_grid_outages():
    demand, solar, grid = at_hour(20, 1.0), at_hour(12, 2.0), at_hour(20, 1.0).astype(bool)
    backup = dispatch(demand, solar, grid, 0, Battery(capacity_kwh=5))
    selfuse = dispatch(demand, solar, grid, 0, Battery(capacity_kwh=5, policy="self_consumption"))
    assert backup.total("battery_to_load") == 0 and backup.total("grid_to_load") == pytest.approx(
        365
    )
    assert selfuse.total("battery_to_load") == pytest.approx(365)


def test_battery_can_charge_from_the_grid_for_a_later_outage():
    # Grid on at 02:00 only; demand at 20:00; no sun.
    battery = Battery(
        capacity_kwh=4, usable_fraction=1.0, round_trip_efficiency=1.0, charge_from_grid=True
    )
    r = dispatch(at_hour(20, 1.0), np.zeros(HOURS), at_hour(2, 1.0).astype(bool), 0, battery)
    assert r.total("grid_to_battery") > 0
    assert r.unmet_hours == 0 and r.total("battery_to_load") == pytest.approx(365)


def test_dispatch_rejects_wrong_lengths():
    with pytest.raises(ValueError):
        dispatch(np.zeros(10), np.zeros(HOURS), np.zeros(HOURS, bool), 0)


# --- finance ----------------------------------------------------------------------


def test_annual_energy_cost_by_hand():
    demand = np.full(HOURS, 1.0)
    grid = np.arange(HOURS) % 2 == 0  # grid on every other hour
    r = dispatch(demand, np.zeros(HOURS), grid, generator_kw=5)
    prices = Prices(0.10, 0.40, grid_fixed_usd_per_month=5, generator_fixed_usd_per_month=10)
    expected = 4380 * 0.10 + 4380 * 0.40 + 12 * 15
    assert annual_energy_cost(r, prices) == pytest.approx(expected)


def test_upfront_cost_by_hand():
    costs = SystemCosts(solar_usd_per_kwp=700, battery_usd_per_kwh=300, installation_usd=500)
    assert upfront_cost(5.0, 10.0, costs) == pytest.approx(5 * 700 + 10 * 300 + 500)
    assert upfront_cost(0, 0, costs) == 0


def test_cash_flow_by_hand():
    costs = SystemCosts(700, 300)
    a = FinanceAssumptions(years=25, discount_rate=0.0, price_escalation=0, solar_degradation=0)
    cf = cash_flow(1000, 400, 3000, 0, costs, a)
    assert cf.year1_savings_usd == 600
    assert cf.simple_payback_years == pytest.approx(5.0)
    assert cf.payback_year == 5 and cf.cumulative_usd[4] == pytest.approx(0)
    assert cf.npv_usd == pytest.approx(-3000 + 600 * 25)


def test_battery_is_replaced_within_the_period_only():
    costs = SystemCosts(700, 300)
    a = FinanceAssumptions(
        discount_rate=0, price_escalation=0, solar_degradation=0, battery_life_years=10
    )
    cf = cash_flow(1000, 400, 6000, 10, costs, a)
    replaced = [y + 1 for y, v in enumerate(cf.yearly_net_usd) if v < 600]
    assert replaced == [10, 20]
    assert cf.yearly_net_usd[9] == pytest.approx(600 - 3000)


def test_escalation_and_degradation_compound():
    a = FinanceAssumptions(years=3, discount_rate=0, price_escalation=0.1, solar_degradation=0.5)
    cf = cash_flow(200, 100, 1, 0, SystemCosts(0, 0), a)
    assert cf.yearly_net_usd == pytest.approx([100, 100 * 1.1 * 0.5, 100 * 1.21 * 0.25])


def test_no_savings_means_no_payback():
    cf = cash_flow(400, 500, 3000, 0, SystemCosts(700, 300), FinanceAssumptions())
    assert cf.year1_savings_usd == -100
    assert cf.simple_payback_years is None and cf.payback_year is None


def test_negative_prices_are_rejected():
    with pytest.raises(ValueError):
        Prices(-0.1, 0.3)
