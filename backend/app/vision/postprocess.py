"""Turn per-pixel class probabilities into roof and obstacle polygons."""

import cv2
import numpy as np

from app.vision.types import Detection, RoofPrediction

MIN_ROOF_AREA_M2 = 4.0
MIN_OBSTACLE_AREA_M2 = 0.25  # same threshold as the evaluation (docs/METRICS.md)
SIMPLIFY_TOLERANCE_PX = 1.0


def _regions(mask: np.ndarray, score: np.ndarray, label: str, min_px: int) -> list[Detection]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    detections = []
    for i in range(1, count):
        if stats[i, cv2.CC_STAT_AREA] < min_px:
            continue
        component = labels == i
        contours, _ = cv2.findContours(
            component.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        outline = cv2.approxPolyDP(
            max(contours, key=cv2.contourArea), SIMPLIFY_TOLERANCE_PX, closed=True
        )
        if len(outline) < 3:
            continue
        polygon = [(float(x), float(y)) for [[x, y]] in outline]
        detections.append(Detection(label, float(score[component].mean()), polygon))
    return detections


def probabilities_to_prediction(
    probs: np.ndarray, classes: list[str], gsd_m: float
) -> RoofPrediction:
    """`probs` is (classes, height, width) softmax output; `gsd_m` is metres per pixel.

    Roofs include the obstacles sitting on them. The score is the mean
    probability of the region's class (for roofs, roof + obstacle) over the region.
    """
    roof, obstacle = classes.index("roof"), classes.index("obstacle")
    predicted = probs.argmax(axis=0)
    pixel_m2 = gsd_m**2
    roofs = _regions(
        (predicted == roof) | (predicted == obstacle),
        probs[roof] + probs[obstacle],
        "roof",
        round(MIN_ROOF_AREA_M2 / pixel_m2),
    )
    obstacles = _regions(
        predicted == obstacle,
        probs[obstacle],
        "obstacle",
        round(MIN_OBSTACLE_AREA_M2 / pixel_m2),
    )
    return RoofPrediction(roofs=roofs, obstacles=obstacles)
