"""U-Net roof model served with ONNX Runtime (exported by ml/scripts/export_onnx.py)."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.vision.postprocess import probabilities_to_prediction
from app.vision.types import RoofPrediction

WINDOW_PX = 1024
OVERLAP_PX = 64
STRIDE_PX = 32  # model input sides must be multiples of this


def _softmax(logits: np.ndarray) -> np.ndarray:
    e = np.exp(logits - logits.max(axis=0, keepdims=True))
    return e / e.sum(axis=0, keepdims=True)


def _window_starts(length: int) -> list[int]:
    if length <= WINDOW_PX:
        return [0]
    step = WINDOW_PX - OVERLAP_PX
    starts = list(range(0, length - WINDOW_PX, step))
    return starts + [length - WINDOW_PX]


class OnnxRoofModel:
    is_stub = False

    def __init__(self, session: Any) -> None:
        meta = session.get_modelmeta().custom_metadata_map
        self._session = session
        self.name = meta["name"]
        self.version = meta["version"]
        self.gsd_m = float(meta["gsd_m"])
        self.classes: list[str] = json.loads(meta["classes"])
        self._mean = np.array(json.loads(meta["mean"]), dtype=np.float32).reshape(3, 1, 1)
        self._std = np.array(json.loads(meta["std"]), dtype=np.float32).reshape(3, 1, 1)
        self.limitations = self._limitations(json.loads(meta.get("test_metrics", "{}")))

    @classmethod
    def from_path(cls, path: str | Path) -> "OnnxRoofModel":
        import onnxruntime as ort

        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Model file {path} not found. Run backend/scripts/fetch_model.py, "
                "or set VISION_MODEL=stub."
            )
        return cls(ort.InferenceSession(str(path), providers=["CPUExecutionProvider"]))

    def _limitations(self, metrics: dict) -> tuple[str, ...]:
        notes = [
            f"Assumes top-down imagery at about {self.gsd_m:g} m per pixel. Other scales "
            "and oblique photos give unreliable results; image scale is not checked yet.",
            "Trained on Dutch aerial imagery (RID2, CC BY 4.0); not yet validated on "
            "Lebanese roofs.",
            "Obstacles are one merged class (chimneys, windows, solar panels and similar); "
            "water tanks and solar water heaters are not yet distinguished.",
        ]
        strict = (metrics.get("obstacle_instances") or {}).get("iou>=0.5") or {}
        if metrics.get("iou_roof") is not None and strict.get("recall") is not None:
            notes.append(
                f"On held-out test data: roof IoU {metrics['iou_roof']:.2f}; about "
                f"{strict['recall']:.0%} of obstacles found with a matching outline."
            )
        return tuple(notes)

    def _infer(self, window: np.ndarray) -> np.ndarray:
        """Class probabilities (C, h, w) for one RGB window, padded to the model stride."""
        h, w = window.shape[:2]
        ph, pw = -h % STRIDE_PX, -w % STRIDE_PX
        padded = np.pad(window, ((0, ph), (0, pw), (0, 0)), mode="symmetric")
        x = padded.transpose(2, 0, 1).astype(np.float32) / 255.0
        x = ((x - self._mean) / self._std)[None]
        logits = self._session.run(None, {"image": x})[0][0]
        return _softmax(logits)[:, :h, :w]

    def probabilities(self, image: Image.Image) -> np.ndarray:
        """Average class probabilities over overlapping windows covering the image."""
        arr = np.asarray(image.convert("RGB"))
        h, w = arr.shape[:2]
        total = np.zeros((len(self.classes), h, w), dtype=np.float32)
        count = np.zeros((h, w), dtype=np.float32)
        for y in _window_starts(h):
            for x in _window_starts(w):
                window = arr[y : y + WINDOW_PX, x : x + WINDOW_PX]
                wh, ww = window.shape[:2]
                total[:, y : y + wh, x : x + ww] += self._infer(window)
                count[y : y + wh, x : x + ww] += 1
        return total / count

    def predict(self, image: Image.Image) -> RoofPrediction:
        return probabilities_to_prediction(self.probabilities(image), self.classes, self.gsd_m)
