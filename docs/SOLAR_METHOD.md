# Solar Production Method

How WattWatch turns a usable roof area into a monthly energy estimate, and every
assumption involved. Code: `backend/app/solar/`. Tests: `backend/tests/test_solar.py`.

## 1. Panel layout (`layout.py`)
- **Panel defaults:** 450 W, 1.722 m × 1.134 m, 2 cm gap between panels (a common
  108-half-cell module, about 23% efficient). All editable.
- **Image orientation:** images are assumed **north-up** (image top = north), as aerial and
  satellite orthophotos normally are. Panel azimuth is measured from that.
- **Flat roofs (default):** panels on tilted racks in rows facing the chosen azimuth
  (default south, 25° tilt). Rows are spaced so they do **not shade each other at solar
  noon on the winter solstice**, the lowest noon sun of the year:
  - sun elevation = 90° − |latitude| − 23.44° (Beirut: 32.7°)
  - gap between rows = slope length × sin(tilt) / tan(sun elevation)
  - Beirut, 25°, landscape: row pitch 1.78 m for a 1.03 m plan-view panel depth.
  - Some morning and evening shading in winter remains; it is covered by the shading loss.
- **Flush mounting (pitched roofs):** panels lie in the roof plane at the roof's tilt and
  azimuth; rows only need the panel gap. Plan-view depth is foreshortened by cos(tilt).
- **Packing:** whole panels only, placed on a regular grid inside the usable area (roof
  minus edge setback and obstacle clearances, see the analysis), trying 16 grid offsets and
  keeping the one that fits the most. Real installers may fit a few more by mixing
  orientations or staggering rows.

- **System size:** by default every panel that fits is placed; `max_panels` sizes the
  system to the household instead (filling the roof often wastes solar, see
  [ENERGY_METHOD.md](ENERGY_METHOD.md)).

## 2. Solar resource (`pvgis.py`)
- **Source:** PVGIS 5.3 `PVcalc` (EU Joint Research Centre), SARAH3 satellite radiation and
  ERA5 weather, 2005-2023, terrain horizon shading on. Called server-side only.
- **Request:** 1 kWp, **0% system loss**, at the panel tilt and azimuth. The result already
  includes PVGIS-modelled effects, which are reported separately:
  temperature and low irradiance (Beirut 25° south: −8.6%), reflection at oblique angles
  (−2.6%) and spectrum (+0.15%).
- **Mounting type sent to PVGIS:** `free` (free-standing racks, well ventilated) for flat
  roofs; `building` (hotter, integrated) for flush mounting, a conservative choice.
- **Location:** city presets or coordinates, rounded to 0.01° (about 1 km) for the request
  and cache; solar resource changes much more slowly than that.
- **Cache:** responses stored in the `pvgis_cache` table, so repeated designs are instant
  and stay within PVGIS's 30 requests/second limit.
- **Attribution:** PVGIS © European Communities, 2001-2026.

## 3. Production (`production.py`)
energy per month = kWp × PVGIS loss-free yield (kWh/kWp) × performance factor

| Stage | Default | Why |
|---|---|---|
| Soiling | 3% | Dust; long dry summers. Raise it if panels are rarely cleaned. |
| Wiring (DC and AC) | 2% | Typical cable losses for a residential system. |
| Mismatch | 1% | Small differences between panels in a string. |
| Shading | 2% | Residual inter-row and nearby-object shading. Raise it for shaded roofs. |
| Availability | 1% | Downtime and grid outages when the inverter cannot export. |
| Inverter efficiency | 96% | Typical weighted efficiency of a modern string or hybrid inverter. |
| **Performance factor** | **0.877** | Product of the stages (12.3% total loss). |

These defaults are typical industry values, not measurements from Lebanese installations.
Every stage is editable and returned with the estimate.

## 4. Validation
- **Hand calculations:** 10 × 450 W = 4.5 kWp; 100 kWh/kWp per month at factor 0.9 gives
  405 kWh per month and 4,860 kWh per year (tested).
- **Against PVGIS itself:** with a loss chain equivalent to PVGIS's default 14% system loss,
  our engine reproduces PVGIS's own `PVcalc` output for Beirut within 0.01 kWh in every
  month (recorded responses in `backend/tests/fixtures/`).
- **Layout:** hand-countable roofs (exactly 3 × 2 panels; one millimetre less loses a
  column), holes, rotation, and the row-pitch formula.

## Limitations
- Year-to-year variation: PVGIS reports a standard deviation (Beirut: about 31 kWh/kWp per
  year); estimates are long-term averages, not a forecast for a given year.
- No modelling of shade from neighbouring buildings, water tanks or parapets beyond the
  shading loss; no degradation over the system's life yet (financial model, Week 5).
- Roof pitch and orientation cannot be measured from a single top-down image; for pitched
  roofs they are user inputs.
