"""Train the baseline U-Net (ResNet-18) on preprocessed RID2 tiles.

Usage (from the repo root):
    PYTHONPATH=ml ml/.venv/Scripts/python ml/scripts/train.py --data data/processed/rid2_gsd030

Selects the checkpoint with the best validation mean IoU over roof and
obstacle. The test split is never touched here.
"""

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
import segmentation_models_pytorch as smp
import torch
from PIL import Image
from torch import nn
from tqdm import tqdm

from wattwatch_ml.metrics import confusion, iou_per_class
from wattwatch_ml.preprocess import IGNORE_INDEX
from wattwatch_ml.rid2 import CLASS_NAMES, CLASS_OBSTACLE, CLASS_ROOF

IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


def load_split(data: Path, split_csv: Path, split: str) -> tuple[np.ndarray, np.ndarray]:
    with split_csv.open(encoding="utf-8") as f:
        names = sorted(r["image_name"] for r in csv.DictReader(f) if r["split"] == split)
    images = np.stack([np.asarray(Image.open(data / "images" / n)) for n in names])
    masks = np.stack([np.asarray(Image.open(data / "masks" / n)) for n in names])
    return images, masks


def to_input(images: torch.Tensor, device: torch.device) -> torch.Tensor:
    x = images.to(device).permute(0, 3, 1, 2).float() / 255.0
    return (x - IMAGENET_MEAN.to(device)) / IMAGENET_STD.to(device)


def augment(x: torch.Tensor, y: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Flips, 90-degree rotations (valid for top-down imagery) and mild colour jitter.

    Rotations are only applied when the tile is square; padding sits on the
    bottom/right, so rotating moves it, which is harmless because it is ignored.
    """
    if torch.rand(1) < 0.5:
        x, y = x.flip(-1), y.flip(-1)
    if torch.rand(1) < 0.5:
        x, y = x.flip(-2), y.flip(-2)
    k = int(torch.randint(0, 4, (1,)))
    x, y = torch.rot90(x, k, (-2, -1)), torch.rot90(y, k, (-2, -1))
    gain = 1 + 0.2 * (torch.rand(x.shape[0], 1, 1, 1, device=x.device) - 0.5)
    bias = 0.2 * (torch.rand(x.shape[0], 1, 1, 1, device=x.device) - 0.5)
    return (x * gain + bias).contiguous(), y.contiguous()


def class_weights(masks: np.ndarray) -> torch.Tensor:
    """Inverse square-root frequency, normalised to mean 1."""
    counts = np.bincount(masks[masks != IGNORE_INDEX].ravel(), minlength=len(CLASS_NAMES))
    w = 1.0 / np.sqrt(counts / counts.sum())
    return torch.tensor(w / w.mean(), dtype=torch.float32)


@torch.no_grad()
def evaluate(model, images, masks, device, batch: int, use_amp: bool) -> dict[str, float]:
    model.eval()
    conf = np.zeros((len(CLASS_NAMES),) * 2, dtype=np.int64)
    for i in range(0, len(images), batch):
        x = to_input(torch.from_numpy(images[i : i + batch]), device)
        with torch.autocast(device.type, dtype=torch.float16, enabled=use_amp):
            pred = model(x).argmax(1).cpu().numpy()
        conf += confusion(pred, masks[i : i + batch], len(CLASS_NAMES))
    iou = iou_per_class(conf)
    return {
        "iou_roof": float(iou[CLASS_ROOF]),
        "iou_obstacle": float(iou[CLASS_OBSTACLE]),
        "miou_roof_obstacle": float(np.nanmean(iou[[CLASS_ROOF, CLASS_OBSTACLE]])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", type=Path, default=Path("data/splits/rid2_split_v1.csv"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--amp",
        action="store_true",
        help="float16 mixed precision. Off by default: cuDNN 9.24 returns NaN from fp16 "
        "BatchNorm on the GeForce MX550 for most batch sizes.",
    )
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = args.amp and device.type == "cuda"
    manifest = json.loads((args.data / "manifest.json").read_text(encoding="utf-8"))
    out = args.out or Path("models") / f"baseline_{args.data.name}"
    out.mkdir(parents=True, exist_ok=True)

    train_x, train_y = load_split(args.data, args.split, "train")
    val_x, val_y = load_split(args.data, args.split, "val")
    weights = class_weights(train_y)
    print(f"train {len(train_x)} / val {len(val_x)} tiles, class weights {weights.tolist()}")

    model = smp.Unet("resnet18", encoder_weights="imagenet", classes=len(CLASS_NAMES)).to(device)
    ce = nn.CrossEntropyLoss(weight=weights.to(device), ignore_index=IGNORE_INDEX)
    dice = smp.losses.DiceLoss("multiclass", ignore_index=IGNORE_INDEX)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * ((len(train_x) + args.batch - 1) // args.batch)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=args.lr, total_steps=steps)
    scaler = torch.amp.GradScaler(enabled=use_amp)

    config = {**vars(args), "data": args.data.as_posix(), "split": args.split.as_posix()}
    config.pop("out")
    best, history, start = -1.0, [], time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = np.random.permutation(len(train_x))
        total = 0.0
        for i in tqdm(range(0, len(order), args.batch), desc=f"epoch {epoch}", leave=False):
            idx = np.sort(order[i : i + args.batch])
            x = to_input(torch.from_numpy(train_x[idx]), device)
            y = torch.from_numpy(train_y[idx]).to(device).long()
            x, y = augment(x, y)
            with torch.autocast(device.type, dtype=torch.float16, enabled=use_amp):
                logits = model(x)
            # Losses in float32: Dice sums ~400k pixels per batch, beyond float16's range.
            logits = logits.float()
            loss = ce(logits, y) + dice(logits, y)
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            total += loss.item() * len(idx)

        metrics = evaluate(model, val_x, val_y, device, args.batch, use_amp)
        record = {
            "epoch": epoch,
            "train_loss": round(total / len(train_x), 4),
            **{k: round(v, 4) for k, v in metrics.items()},
            "minutes": round((time.time() - start) / 60, 1),
        }
        history.append(record)
        print(json.dumps(record), flush=True)
        if metrics["miou_roof_obstacle"] > best:
            best = metrics["miou_roof_obstacle"]
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "arch": {"name": "Unet", "encoder": "resnet18", "classes": list(CLASS_NAMES)},
                    "epoch": epoch,
                    "val": metrics,
                    "config": config,
                    "data_manifest": manifest,
                },
                out / "best.pt",
            )

    (out / "history.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    print(f"best val mIoU(roof, obstacle) {best:.4f}; checkpoint {out / 'best.pt'}")


if __name__ == "__main__":
    main()
