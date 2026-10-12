# Contributing

## Branching
- `main` is always deployable; no direct commits once CI is live.
- Branch per issue: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`, `chore/<short-name>`.
- Open a PR into `main`; CI (lint, typecheck, tests, build) must pass before merging.
- Squash-merge with a message that says what changed and why.

## Commits
Imperative mood, short subject: `Add roof area calculation from scale input`.

## Before opening a PR
```bash
# backend
cd backend && ruff check . && ruff format --check . && pytest
# frontend
cd frontend && npm run lint && npm run typecheck && npm test
```

## Issues
One issue per deliverable from the weekly plan ([docs/IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)),
labelled by week (`week-1` … `week-8`) and module (`vision`, `solar`, `finance`, `dashboard`, `infra`).
