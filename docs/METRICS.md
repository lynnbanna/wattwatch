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
  are not represented; no regional metrics exist yet.
- **`obstacle` merges 12 RID2 superstructure types** (windows, chimneys, PV modules, etc.),
  so these metrics say nothing yet about water tanks specifically.
- **Imagery resolution:** 0.15 m needs drone or high-end aerial imagery. Satellite imagery
  (0.3–0.5 m) upsampled to 0.15 m does not add detail; expect results closer to, or below,
  the 0.3 m column on such inputs.
- Test regions are more rural than training (fewer roof and obstacle pixels).

### Failure cases
Not yet reviewed visually; to be documented with examples before the model is served.
