# WattWatch — Product Requirements (v0.1)

## Problem
Households considering rooftop solar — particularly in Lebanon, where grid
supply is unreliable and private generators fill the gap — lack a quick,
honest way to see what their roof could produce and whether solar plus a
battery would pay off against their current utility and generator costs.

## Users
- **Homeowner / household decision-maker** — wants a credible estimate before talking to installers.
- **Installer or consultant** (secondary) — wants a fast first-pass assessment to share with a client.

## Main user journey
1. **Upload** a rooftop image (or pick a demo property).
2. **Analyze** — the system segments the roof and flags obstacles, with confidence shown.
3. **Calibrate and correct** — the user supplies scale (or uses georeferenced imagery) and fixes boundaries/obstacles.
4. **Estimate usable area** — after obstacles and clearance margins.
5. **Configure** panels and an optional battery.
6. **Compare** costs, savings, and payback across scenarios (optimistic / baseline / conservative).
7. **Save or share** a report that lists every assumption and limitation.

## MVP scope
| Module | Must do |
|---|---|
| Rooftop Vision | Roof segmentation, selected obstacle detection, overlay with confidence |
| Solar Estimation | Calibrated area → feasible panel layout → monthly/annual generation |
| Energy & Financial | Demand profile, user-entered utility/generator costs, battery behaviour, savings, payback |
| Dashboard | Saved properties and scenarios, comparison, assumption inspector, report |

## Success criteria
- A first-time user completes the journey end to end in under 10 minutes.
- Vision metrics (IoU, precision/recall) reported on a held-out set.
- Area-estimation error measured against manually measured references.
- Solar and financial outputs match hand-calculated test scenarios.
- Every displayed number traces back to a visible assumption.

## Non-goals (v1)
Mobile apps, nationwide real-time satellite processing, bill OCR, custom
foundation models, live utility integrations, organisation accounts.

## Key risks
| Risk | Mitigation |
|---|---|
| No legally usable labelled rooftop data for the region | Validate licensing in Weeks 1–2; fall back to public datasets + a small hand-labelled set |
| Pixel area mistaken for real area | Require scale or georeferencing; show uncertainty |
| Model underperforms | Manual correction is a first-class path; model is swappable |
| Tariff/generator costs vary widely | User-entered costs with documented defaults, never one hardcoded tariff |
