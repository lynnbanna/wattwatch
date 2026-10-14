# Model Decision: Baseline Roof and Obstacle Model

Status: **approved 2026-10-12** (issue #5). Revisit after baseline metrics (#7).

## Decision
One **multi-class semantic segmentation** model handles both roofs and
obstacles: a **U-Net with a ResNet-18 encoder** pretrained on ImageNet, from
[`segmentation_models_pytorch`](https://github.com/qubvel-org/segmentation_models.pytorch).

- Each pixel is classified as `background`, `roof`, or an obstacle class.
- Obstacles become instances by taking connected components of obstacle pixels.
  Each component becomes a polygon, and its confidence is the mean class
  probability over the component.
- The model sits behind the API's `RoofModel` interface
  (`backend/app/vision/models.py`), so it can be replaced without touching the
  API or the frontend.

## Why
| Consideration | Choice |
|---|---|
| Hardware: GeForce MX550, 2 GB VRAM | ~14 M parameters; trains on small tiles with mixed precision. Free Google Colab is the fallback. |
| One model vs. segmenter + detector | One model is simpler to train, serve and evaluate on a small GPU |
| Week 3 manual correction | Masks convert directly to editable polygons |
| Licensing | Library MIT; encoder weights from torchvision (code BSD-3; see risks) |

### Alternatives rejected
| Option | Reason |
|---|---|
| SegFormer (NVIDIA weights) | Weights are licensed for non-commercial use only |
| YOLO (Ultralytics) | AGPL-3.0: serving it in a web app would oblige publishing the whole app under AGPL |
| Segment Anything (SAM) | Apache-2.0, but too large for 2 GB VRAM and needs prompts |
| Training from scratch | Too little data; pretrained encoders converge far faster |

## Classes
| Phase | Classes | Data |
|---|---|---|
| Baseline (Week 2) | `background`, `roof`, `obstacle` | RID2: all roof segments merged into `roof`; all 12 superstructure classes merged into `obstacle` |
| Regional fine-tune | `background`, `roof`, `water_tank`, `solar_water_heater`, `other_obstacle` | Hand-labelled Lebanese tiles (see [DATA_PLAN.md](DATA_PLAN.md)) |

RID2 has no water tanks or solar water heaters, so the regional classes need
hand labels.

## Ground sampling distance (GSD)
All imagery is resampled to one fixed GSD, so a pixel always means the same
ground size. This matters for area estimation in Week 3.

- **Default 0.3 m/px.** This matches commercial satellite imagery. RID2 tiles
  (512 px at 0.08 m ≈ 41 m) become about 136 px.
- **Known risk:** at 0.3 m, a 1.2 m water tank is about 4 px across and a solar
  water heater about 7 × 3 px, so obstacle recall may be poor.
- **Plan:** make GSD a preprocessing parameter and evaluate the baseline at both
  **0.3 m and 0.15 m**. Choose 0.15 m only if obstacle recall improves
  materially without hurting roof IoU. Record the result in the metrics doc.
- **Result (2026-10-14): 0.15 m selected.** Obstacle recall at IoU ≥ 0.5 rose from
  0.36 to 0.55 and roof IoU from 0.69 to 0.75 on the test split. See
  [METRICS.md](METRICS.md). Consequence: inputs need about 0.15 m imagery (drone or
  high-end aerial); satellite imagery at 0.3–0.5 m will give weaker obstacle results.

## Evaluation (#7)
- **Roof:** pixel IoU on the frozen held-out test split.
- **Obstacles:** pixel IoU, plus instance precision and recall. A predicted
  component matches a ground-truth component at IoU ≥ 0.5.
- **Reporting:** metrics on RID2's test split are reported separately from
  metrics on the Lebanese regional set, and never averaged together.
- **Every reported metric carries:** model version, dataset version, GSD, and
  split manifest hash.

## Input assumptions and limitations
- The model expects **top-down (nadir) aerial or satellite imagery**. Oblique
  or ground-level photos are out of distribution: predictions are unreliable,
  and area cannot be measured from them because of perspective. The upload
  flow must say so (Week 3).
- Training data is Dutch (mostly pitched roofs). A domain gap on Lebanese flat
  roofs is expected until regional fine-tuning.

## Risks
- **ImageNet-pretrained weights:** torchvision's code is BSD-3, but the
  ImageNet dataset's terms are research-oriented, and the status of weights
  trained on it is legally unsettled. This is widely accepted practice; revisit
  before any commercial release.
- **Training speed:** the MX550 may be too slow for many experiments (0.15 m takes
  80 min per run). Mixed precision is unusable on it: cuDNN 9.24 returns NaN from
  float16 BatchNorm, so training runs in float32. Use Colab if experiments multiply.
