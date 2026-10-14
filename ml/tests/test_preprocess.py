import numpy as np
from PIL import Image

from wattwatch_ml.preprocess import (
    IGNORE_INDEX,
    pad_to_stride,
    padded_size,
    resample_image,
    resample_mask,
    resampled_size,
)


def test_resampled_size_matches_ground_footprint():
    assert resampled_size(512, 0.08, 0.3) == 137
    assert resampled_size(512, 0.08, 0.15) == 273
    assert resampled_size(512, 0.08, 0.08) == 512


def test_padded_size_rounds_up_to_stride():
    assert padded_size(137) == 160
    assert padded_size(273) == 288
    assert padded_size(160) == 160


def test_resample_mask_uses_majority_coverage():
    mask = np.zeros((4, 4), dtype=np.uint8)
    mask[:, :3] = 1  # 75% roof, 25% background
    out = resample_mask(mask, (1, 1), num_classes=3)
    assert out.tolist() == [[1]]


def test_resample_mask_keeps_classes_within_range():
    rng = np.random.default_rng(0)
    mask = rng.integers(0, 3, size=(64, 64), dtype=np.uint8)
    out = resample_mask(mask, (17, 17), num_classes=3)
    assert out.shape == (17, 17)
    assert set(np.unique(out)) <= {0, 1, 2}


def test_resample_image_returns_rgb_of_requested_size():
    img = Image.new("RGBA", (64, 64))
    out = resample_image(img, (20, 20))
    assert out.mode == "RGB" and out.size == (20, 20)


def test_pad_to_stride_marks_padding_as_ignored():
    image = np.zeros((137, 137, 3), dtype=np.uint8)
    mask = np.ones((137, 137), dtype=np.uint8)
    image_p, mask_p = pad_to_stride(image, mask)
    assert image_p.shape == (160, 160, 3)
    assert mask_p.shape == (160, 160)
    assert (mask_p[:137, :137] == 1).all()
    assert (mask_p[137:, :] == IGNORE_INDEX).all()
    assert (mask_p[:, 137:] == IGNORE_INDEX).all()
