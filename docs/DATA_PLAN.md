# Data Plan

Status: **licenses reviewed 2026-10-12** from primary sources (dataset pages,
license files, provider terms). Items marked *unverified* could not be confirmed
from a primary source and must be checked before that source is used.
Decisions signed off 2026-10-12.

## What we need
| Need | Purpose | Minimum for MVP |
|---|---|---|
| Aerial/satellite rooftop images | Roof segmentation | A few hundred labelled roofs |
| Roof obstacle labels | Obstacle detection | One or two obstacle classes, narrowly defined |
| Held-out evaluation set | Honest metrics | Never used for tuning; includes regional (Lebanese) roofs |
| Reference measurements | Area-error measurement | 10–20 roofs with known real dimensions |
| Solar resource data | Generation estimates | Monthly irradiance for the target location |

## Source review
| Source | License | Train | Publish weights | Redistribute | Commercial | Verdict |
|---|---|---|---|---|---|---|
| **RID2** (TUM, Zenodo [10.5281/zenodo.14062580](https://zenodo.org/records/14062580)) | CC BY 4.0 (labels and imagery) | ✅ | ✅ | ✅ with credit | ✅ | **Use** |
| RID v1 (TUM) | Code LGPL-3.0; imagery is Google satellite under "fair use" | ❌ | ❌ | ❌ | ❌ | **Avoid** — Google Maps Platform Terms §3.2.3(c) forbid ML training and tracing |
| Inria Aerial Image Labeling | No license stated; registration form | *unverified* | *unverified* | *unverified* | *unverified* | Avoid unless authors confirm terms |
| SpaceNet 2 buildings | CC BY-SA 4.0 | ✅ | ⚠️ share-alike may apply | ✅ CC BY-SA | ✅ | Optional; share-alike risk |
| OpenStreetMap buildings | ODbL 1.0 | ⚠️ | ⚠️ unclear if a model is a Produced Work | ODbL share-alike | ✅ | Vectors only; reference use |
| Microsoft Global ML Building Footprints | CDLA-Permissive-2.0 | ✅ | ✅ | ✅ | ✅ | Use for roof cropping / weak masks (covers Lebanon; no imagery) |
| OpenAerialMap — Beirut drone orthophoto (2020-08-04), 0.12 m | CC BY 4.0 | ✅ | ✅ | ✅ | ✅ | **Use for regional evaluation** |
| OpenAerialMap — Maxar/Planet Beirut scenes, 0.42–0.63 m | CC BY-NC 4.0 (per-image metadata) | ✅ | non-commercial only | non-commercial only | ❌ | Optional, quarantined NC tier |
| Google / Bing / Esri basemaps | Provider terms | ❌ | ❌ | ❌ | ❌ | **Never label or train on these** |
| Zindi Lacuna Solar Survey (solar water heaters) | *unverified* (competition terms) | *unverified* | | | | Check terms before use |
| PVGIS 5.3 (EU JRC) | Free reuse with acknowledgement (EC reuse policy CC BY 4.0) | n/a | n/a | ✅ with credit | probably ✅ (*unverified*) | **Use** for solar resource |
| pvlib | BSD-3-Clause | n/a | n/a | n/a | ✅ | Use; validate against PVGIS |

### Key facts
- **RID2:** 4,764 grid images (512×512, 0.08 m, Dutch aerial imagery, 50 regions);
  roof segments (N/E/S/W/flat, or 16 azimuths + flat); 12 superstructure classes
  (PV module, dormer, window, skylight, chimney, AC outlet, AC system, TV dish,
  ladder, wall, balcony, other). 7 GB zip from Zenodo. No water tanks or solar
  water heaters, and roofs are mostly pitched.
- **Lebanon imagery is the bottleneck:** the only openly licensed sub-0.5 m
  imagery found that permits labelling and redistribution is one ~0.8 × 0.8 km
  CC BY 4.0 drone orthophoto of the Beirut port area. Maxar Open Data no longer
  lists a Beirut event; the CC BY-NC copies survive only on OpenAerialMap.
- **PVGIS:** API `https://re.jrc.ec.europa.eu/api/v5_3/`, 30 requests/s per IP,
  **no browser (CORS) calls**, so it must be called from the backend. Beirut test
  call returned SARAH3 radiation data, 2005–2023, ~1,444 kWh/kWp/yr.

### Required attributions
- RID2: Krapf, Ganß, Zinniel, Lienkamp, "RID2", Zenodo, doi:10.5281/zenodo.14062580; imagery © Beeldmateriaal Nederland, CC BY 4.0; state modifications.
- OpenAerialMap images: per-image provider and license from the image metadata.
- Microsoft footprints: dataset name and CDLA-Permissive-2.0 link.
- PVGIS: "PVGIS © European Communities, 2001-2026".

## Regional fit
Lebanese residential roofs are commonly flat concrete with water tanks,
solar water heaters, and stairwell structures — different from the pitched
roofs that dominate public datasets. Expect a domain gap: train on RID2
downsampled to 0.3–0.5 m, then fine-tune and evaluate on hand-labelled
regional roofs.

## Decisions
- **Decided — roof segmentation source:** RID2, using the "flat" class and
  downsampling to match available Lebanese imagery resolution.
- **Decided — obstacle classes (MVP, 2 classes):**
  - `water_tank` — a cylindrical or box-shaped storage tank on the roof surface,
    including its stand.
  - `solar_water_heater` — a flat-plate or evacuated-tube collector together
    with its attached tank.
  - Later candidates: `stairwell_bulkhead`, `hvac_unit`, `pv_module`.
  - Neither class exists in RID2, so these need hand labels; RID2's
    superstructure classes can be used for pretraining.
- **Decided — held-out evaluation set:** hand-labelled tiles from the CC BY 4.0
  Beirut orthophoto, spatially separated from any training tiles. Optional
  non-commercial tier from the CC BY-NC Beirut scenes, kept in its own folder
  and excluded from any commercial build. Limitation to document: Beirut-only
  coverage.

## Rules
- Record source, license, download date, and attribution for every dataset in `data/SOURCES.md`.
- Raw data lives in `data/raw/` (git-ignored); only small fixtures go in git.
- Split train / validation / held-out test **before** any model work; the test split is frozen.
- No private or identifiable imagery without permission.
- Never trace, label, or train on Google, Bing, or Esri basemap imagery.
- Keep non-commercial (NC) data and anything derived from it separate from commercially usable data.

## Week 1 exit criteria
- [x] License verified for at least one segmentation source (RID2, CC BY 4.0)
- [x] Obstacle classes chosen and defined in writing (`water_tank`, `solar_water_heater`)
- [x] Decision on evaluation set composition (Beirut CC BY 4.0 orthophoto; optional quarantined NC tier)
