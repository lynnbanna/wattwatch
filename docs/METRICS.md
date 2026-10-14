# Model Metrics

All numbers are on held-out data that was never used for training or model
selection. Method: [MODEL_DECISION.md](MODEL_DECISION.md) (Evaluation).

## Baseline v0 — RID2, 2026-10-14

| | GSD 0.3 m | **GSD 0.15 m (selected)** |
|---|---|---|
| Roof IoU | 0.686 | **0.751** |
| Obstacle pixel IoU | 0.396 | **0.497** |
| Obstacle instances, IoU ≥ 0.5: precision / recall | 0.386 / 0.362 | **0.521 / 0.545** |
| Obstacle instances, IoU ≥ 0.25: precision / recall | 0.523 / 0.491 | **0.614 / 0.643** |
| Validation mIoU (roof, obstacle) at best epoch | 0.577 (epoch 28) | 0.668 (epoch 28) |
| Training time (GeForce MX550) | 27 min | 80 min |

### Setup
- **Model:** U-Net, ResNet-18 encoder (ImageNet weights), classes `background`/`roof`/`obstacle`.
- **Data:** RID2 v1.0, region split `rid2_split_v1.csv` (SHA-256 `18e143ed…`); test = 724
  tiles from 8 regions, at least 1.2 km from any training tile.
- **Training:** 30 epochs, AdamW, one-cycle LR (max 1e-3), weighted cross-entropy + Dice,
  flips and 90° rotations, float32, seed 0. Batch 16 at 0.3 m; batch 8 at 0.15 m (GPU memory).
- **Scoring:** predictions are upsampled to RID2's native 0.08 m grid and compared with the
  native labels, so both GSDs face the same ground truth. Obstacle components smaller than
  0.25 m² are ignored on both sides. Instances are matched one-to-one by IoU.
- **Reproduce:** `ml/scripts/preprocess_rid2.py`, `train.py`, `evaluate.py` (see [ml/README.md](../ml/README.md)).

### Decision
**Use 0.15 m.** Obstacle recall at IoU ≥ 0.5 rises from 0.36 to 0.55 and roof IoU
also improves, meeting the switch criterion in MODEL_DECISION.md.

### Limitations
- **Not comparable with the RID2 paper:** our split is region-based and stricter.
- **One run per setting** (single seed): differences of a few points could be noise; the
  gaps above are large enough that the conclusion is unlikely to change.
- **Batch size differs** between the two runs (16 vs 8) because of GPU memory.
- **Dutch, mostly pitched roofs.** Lebanese flat roofs, water tanks and solar water heaters
  are not represented; no regional metrics exist yet ([#20](https://github.com/lynnbanna/wattwatch/issues/20)).
- **`obstacle` merges 12 RID2 superstructure types** (windows, chimneys, PV modules, etc.),
  so these metrics say nothing yet about water tanks specifically.
- **Imagery resolution:** 0.15 m needs drone or high-end aerial imagery. Satellite imagery
  (0.3–0.5 m) upsampled to 0.15 m does not add detail; expect results closer to, or below,
  the 0.3 m column on such inputs.
- Test regions are more rural than training (fewer roof and obstacle pixels).

### Failure cases (0.15 m model, visual review of test tiles)
- **Neighbouring roofs merge** into one region when they touch or are separated by only a
  narrow gap, so per-building outlines are not reliable yet.
- **Grey paving, flat garage roofs and courtyards** are sometimes predicted as roof.
- **Small obstacles** (skylights, vents) are often missed or appear as fragments, consistent
  with the 0.55 recall above.

- **Out-of-distribution inputs score high.** On an oblique ground-level photo of a Lebanese
  rooftop, the model missed the roof itself and labelled solar collectors and a facade as roof
  with scores up to 0.97. Scores are not calibrated probabilities and must not be presented
  as confidence in correctness.

### Area-estimation error (2026-10-14)
Measured with the **served pipeline** (ONNX model, resampling to 0.15 m, polygonisation and
area code from `backend/app/measure`) on all 724 test tiles, against RID2's hand-drawn roof and
superstructure outlines (EPSG:28992 metres; they agree with the training masks to about 1.5%).
Script: `ml/scripts/area_error.py`. The correct scale is given, as in an ideal upload.

**Per tile** (40.96 m × 40.96 m; tiles with at least 25 m² of reference roof):

| | Roof area (620 tiles) | Usable area (567 tiles) |
|---|---|---|
| Median absolute error | **6.8%** (38 m² mean absolute) | **9.6%** (37 m² mean absolute) |
| 90th percentile absolute error | 45.2% | 55.5% |
| Mean signed error (bias) | +1.3% | +4.5% |
| Error of the total over all tiles | −3.0% | −0.9% |

Usable area uses the default 0.5 m edge setback and 0.3 m obstacle clearance on both sides.

**Per building** (927 reference buildings lying fully inside a tile):
- Detected (at least 50% covered by predicted roof): **73.4%**
- Matched one-to-one at IoU ≥ 0.5: **50.8%**; their area error is 8.4% median, 35.2% at the
  90th percentile, +3.3% bias
- Part of a prediction that merges two or more buildings: **21.9%**

**Reading this:** a typical estimate is within about 7-10% with little bias, but the tail is
long: about one estimate in ten is off by 45% or more, mostly on small roofs, merged buildings
and paving mistaken for roof. Per-building outlines are unreliable without correction. These
are best-case numbers (sharp 8 cm aerial imagery downsampled to 0.15 m, exact scale, Dutch
roofs); expect larger errors on satellite imagery, imprecise scale input, or Lebanese roofs.

### Serving
Released as [`model-v0.1.0`](https://github.com/lynnbanna/wattwatch/releases/tag/model-v0.1.0)
(ONNX, SHA-256 `f3eb427e…`). The API runs it with ONNX Runtime on CPU in 1,024 px windows with
64 px overlap: about 0.1 s for a 273 px tile and 11 s for a 3,000 × 2,000 px image.
