"""Segmentation and instance metrics (see docs/MODEL_DECISION.md, Evaluation)."""

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from wattwatch_ml.preprocess import IGNORE_INDEX


def confusion(pred: np.ndarray, target: np.ndarray, num_classes: int) -> np.ndarray:
    """Confusion matrix [target, pred], skipping IGNORE_INDEX target pixels."""
    valid = target != IGNORE_INDEX
    idx = target[valid].astype(np.int64) * num_classes + pred[valid].astype(np.int64)
    return np.bincount(idx, minlength=num_classes**2).reshape(num_classes, num_classes)


def iou_per_class(conf: np.ndarray) -> np.ndarray:
    tp = np.diag(conf).astype(float)
    denom = conf.sum(0) + conf.sum(1) - tp
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(denom > 0, tp / denom, np.nan)


@dataclass
class InstanceCounts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def __iadd__(self, other: "InstanceCounts") -> "InstanceCounts":
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn
        return self

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else float("nan")

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else float("nan")


def _components(mask: np.ndarray, min_pixels: int) -> tuple[np.ndarray, int]:
    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n and min_pixels > 1:
        sizes = np.bincount(labels.ravel(), minlength=n + 1)
        small = sizes < min_pixels
        small[0] = False
        labels[small[labels]] = 0
        labels, n = ndimage.label(labels > 0, structure=np.ones((3, 3)))
    return labels, n


def match_instances(
    pred: np.ndarray, target: np.ndarray, iou_threshold: float, min_pixels: int = 1
) -> InstanceCounts:
    """One-to-one greedy matching of connected components by IoU.

    `pred` and `target` are boolean masks of one class. Components smaller than
    `min_pixels` are dropped on both sides before matching.
    """
    p_lab, n_p = _components(pred, min_pixels)
    t_lab, n_t = _components(target, min_pixels)
    if n_p == 0 or n_t == 0:
        return InstanceCounts(tp=0, fp=n_p, fn=n_t)

    overlap = np.bincount(
        p_lab.ravel() * (n_t + 1) + t_lab.ravel(), minlength=(n_p + 1) * (n_t + 1)
    ).reshape(n_p + 1, n_t + 1)
    p_area = np.bincount(p_lab.ravel(), minlength=n_p + 1)
    t_area = np.bincount(t_lab.ravel(), minlength=n_t + 1)
    inter = overlap[1:, 1:].astype(float)
    union = p_area[1:, None] + t_area[None, 1:] - inter
    iou = inter / union

    pairs = np.argwhere(iou >= iou_threshold)
    order = np.argsort(-iou[pairs[:, 0], pairs[:, 1]])
    used_p, used_t = set(), set()
    for i, j in pairs[order]:
        if i not in used_p and j not in used_t:
            used_p.add(i)
            used_t.add(j)
    tp = len(used_p)
    return InstanceCounts(tp=tp, fp=n_p - tp, fn=n_t - tp)
