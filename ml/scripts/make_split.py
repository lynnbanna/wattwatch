"""Freeze a region-based train / val / test split of RID2.

Usage (from the repo root):
    ml/.venv/Scripts/python ml/scripts/make_split.py

Writes data/splits/rid2_split_v1.csv (one row per tile) and a JSON summary
with the CSV's SHA-256, per-split tile counts, class pixel shares, and the
minimum distance between test and training tiles. Never regenerate v1;
make a v2 instead, so recorded metrics stay traceable.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from wattwatch_ml.rid2 import (
    CLASS_NAMES,
    baseline_mask,
    group_regions,
    split_regions,
    tile_xy,
    tiles_in,
)

FRACTIONS = {"train": 0.70, "val": 0.15, "test": 0.15}
SEED = 42


def class_shares(root: Path, names: list[str]) -> dict[str, float]:
    counts = np.zeros(len(CLASS_NAMES), dtype=np.int64)
    for name in names:
        seg = np.array(Image.open(root / "masks" / "masks_segments" / name))
        sup = np.array(Image.open(root / "masks" / "masks_superstructures" / name))
        counts += np.bincount(baseline_mask(seg, sup).ravel(), minlength=len(CLASS_NAMES))
    return {c: round(float(n / counts.sum()), 4) for c, n in zip(CLASS_NAMES, counts, strict=True)}


def min_distance_m(a: list[str], b: list[str]) -> float:
    xa = np.array([tile_xy(n) for n in a])
    xb = np.array([tile_xy(n) for n in b])
    return float(np.sqrt(((xa[:, None, :] - xb[None, :, :]) ** 2).sum(-1)).min())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rid2", type=Path, default=Path("data/raw/rid2"))
    parser.add_argument("--out", type=Path, default=Path("data/splits/rid2_split_v1.csv"))
    args = parser.parse_args()

    names = sorted(p.name for p in (args.rid2 / "images").glob("*.png"))
    regions = group_regions(names)
    assignment = split_regions(Counter(regions), FRACTIONS, SEED)
    split_of = {n: assignment[r] for n, r in zip(names, regions, strict=True)}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["image_name,region,split"] + [
        f"{n},{r},{split_of[n]}" for n, r in zip(names, regions, strict=True)
    ]
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    by_split = {s: tiles_in(names, split_of, s) for s in FRACTIONS}
    summary = {
        "csv": args.out.name,
        "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
        "seed": SEED,
        "region_link_distance_m": 1000,
        "regions": len(set(regions)),
        "tiles": {s: len(t) for s, t in by_split.items()},
        "regions_per_split": dict(Counter(assignment.values())),
        "min_test_to_train_distance_m": round(min_distance_m(by_split["test"], by_split["train"])),
        "min_val_to_train_distance_m": round(min_distance_m(by_split["val"], by_split["train"])),
        "class_pixel_share": {s: class_shares(args.rid2, t) for s, t in by_split.items()},
    }
    args.out.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
