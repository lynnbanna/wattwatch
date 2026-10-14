"""Resample RID2 tiles to a target GSD for training and evaluation.

Usage (from the repo root):
    PYTHONPATH=ml ml/.venv/Scripts/python ml/scripts/preprocess_rid2.py --gsd 0.3

Writes data/processed/rid2_gsd<NNN>/{images,masks}/<tile>.png plus manifest.json.
Images are padded to a multiple of 32 px (reflect); padded mask pixels are 255
(ignored by training and evaluation). Masks use background/roof/obstacle indices.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from tqdm import tqdm

from wattwatch_ml.preprocess import pad_to_stride, resample_image, resample_mask, resampled_size
from wattwatch_ml.rid2 import CLASS_NAMES, TILE_GSD_M, TILE_SIZE_PX, baseline_mask


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gsd", type=float, required=True, help="target metres per pixel")
    parser.add_argument("--rid2", type=Path, default=Path("data/raw/rid2"))
    parser.add_argument("--split", type=Path, default=Path("data/splits/rid2_split_v1.csv"))
    parser.add_argument("--out-root", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    out = args.out_root / f"rid2_gsd{round(args.gsd * 100):03d}"
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "masks").mkdir(parents=True, exist_ok=True)

    side = resampled_size(TILE_SIZE_PX, TILE_GSD_M, args.gsd)
    with args.split.open(encoding="utf-8") as f:
        names = [row["image_name"] for row in csv.DictReader(f)]

    for name in tqdm(names, desc=f"GSD {args.gsd} m"):
        image = resample_image(Image.open(args.rid2 / "images" / name), (side, side))
        seg = np.array(Image.open(args.rid2 / "masks" / "masks_segments" / name))
        sup = np.array(Image.open(args.rid2 / "masks" / "masks_superstructures" / name))
        mask = resample_mask(baseline_mask(seg, sup), (side, side), len(CLASS_NAMES))
        image_arr, mask = pad_to_stride(np.asarray(image), mask)
        Image.fromarray(image_arr).save(out / "images" / name)
        Image.fromarray(mask).save(out / "masks" / name)

    manifest = {
        "source": "RID2 v1.0 (doi:10.5281/zenodo.14062580)",
        "split_csv": args.split.as_posix(),
        "split_sha256": hashlib.sha256(args.split.read_bytes()).hexdigest(),
        "gsd_m": args.gsd,
        "content_px": side,
        "padded_px": int(mask.shape[0]),
        "classes": list(CLASS_NAMES),
        "ignore_index": 255,
        "tiles": len(names),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
