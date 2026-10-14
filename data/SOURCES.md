# Data Sources

Register of every dataset used by WattWatch. Add an entry **before** using a
source, and fill in the download date when data lands in `data/raw/`.
Licence review and decisions: [docs/DATA_PLAN.md](../docs/DATA_PLAN.md).

| Source | Use | License | Downloaded | Local path | Attribution |
|---|---|---|---|---|---|
| RID2 — [zenodo.org/records/14062580](https://zenodo.org/records/14062580) (v1.0) | Roof segmentation training; obstacle pretraining | CC BY 4.0 | not yet | `data/raw/rid2/` | Krapf, Ganß, Zinniel, Lienkamp, "RID2", Zenodo, doi:10.5281/zenodo.14062580. Imagery © Beeldmateriaal Nederland, CC BY 4.0. Modified: downsampled and re-tiled. |
| Beirut port drone orthophoto, 2020-08-04, 0.121 m — [OpenAerialMap](https://openaerialmap.org/) | **Reviewed, not used:** covers only the port blast zone, no residential roofs (see DATA_PLAN.md) | CC BY 4.0 | 2026-10-14 | `data/raw/oam_beirut_ccby/` | UAV imagery supplied by Rabih El Zein (@rabzthecopter); orthoimage by @GeoConor; via OpenAerialMap, CC BY 4.0. |
| Maxar/Planet Beirut scenes, 0.42–0.63 m — [OpenAerialMap](https://openaerialmap.org/) | *Optional* non-commercial evaluation tier | CC BY-NC 4.0 | not yet | `data/raw/nc/oam_beirut_ccbync/` | Provider and title from each image's metadata, CC BY-NC 4.0. **Non-commercial only — keep out of any commercial build.** |
| Microsoft Global ML Building Footprints — [github.com/microsoft/GlobalMLBuildingFootprints](https://github.com/microsoft/GlobalMLBuildingFootprints) | Roof cropping, weak masks (Lebanon) | CDLA-Permissive-2.0 | not yet | `data/raw/ms_footprints/` | Microsoft Global ML Building Footprints, CDLA-Permissive-2.0. |
| PVGIS 5.3 API — [re.jrc.ec.europa.eu/api/v5_3/](https://re.jrc.ec.europa.eu/api/v5_3/) | Solar resource (called server-side at runtime) | Free reuse with acknowledgement | n/a (API) | n/a | PVGIS © European Communities, 2001-2026. |

## Not permitted
Google, Bing, and Esri basemap imagery — their terms forbid tracing and ML
training. RID v1 is excluded for the same reason (Google imagery).
