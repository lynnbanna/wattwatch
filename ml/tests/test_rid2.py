import numpy as np

from wattwatch_ml.rid2 import (
    CLASS_BACKGROUND,
    CLASS_OBSTACLE,
    CLASS_ROOF,
    baseline_mask,
    group_regions,
    split_regions,
    tile_xy,
)


def test_tile_xy_parses_coordinates_from_name():
    assert tile_xy("98594.98_437972.39.png") == (98594.98, 437972.39)


def test_adjacent_tiles_share_a_region_and_distant_tiles_do_not():
    names = ["0_0.png", "40.96_0.png", "81.92_0.png", "50000_50000.png"]
    regions = group_regions(names)
    assert regions[0] == regions[1] == regions[2]
    assert regions[3] != regions[0]


def test_regions_chain_through_intermediate_tiles():
    names = ["0_0.png", "900_0.png", "1800_0.png"]
    regions = group_regions(names)
    assert len(set(regions)) == 1


def test_split_assigns_whole_regions_deterministically():
    sizes = {r: 10 for r in range(20)}
    fractions = {"train": 0.7, "val": 0.15, "test": 0.15}
    a = split_regions(sizes, fractions, seed=42)
    b = split_regions(sizes, fractions, seed=42)
    assert a == b
    counts = {s: sum(sizes[r] for r, v in a.items() if v == s) for s in fractions}
    assert counts == {"train": 140, "val": 30, "test": 30}


def test_baseline_mask_merges_classes_and_obstacles_win():
    seg = np.array([[5, 0], [4, 2]], dtype=np.uint8)
    sup = np.array([[5, 5], [1, 5]], dtype=np.uint8)
    expected = np.array([[CLASS_BACKGROUND, CLASS_ROOF], [CLASS_OBSTACLE, CLASS_ROOF]])
    np.testing.assert_array_equal(baseline_mask(seg, sup), expected)
