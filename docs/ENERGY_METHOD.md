# Energy and Financial Method

How WattWatch compares solar and battery configurations for a household that relies on
limited grid supply and a private generator. Code: `backend/app/energy/`. Tests:
`backend/tests/test_energy.py`, `backend/tests/test_energy_api.py`.

## Why hourly
In Lebanon, grid power is available only part of the day and a generator covers the rest,
usually at a much higher price. Whether a battery pays off depends on *when* solar is
produced, when the household uses power and when the grid is off. Monthly totals cannot
show that, so WattWatch simulates **every hour of a typical year (8,760 hours)**.

## Inputs
| Input | Source |
|---|---|
| Monthly consumption (kWh) | User |
| Daily usage pattern | User picks a preset: evening peak, home all day, or flat. Presets are illustrative shapes, not measured profiles |
| Grid hours per day | User; spread evenly through the day |
| Generator capacity (kW) | User (e.g. a 10 A subscription at 220 V is about 2.2 kW) |
| Grid and generator prices, fixed monthly fees | User; **no built-in tariff** |
| Solar, battery and installation costs | User |
| Solar system | The saved solar design (kWp, location, tilt, azimuth, losses) |

## 1. Hourly solar (`hourly_solar.py`)
PVGIS `seriescalc` gives one real year of hourly output (2019) for 1 kWp with no system
losses. It is shifted from UTC to local standard time (UTC + round(longitude / 15),
daylight saving ignored) and **each month is scaled so its total matches the 2005-2023
long-term monthly yield** used by the solar design. The design's performance factor and
kWp are then applied. The result keeps real day-to-day weather while matching the design's
monthly numbers.

## 2. Hourly demand (`demand.py`)
Each month's kWh is spread evenly over its days, and each day over 24 hours by the chosen
pattern. Monthly totals are preserved exactly.

## 3. Dispatch (`dispatch.py`)
Each hour, in this order:
1. **Solar** supplies demand directly.
2. **Battery** supplies what solar cannot:
   - *backup first* (default): only while the grid is off. Stored energy is saved for
     outages, because grid power is usually far cheaper than generator power.
   - *self consumption*: whenever solar falls short.
3. **Grid** covers the rest while it is on.
4. **Generator** covers the rest while the grid is off, up to its capacity.
5. Anything left is **unmet demand** (counted in kWh and hours).

Surplus solar charges the battery; the rest is **curtailed** (no export credit). Optionally
the battery also charges from the grid. Battery model: usable share of capacity (default
90%), round-trip efficiency (default 90%, split equally between charging and discharging),
charge and discharge limit (default half the capacity per hour).

## 4. Costs and payback (`finance.py`)
- **Annual energy cost** = grid kWh (including battery charging) × grid price + generator
  kWh × generator price + 12 × fixed monthly fees.
- **Savings** compare with the **same household without the system** (same demand, grid
  hours and generator), simulated the same way.
- **Upfront** = kWp × solar cost per kWp + battery kWh × battery cost per kWh + installation.
- **Cash flow** over 25 years (default): savings grow with energy prices (default +2% a
  year) and shrink with panel ageing (default 0.5% a year); maintenance is subtracted; the
  battery is replaced at today's price every 10 years (default). Outputs: simple payback,
  payback year, cumulative cash and net present value (default 8% discount rate).

## 5. Scenarios (`scenarios.py`)
Adjustments to the user's own inputs, to show sensitivity, **not probabilities**:

| | Optimistic | Baseline | Conservative |
|---|---|---|---|
| Solar output | +5% | as designed | −10% |
| Household demand | −5% | as entered | +5% |
| Energy price change per year | +2 points | as entered | −2 points |
| Panel ageing per year | −0.1 point | as entered | +0.3 point |
| Battery life | +2 years | as entered | −3 years (minimum 3) |
| Upfront cost | −5% | as entered | +15% |

## Validation
- **Energy balance every hour:** on randomised inputs, solar + battery + grid + generator
  + unmet equals demand in all 8,760 hours, and solar = direct use + battery charging +
  curtailment.
- **Hand-checked hours:** noon surplus carried to the evening at 0.81 round-trip efficiency;
  generator capacity limits and unmet hours; backup-first vs self-consumption; grid charging.
- **Hand-checked money:** bills, payback of exactly 5.0 years, NPV, battery replacement in
  years 10 and 20 but not 25, compounding of escalation and ageing.
- **End to end:** with grid power all day, the no-solar bill equals demand × grid price
  ($240 for 1,200 kWh at $0.20).

## Example (illustrative inputs, not advice)
Beirut, 4,370 kWh a year (evening peak), grid 6 h a day, 2.2 kW generator, grid
$0.27/kWh, generator $0.45/kWh, solar $600/kWp, battery $250/kWh, installation $500,
baseline scenario:

| System | Generator kWh/yr | Energy cost/yr | Upfront | Payback | 25-year NPV |
|---|---|---|---|---|---|
| None | 3,272 | $1,769 | n/a | n/a | n/a |
| 3.6 kWp solar | 2,192 | $1,156 | $2,660 | 4.3 y | +$4,761 |
| 3.6 kWp + 10 kWh battery | 142 | $234 | $5,160 | 3.4 y | +$11,746 |
| 16.2 kWp solar (fills the roof) | 1,962 | $1,043 | $10,220 | 14.1 y | −$1,421 |

Filling the roof wastes most of the extra solar at midday; sizing to the household and
adding storage matters more.

## Limitations
- Rationing schedules vary and rotate; the timing of real outages changes how much a
  battery helps.
- A generator subscription is assumed to continue (its fixed fee is paid in both cases).
- Yearly savings are scaled by panel ageing as if all savings came from solar.
- Not included: inverter replacement (often after 10-15 years), taxes, financing costs,
  insurance, payment for exported solar, and battery capacity fade between replacements.
- Daily patterns are presets; seasonal change comes only from the monthly kWh.
