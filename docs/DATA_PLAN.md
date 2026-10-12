# Data Plan

Status: **draft — licenses must be verified against each source's current
terms before any data is downloaded into the project or used for training.**

## What we need
| Need | Purpose | Minimum for MVP |
|---|---|---|
| Aerial/satellite rooftop images | Roof segmentation | A few hundred labelled roofs |
| Roof obstacle labels (e.g. water tanks, solar water heaters, stairwell structures, HVAC) | Obstacle detection | One or two obstacle classes, narrowly defined |
| Held-out evaluation set | Honest metrics | Never used for tuning; ideally includes regional (Lebanese) roofs |
| Reference measurements | Area-error measurement | 10–20 roofs with known real dimensions |
| Solar resource data | Generation estimates | Monthly irradiance for the target location |

## Candidate sources (to evaluate)
| Source | What it offers | Notes to verify |
|---|---|---|
| Roof Information Dataset (RID) | Roof segments and superstructures (obstacles) | Geography (Germany), license terms |
| Inria Aerial Image Labeling | Building footprints, high-res aerial | License restrictions on use; footprints only, no obstacles |
| SpaceNet building datasets | Building footprints from satellite imagery | License and attribution terms |
| OpenStreetMap buildings | Footprint polygons, includes Lebanon | ODbL — attribution and share-alike obligations |
| Microsoft Global ML Building Footprints | Footprint polygons | License; coverage of Lebanon |
| Own hand-labelled images | Regional roofs (flat concrete, water tanks) | Image source must allow use; permission for any private property imagery |
| PVGIS (EU JRC) | Solar irradiance and PV estimates; covers Lebanon | Terms of use, API rate limits |
| pvlib (Python library) | Solar position, irradiance transposition, PV models | Open source; validate against PVGIS outputs |

## Regional fit
Lebanese residential roofs are commonly flat concrete with water tanks,
solar water heaters, and stairwell structures — different from the pitched
roofs that dominate most public datasets. Expect a domain gap; build a small
regional evaluation set even if training uses public data.

## Rules
- Record source, license, download date, and attribution for every dataset in `data/SOURCES.md`.
- Raw data lives in `data/raw/` (git-ignored); only small fixtures go in git.
- Split train / validation / held-out test **before** any model work; the test split is frozen.
- No private or identifiable imagery without permission.

## Week 1 exit criteria
- [ ] License verified for at least one segmentation source
- [ ] Obstacle classes chosen and defined in writing
- [ ] Decision on evaluation set composition
