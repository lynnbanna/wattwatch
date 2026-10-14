"""Evaluate a trained checkpoint on the frozen held-out test split.

Usage (from the repo root):
    PYTHONPATH=ml ml/.venv/Scripts/python ml/scripts/evaluate.py --checkpoint models/<run>/best.pt

Predictions made at the model's GSD are upsampled to RID2's native 0.08 m grid
and scored against the native labels, so runs at different GSDs are compared
against the same ground truth. Writes <run>/test_metrics.json.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import segmentation_models_pytorch as smp
import torch
import torch.nn.functional as F
from PIL import Image
from tqdm import tqdm

from wattwatch_ml.metrics import InstanceCounts, confusion, iou_per_class, match_instances
from wattwatch_ml.rid2 import (
    CLASS_NAMES,
    CLASS_OBSTACLE,
    CLASS_ROOF,
    TILE_GSD_M,
    TILE_SIZE_PX,
    baseline_mask,
)

IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
MIN_OBSTACLE_AREA_M2 = 0.25
IOU_THRESHOLDS = (0.5, 0.25)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--rid2", type=Path, default=Path("data/raw/rid2"))
    parser.add_argument("--split-name", default="test")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    manifest = ckpt["data_manifest"]
    data = Path(ckpt["config"]["data"])
    split_csv = Path(ckpt["config"]["split"])
    split_sha = hashlib.sha256(split_csv.read_bytes()).hexdigest()
    if split_sha != manifest["split_sha256"]:
        raise SystemExit("Split file changed since preprocessing; refusing to evaluate.")

    model = smp.Unet("resnet18", encoder_weights=None, classes=len(CLASS_NAMES)).to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    with split_csv.open(encoding="utf-8") as f:
        names = sorted(r["image_name"] for r in csv.DictReader(f) if r["split"] == args.split_name)

    content = manifest["content_px"]
    min_pixels = round(MIN_OBSTACLE_AREA_M2 / TILE_GSD_M**2)
    conf = np.zeros((len(CLASS_NAMES),) * 2, dtype=np.int64)
    counts = {t: InstanceCounts() for t in IOU_THRESHOLDS}
    with torch.no_grad():
        for name in tqdm(names, desc="evaluating"):
            image = np.asarray(Image.open(data / "images" / name))
            x = torch.from_numpy(image).to(device).permute(2, 0, 1)[None].float() / 255.0
            x = (x - IMAGENET_MEAN.to(device)) / IMAGENET_STD.to(device)
            logits = model(x)  # float32: see train.py --amp
            probs = logits.float().softmax(1)[:, :, :content, :content]
            probs = F.interpolate(
                probs, size=(TILE_SIZE_PX, TILE_SIZE_PX), mode="bilinear", align_corners=False
            )
            pred = probs.argmax(1)[0].cpu().numpy()

            seg = np.array(Image.open(args.rid2 / "masks" / "masks_segments" / name))
            sup = np.array(Image.open(args.rid2 / "masks" / "masks_superstructures" / name))
            target = baseline_mask(seg, sup)

            conf += confusion(pred, target, len(CLASS_NAMES))
            for t in IOU_THRESHOLDS:
                counts[t] += match_instances(
                    pred == CLASS_OBSTACLE, target == CLASS_OBSTACLE, t, min_pixels
                )

    iou = iou_per_class(conf)
    result = {
        "checkpoint": args.checkpoint.as_posix(),
        "split": args.split_name,
        "split_sha256": split_sha,
        "tiles": len(names),
        "model_gsd_m": manifest["gsd_m"],
        "scored_at_gsd_m": TILE_GSD_M,
        "best_epoch": ckpt["epoch"],
        "val": ckpt["val"],
        "iou_roof": round(float(iou[CLASS_ROOF]), 4),
        "iou_obstacle": round(float(iou[CLASS_OBSTACLE]), 4),
        "obstacle_instances": {
            f"iou>={t}": {
                "precision": round(c.precision, 4),
                "recall": round(c.recall, 4),
                "tp": c.tp,
                "fp": c.fp,
                "fn": c.fn,
            }
            for t, c in counts.items()
        },
        "min_obstacle_area_m2": MIN_OBSTACLE_AREA_M2,
    }
    out = args.checkpoint.parent / f"{args.split_name}_metrics.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
