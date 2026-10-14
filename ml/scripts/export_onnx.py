"""Export a trained checkpoint to ONNX for serving, and verify it against PyTorch.

Usage (from the repo root):
    PYTHONPATH=ml ml/.venv/Scripts/python ml/scripts/export_onnx.py \
        --checkpoint models/baseline_rid2_gsd015/best.pt --version 0.1.0

Writes models/roof_unet_r18_gsd<NNN>_v<version>.onnx with metadata (GSD,
classes, normalisation, test metrics) and prints its SHA-256.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import segmentation_models_pytorch as smp
import torch

from wattwatch_ml.rid2 import CLASS_NAMES

MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("models"))
    args = parser.parse_args()

    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    gsd = ckpt["data_manifest"]["gsd_m"]
    model = smp.Unet("resnet18", encoder_weights=None, classes=len(CLASS_NAMES))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    out = args.out_dir / f"roof_unet_r18_gsd{round(gsd * 100):03d}_v{args.version}.onnx"
    example = torch.randn(1, 3, 288, 288)
    torch.onnx.export(
        model,
        (example,),
        out,
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={"image": {0: "batch", 2: "height", 3: "width"}, "logits": {0: "batch"}},
        opset_version=18,
        dynamo=False,
    )

    test_metrics_path = args.checkpoint.parent / "test_metrics.json"
    test_metrics = (
        json.loads(test_metrics_path.read_text(encoding="utf-8"))
        if test_metrics_path.exists()
        else {}
    )
    metadata = {
        "name": "roof-unet-r18",
        "version": args.version,
        "gsd_m": str(gsd),
        "classes": json.dumps(list(CLASS_NAMES)),
        "input": "RGB float32 NCHW, (x/255 - mean) / std; height and width multiples of 32",
        "mean": json.dumps(MEAN),
        "std": json.dumps(STD),
        "training_data": "RID2 v1.0, doi:10.5281/zenodo.14062580, CC BY 4.0",
        "test_metrics": json.dumps(
            {
                k: test_metrics.get(k)
                for k in ("iou_roof", "iou_obstacle", "obstacle_instances", "split_sha256")
            }
        ),
    }
    proto = onnx.load(out)
    for key, value in metadata.items():
        entry = proto.metadata_props.add()
        entry.key, entry.value = key, value
    onnx.checker.check_model(proto)
    onnx.save(proto, out)

    session = ort.InferenceSession(out, providers=["CPUExecutionProvider"])
    for h, w in ((288, 288), (320, 480)):
        x = torch.randn(1, 3, h, w)
        with torch.no_grad():
            expected = model(x).numpy()
        got = session.run(None, {"image": x.numpy()})[0]
        diff = float(np.abs(expected - got).max())
        print(f"{h}x{w}: max |torch - onnx| = {diff:.2e}")
        if diff > 1e-3:
            raise SystemExit("ONNX output does not match PyTorch")

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"{out} ({out.stat().st_size / 1e6:.1f} MB) sha256 {digest}")


if __name__ == "__main__":
    main()
