"""RID2 dataset helpers: tile coordinates, spatial regions, and label mapping.

RID2 tiles are 512 x 512 px at 0.08 m/px (40.96 m), named "<x>_<y>.png" with
x/y in EPSG:28992 metres. Masks (5-class "simple" variant):
- masks_segments: 0-3 pitched roof faces (N/E/S/W), 4 flat roof, 5 background
- masks_superstructures: 0-4 superstructure groups, 5 background
"""

from collections.abc import Iterable, Sequence

import numpy as np

TILE_SIZE_PX = 512
TILE_GSD_M = 0.08
BACKGROUND_VALUE = 5

# Baseline classes (docs/MODEL_DECISION.md)
CLASS_BACKGROUND, CLASS_ROOF, CLASS_OBSTACLE = 0, 1, 2
CLASS_NAMES = ("background", "roof", "obstacle")


def tile_xy(name: str) -> tuple[float, float]:
    """Map coordinates (metres) encoded in a tile file name like '98594.98_437972.39.png'."""
    stem = name.rsplit(".", 1)[0]
    x, y = stem.split("_")
    return float(x), float(y)


def group_regions(names: Sequence[str], link_distance_m: float = 1000.0) -> list[int]:
    """Assign each tile a region id; tiles within `link_distance_m` (per axis) chain together.

    Splitting by region keeps buildings that straddle tile edges, and their
    neighbours, on one side of the split.
    """
    xy = np.array([tile_xy(n) for n in names])
    labels = np.full(len(names), -1, dtype=int)
    region = 0
    for start in range(len(names)):
        if labels[start] >= 0:
            continue
        labels[start] = region
        stack = [start]
        while stack:
            j = stack.pop()
            near = np.where(
                (labels < 0)
                & (np.abs(xy[:, 0] - xy[j, 0]) < link_distance_m)
                & (np.abs(xy[:, 1] - xy[j, 1]) < link_distance_m)
            )[0]
            labels[near] = region
            stack.extend(near.tolist())
        region += 1
    return labels.tolist()


def split_regions(
    region_sizes: dict[int, int],
    fractions: dict[str, float],
    seed: int,
) -> dict[int, str]:
    """Assign whole regions to splits, aiming for each split's share of tiles.

    Regions are shuffled with a fixed seed, then each goes to the split that is
    furthest below its target share.
    """
    rng = np.random.default_rng(seed)
    regions = list(region_sizes)
    rng.shuffle(regions)
    total = sum(region_sizes.values())
    counts = dict.fromkeys(fractions, 0)
    assignment: dict[int, str] = {}
    for region in regions:
        split = max(fractions, key=lambda s: fractions[s] * total - counts[s])
        assignment[region] = split
        counts[split] += region_sizes[region]
    return assignment


def baseline_mask(segments: np.ndarray, superstructures: np.ndarray) -> np.ndarray:
    """Combine RID2 masks into background / roof / obstacle class indices."""
    out = np.full(segments.shape, CLASS_BACKGROUND, dtype=np.uint8)
    out[segments != BACKGROUND_VALUE] = CLASS_ROOF
    out[superstructures != BACKGROUND_VALUE] = CLASS_OBSTACLE
    return out


def tiles_in(names: Iterable[str], split_of: dict[str, str], split: str) -> list[str]:
    return sorted(n for n in names if split_of[n] == split)
