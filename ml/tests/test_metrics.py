import math

import numpy as np

from wattwatch_ml.metrics import confusion, iou_per_class, match_instances
from wattwatch_ml.preprocess import IGNORE_INDEX


def test_confusion_skips_ignored_pixels():
    target = np.array([[0, 1], [IGNORE_INDEX, 1]])
    pred = np.array([[0, 1], [1, 0]])
    conf = confusion(pred, target, num_classes=2)
    assert conf.tolist() == [[1, 0], [1, 1]]


def test_iou_per_class():
    conf = np.array([[1, 0], [1, 1]])
    np.testing.assert_allclose(iou_per_class(conf), [0.5, 0.5])


def test_iou_is_nan_for_absent_class():
    conf = np.array([[4, 0], [0, 0]])
    assert math.isnan(iou_per_class(conf)[1])


def _square(mask, y, x, s):
    mask[y : y + s, x : x + s] = True


def test_match_counts_tp_fp_fn():
    target = np.zeros((20, 20), bool)
    pred = np.zeros((20, 20), bool)
    _square(target, 0, 0, 4)  # matched exactly
    _square(pred, 0, 0, 4)
    _square(target, 10, 10, 4)  # missed
    _square(pred, 0, 12, 3)  # false alarm
    counts = match_instances(pred, target, iou_threshold=0.5)
    assert (counts.tp, counts.fp, counts.fn) == (1, 1, 1)
    assert counts.precision == 0.5 and counts.recall == 0.5


def test_low_overlap_is_not_a_match():
    target = np.zeros((10, 10), bool)
    pred = np.zeros((10, 10), bool)
    _square(target, 0, 0, 4)
    _square(pred, 0, 3, 4)  # IoU = 4 / 28
    counts = match_instances(pred, target, iou_threshold=0.5)
    assert (counts.tp, counts.fp, counts.fn) == (0, 1, 1)


def test_matching_is_one_to_one():
    target = np.zeros((10, 10), bool)
    pred = np.zeros((10, 10), bool)
    _square(target, 0, 0, 4)
    _square(target, 0, 5, 4)
    pred[0:4, 0:9] = True  # one blob covering both targets
    counts = match_instances(pred, target, iou_threshold=0.4)
    assert counts.tp <= 1


def test_small_components_are_dropped():
    target = np.zeros((10, 10), bool)
    pred = np.zeros((10, 10), bool)
    target[0, 0] = True
    counts = match_instances(pred, target, iou_threshold=0.5, min_pixels=4)
    assert (counts.tp, counts.fp, counts.fn) == (0, 0, 0)
