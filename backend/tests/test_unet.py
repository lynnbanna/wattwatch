import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from app.core.config import get_settings
from app.vision.postprocess import probabilities_to_prediction
from app.vision.unet import WINDOW_PX, OnnxRoofModel, _window_starts

CLASSES = ["background", "roof", "obstacle"]


def _probs(h: int, w: int) -> np.ndarray:
    probs = np.zeros((3, h, w), dtype=np.float32)
    probs[0] = 1.0
    return probs


def _paint(probs: np.ndarray, cls: int, y0: int, y1: int, x0: int, x1: int, p: float = 0.9):
    probs[:, y0:y1, x0:x1] = (1 - p) / 2
    probs[cls, y0:y1, x0:x1] = p


def test_roof_with_obstacle_becomes_one_roof_and_one_obstacle():
    probs = _probs(100, 100)
    _paint(probs, 1, 10, 90, 10, 90)
    _paint(probs, 2, 30, 40, 30, 40, p=0.8)
    pred = probabilities_to_prediction(probs, CLASSES, gsd_m=0.15)
    assert len(pred.roofs) == 1 and len(pred.obstacles) == 1
    xs = [x for x, _ in pred.roofs[0].polygon]
    assert min(xs) == 10 and max(xs) == 89
    assert pred.obstacles[0].score == pytest.approx(0.8)
    assert pred.roofs[0].score == pytest.approx(0.95, abs=0.01)  # P(roof) + P(obstacle)


def test_regions_below_minimum_area_are_dropped():
    probs = _probs(100, 100)
    _paint(probs, 1, 0, 5, 0, 5)  # 25 px x 0.0225 m2 = 0.56 m2 < 4 m2 roof minimum
    _paint(probs, 2, 50, 52, 50, 52)  # 4 px = 0.09 m2 < 0.25 m2 obstacle minimum
    pred = probabilities_to_prediction(probs, CLASSES, gsd_m=0.15)
    assert pred.roofs == [] or all(len(r.polygon) >= 3 for r in pred.roofs)
    assert pred.obstacles == []
    assert all(min(x for x, _ in r.polygon) >= 49 for r in pred.roofs)


def test_window_starts_cover_long_sides_with_overlap():
    assert _window_starts(500) == [0]
    starts = _window_starts(2500)
    assert starts[0] == 0 and starts[-1] == 2500 - WINDOW_PX
    assert all(b - a < WINDOW_PX for a, b in zip(starts, starts[1:], strict=False))


class FakeSession:
    """Mimics onnxruntime: marks the left half of every input as roof."""

    def __init__(self):
        self.shapes = []

    def get_modelmeta(self):
        return SimpleNamespace(
            custom_metadata_map={
                "name": "roof-unet-r18",
                "version": "9.9.9",
                "gsd_m": "0.15",
                "classes": json.dumps(CLASSES),
                "mean": "[0.5, 0.5, 0.5]",
                "std": "[0.5, 0.5, 0.5]",
                "test_metrics": json.dumps(
                    {"iou_roof": 0.75, "obstacle_instances": {"iou>=0.5": {"recall": 0.545}}}
                ),
            }
        )

    def run(self, _outputs, feeds):
        x = feeds["image"]
        self.shapes.append(x.shape)
        _, _, h, w = x.shape
        logits = np.zeros((1, 3, h, w), dtype=np.float32)
        logits[0, 0] = 5.0
        logits[0, 1, :, : w // 2] = 10.0
        return [logits]


def test_onnx_model_pads_inputs_and_maps_back_to_image_pixels():
    session = FakeSession()
    model = OnnxRoofModel(session)
    pred = model.predict(Image.new("RGB", (300, 200)))
    assert all(h % 32 == 0 and w % 32 == 0 for _, _, h, w in session.shapes)
    assert len(pred.roofs) == 1
    xs = [x for x, _ in pred.roofs[0].polygon]
    ys = [y for _, y in pred.roofs[0].polygon]
    assert max(ys) <= 199 and max(xs) < 300


def test_onnx_model_tiles_large_images():
    session = FakeSession()
    probs = OnnxRoofModel(session).probabilities(Image.new("RGB", (2500, 300)))
    assert probs.shape == (3, 300, 2500)
    assert len(session.shapes) == len(_window_starts(2500))
    np.testing.assert_allclose(probs.sum(0), 1.0, rtol=1e-5)


def test_onnx_model_reports_metadata_and_limitations():
    model = OnnxRoofModel(FakeSession())
    assert (model.name, model.version, model.gsd_m, model.is_stub) == (
        "roof-unet-r18",
        "9.9.9",
        0.15,
        False,
    )
    notes = " ".join(model.limitations)
    assert "0.15 m per pixel" in notes
    assert "roof IoU 0.75" in notes and "55%" in notes


def test_missing_model_file_has_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="fetch_model"):
        OnnxRoofModel.from_path(tmp_path / "missing.onnx")


MODEL_PATH = Path(__file__).resolve().parents[1] / get_settings().vision_model_path


@pytest.mark.skipif(not MODEL_PATH.is_file(), reason="model file not downloaded")
def test_real_model_runs_end_to_end():
    model = OnnxRoofModel.from_path(MODEL_PATH)
    pred = model.predict(Image.new("RGB", (320, 288), (128, 128, 128)))
    assert model.gsd_m == 0.15
    for d in pred.roofs + pred.obstacles:
        assert 0 <= d.score <= 1
