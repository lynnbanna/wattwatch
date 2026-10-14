# WattWatch ML

Training, evaluation and data preparation for the roof model.
Decisions: [docs/MODEL_DECISION.md](../docs/MODEL_DECISION.md) · data and licences: [docs/DATA_PLAN.md](../docs/DATA_PLAN.md).

## Setup (Windows, NVIDIA GPU)
```bash
python -m venv ml/.venv
ml/.venv/Scripts/python -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu130
ml/.venv/Scripts/python -m pip install -r ml/requirements.txt -r ml/requirements-dev.txt
```
PyTorch on Windows needs the Microsoft Visual C++ Redistributable (x64).

## Data
Download RID2 from [Zenodo](https://zenodo.org/records/14062580) into `data/raw/rid2/`
and unzip it there (see `data/SOURCES.md`).

## Split (frozen)
`data/splits/rid2_split_v1.csv` assigns every RID2 tile to `train`, `val` or `test`
**by region**: tiles within 1 km chain into one region (48 regions), and whole regions
are assigned with seed 42. The nearest test tile is 1.2 km from any training tile.

RID2's official split is not used: 520 of its 952 test tiles are directly adjacent to
training tiles, so buildings that straddle tile edges would leak into evaluation.
Metrics are therefore not directly comparable with the RID2 paper.

Never regenerate v1 (`rid2_split_v1.json` records its SHA-256); create a v2 instead.

```bash
PYTHONPATH=ml ml/.venv/Scripts/python ml/scripts/make_split.py
```

## Tests
```bash
cd ml && .venv/Scripts/python -m pytest && .venv/Scripts/python -m ruff check .
```
