"""Measure area-estimation error of the served pipeline against RID2 reference outlines.

Usage (from the repo root):
    PYTHONPATH="ml;backend" ml/.venv/Scripts/python ml/scripts/area_error.py

Runs the API's own code path (ONNX model, resampling, polygonisation, area
measurement) on the frozen test split and compares with RID2's hand-drawn roof
and superstructure outlines (EPSG:28992 metres). Writes area_error.json next to
the model's checkpoint folder.

- Tile level: roof and usable area inside each 40.96 m tile.
- Building level: reference buildings lying fully inside a tile, matched
  one-to-one to predicted roofs at IoU >= 0.5; also detection, merge rates.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from shapely import STRtree, box, make_valid, unary_union
from shapely.geometry import Polygon, shape
from tqdm import tqdm

from app.measure.area import DEFAULT_EDGE_SETBACK_M, DEFAULT_OBSTACLE_CLEARANCE_M, measure
from app.vision.resample import resample_to_gsd
from app.vision.unet import OnnxRoofModel
from wattwatch_ml.rid2 import TILE_GSD_M, TILE_SIZE_PX, tile_xy

TILE_M = TILE_SIZE_PX * TILE_GSD_M
MIN_TILE_ROOF_M2 = 25.0  # relative errors on near-empty tiles are meaningless
MATCH_IOU = 0.5
DETECT_COVERAGE = 0.5


def load_outlines(path: Path) -> tuple[list, STRtree]:
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    geoms = [make_valid(shape(f["geometry"])) for f in features]
    return geoms, STRtree(geoms)


def clipped(geoms: list, tree: STRtree, tile: Polygon) -> list:
    return [
        g.intersection(tile) for g in (geoms[i] for i in tree.query(tile, predicate="intersects"))
    ]


def to_map(polygon_px, x0: float, y0: float) -> Polygon:
    return make_valid(Polygon([(x0 + x * TILE_GSD_M, y0 - y * TILE_GSD_M) for x, y in polygon_px]))


def summarise(pred: np.ndarray, ref: np.ndarray) -> dict:
    keep = ref >= MIN_TILE_ROOF_M2
    rel = (pred[keep] - ref[keep]) / ref[keep]
    return {
        "tiles": int(keep.sum()),
        "mean_abs_error_m2": round(float(np.abs(pred[keep] - ref[keep]).mean()), 2),
        "median_abs_pct_error": round(float(np.median(np.abs(rel)) * 100), 1),
        "p90_abs_pct_error": round(float(np.percentile(np.abs(rel), 90) * 100), 1),
        "mean_signed_pct_error": round(float(rel.mean() * 100), 1),
        "total_pct_error": round(float((pred[keep].sum() / ref[keep].sum() - 1) * 100), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--model", type=Path, default=Path("models/roof_unet_r18_gsd015_v0.1.0.onnx")
    )
    parser.add_argument("--rid2", type=Path, default=Path("data/raw/rid2"))
    parser.add_argument("--split", type=Path, default=Path("data/splits/rid2_split_v1.csv"))
    parser.add_argument(
        "--out", type=Path, default=Path("models/baseline_rid2_gsd015/area_error.json")
    )
    args = parser.parse_args()

    model = OnnxRoofModel.from_path(args.model)
    roofs, roof_tree = load_outlines(args.rid2 / "geometries" / "gdf_all_outlines.json")
    sups, sup_tree = load_outlines(args.rid2 / "geometries" / "gdf_all_superstructures.json")
    with args.split.open(encoding="utf-8") as f:
        names = sorted(r["image_name"] for r in csv.DictReader(f) if r["split"] == "test")

    tile_rows = []
    buildings = {"reference": 0, "detected": 0, "matched": 0, "in_merged_prediction": 0}
    building_rel_errors = []
    for name in tqdm(names, desc="tiles"):
        x0, y0 = tile_xy(name)
        tile = box(x0, y0 - TILE_M, x0 + TILE_M, y0)
        image = Image.open(args.rid2 / "images" / name).convert("RGB")
        resampled = resample_to_gsd(image, TILE_GSD_M, model.gsd_m)
        pred = model.predict(resampled.image)
        pred_roofs = [to_map(resampled.to_original(d.polygon), x0, y0) for d in pred.roofs]
        pred_obs = [to_map(resampled.to_original(d.polygon), x0, y0) for d in pred.obstacles]
        ref_roofs = clipped(roofs, roof_tree, tile)
        ref_obs = clipped(sups, sup_tree, tile)

        # Same measurement code as the API; coordinates are already metres (gsd = 1).
        def coords(geoms):
            return [
                list(p.exterior.coords)
                for g in geoms
                for p in getattr(g, "geoms", [g])
                if isinstance(p, Polygon) and not p.is_empty
            ]

        mp = measure(
            coords(pred_roofs),
            coords(pred_obs),
            1.0,
            DEFAULT_EDGE_SETBACK_M,
            DEFAULT_OBSTACLE_CLEARANCE_M,
        )
        mr = measure(
            coords(ref_roofs),
            coords(ref_obs),
            1.0,
            DEFAULT_EDGE_SETBACK_M,
            DEFAULT_OBSTACLE_CLEARANCE_M,
        )
        tile_rows.append((mp.roof_area_m2, mr.roof_area_m2, mp.usable_area_m2, mr.usable_area_m2))

        # Building level: reference buildings fully inside the tile.
        inside = [roofs[i] for i in roof_tree.query(tile, predicate="contains")]
        pred_union = unary_union(pred_roofs) if pred_roofs else Polygon()
        used = set()
        for ref in inside:
            buildings["reference"] += 1
            if ref.area == 0:
                continue
            if pred_union.intersection(ref).area / ref.area >= DETECT_COVERAGE:
                buildings["detected"] += 1
            best, best_iou = None, 0.0
            for j, p in enumerate(pred_roofs):
                if j in used or not p.intersects(ref):
                    continue
                iou = p.intersection(ref).area / p.union(ref).area
                if iou > best_iou:
                    best, best_iou = j, iou
            if best is not None and best_iou >= MATCH_IOU:
                used.add(best)
                buildings["matched"] += 1
                building_rel_errors.append((pred_roofs[best].area - ref.area) / ref.area)
            covering = [
                p for p in pred_roofs if p.intersection(ref).area / ref.area >= DETECT_COVERAGE
            ]
            if any(
                sum(p.intersection(o).area / o.area >= DETECT_COVERAGE for o in inside if o.area)
                >= 2
                for p in covering
            ):
                buildings["in_merged_prediction"] += 1

    rows = np.array(tile_rows)
    rel = np.array(building_rel_errors)
    n = buildings["reference"]
    result = {
        "model": f"{model.name} v{model.version}",
        "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
        "split_sha256": hashlib.sha256(args.split.read_bytes()).hexdigest(),
        "tiles_evaluated": len(names),
        "edge_setback_m": DEFAULT_EDGE_SETBACK_M,
        "obstacle_clearance_m": DEFAULT_OBSTACLE_CLEARANCE_M,
        "tile_roof_area": summarise(rows[:, 0], rows[:, 1]),
        "tile_usable_area": summarise(rows[:, 2], rows[:, 3]),
        "buildings": {
            **buildings,
            "detected_pct": round(100 * buildings["detected"] / n, 1),
            "matched_pct": round(100 * buildings["matched"] / n, 1),
            "in_merged_prediction_pct": round(100 * buildings["in_merged_prediction"] / n, 1),
            "matched_median_abs_pct_error": round(float(np.median(np.abs(rel)) * 100), 1),
            "matched_p90_abs_pct_error": round(float(np.percentile(np.abs(rel), 90) * 100), 1),
            "matched_mean_signed_pct_error": round(float(rel.mean() * 100), 1),
        },
    }
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
