# WattWatch

An energy intelligence platform combining rooftop computer vision, solar
estimation, and household energy financial modeling.

**Core journey:** upload rooftop image → analyze roof → estimate usable area →
configure solar and battery → compare costs and savings → save or share a report.

Estimates are explainable by design: every number is shown with its
assumptions, confidence, and limitations.

> Status: **Week 1 — foundation.** See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).

## Repository layout
```
frontend/   Next.js + TypeScript + Tailwind CSS (web app)
backend/    FastAPI (API, orchestration; vision and domain engines added from Week 2)
data/       Local datasets (git-ignored; see docs/DATA_PLAN.md)
models/     Model weights (git-ignored)
docs/       Plan, PRD, data plan, API conventions
```

## Quick start (Docker)
Requires Docker Desktop.
```bash
docker compose up --build
```
- Web: http://localhost:3000 — the status panel should show API `ok` and Database `ok`
- API docs: http://localhost:8000/docs

On Windows, if the build fails with `additional privileges requested`, run it with the
classic builder: `$env:COMPOSE_BAKE="false"; docker compose up --build` (PowerShell).

## Running without Docker
**Backend** (Python 3.11+; PostgreSQL running locally or via `docker compose up db`):
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt
copy .env.example .env          # `cp` on macOS/Linux
uvicorn app.main:app --reload
pytest
```

**Frontend** (Node 20+ required):
```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
npm test
```

## Docs
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Product requirements](docs/PRD.md)
- [Data plan](docs/DATA_PLAN.md)
- [Model decision](docs/MODEL_DECISION.md)
- [Model metrics](docs/METRICS.md)
- [API conventions](docs/API_CONVENTIONS.md)
- [Contributing & branching](docs/CONTRIBUTING.md)
