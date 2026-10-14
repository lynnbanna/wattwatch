# WattWatch — 8-Week Implementation Plan

Tracked version of the original plan. Tick items as they land; each week's
**Definition of done** must hold before moving on. If a milestone slips, cut
optional scope before cutting validation or tests.

**Product principle:** estimates are explainable — show assumptions,
confidence, and limitations; never present uncertain predictions as facts.

**Core journey:** upload rooftop image → analyze roof → estimate usable area →
configure solar and battery → compare costs and savings → save or share a report.

---

## Week 1 — Foundation (done)
Goal: running app, repository, architecture, validated data strategy.

- [x] One-page PRD and main user journey → [PRD.md](PRD.md)
- [x] GitHub repository + issue board → [repo](https://github.com/lynnbanna/wattwatch), [project board](https://github.com/users/lynnbanna/projects/1)
- [x] README and branching conventions → [README.md](../README.md), [CONTRIBUTING.md](CONTRIBUTING.md)
- [x] Next.js + TypeScript + Tailwind CSS → `frontend/`
- [x] Python + FastAPI + PostgreSQL → `backend/`, `docker-compose.yml`
- [x] Docker Compose for local development
- [x] API conventions, env vars, logging, initial tests → [API_CONVENTIONS.md](API_CONVENTIONS.md)
- [x] Research rooftop datasets, usage rights, labels, coverage → [DATA_PLAN.md](DATA_PLAN.md)

**Done when:** local frontend and API run; database connection succeeds; data plan documented.

## Week 2 — Computer vision baseline (done)
Goal: an uploaded image is processed by a baseline model.

- [x] Collect a small, legally usable dataset of rooftop images + annotations → RID2 (CC BY 4.0); Lebanese set deferred to [#20](https://github.com/lynnbanna/wattwatch/issues/20)
- [x] Choose one segmentation model and a narrow obstacle-detection approach → [MODEL_DECISION.md](MODEL_DECISION.md)
- [x] Preprocessing and inference scripts → model `v0.1.0` served by the API (ONNX Runtime)
- [x] Separate evaluation set, never used for tuning → region-based RID2 split (`data/splits/rid2_split_v1.csv`); Lebanese set pending hand labels
- [x] Measure segmentation quality (IoU) and detection precision/recall → [METRICS.md](METRICS.md) (RID2; Lebanese set pending)
- [x] FastAPI inference endpoint (stub model until training lands)
- [x] Frontend shows uploaded image + prediction overlay

**Done when:** upload an image and view an overlay; baseline metrics recorded.

## Week 3 — Pixels to rooftop measurements
Goal: usable-area estimate with clear limitations.

- [x] Image validation, resizing, coordinate handling
- [x] Require top-down (nadir) imagery: users state image type and scale before analysis; oblique photos get a clear message, not a result
- [x] Replace "confidence" with an explained model score (not a probability of being correct) until scores are calibrated
- [x] Scale input or georeferenced-imagery workflow → entered resolution or drawn reference line (GeoTIFF later)
- [x] Roof area from calibrated pixel measurements
- [x] Subtract obstacles; configurable clearance margins
- [x] Manual correction of roof boundaries and obstacles → move, insert and remove corners; delete or draw outlines; undo; areas re-measured by the API
- [x] Store original image, model version, predictions, corrected measurements → `analyses` table + metadata-free PNG; `/analyses/{id}` page with autosave
- [x] Test against manually measured reference examples → RID2 outlines: roof area median error 6.8%, p90 45% ([METRICS.md](METRICS.md))

**Done when:** calibrated area estimate with manual correction and a documented error measure.

## Week 4 — Solar production engine
Goal: users configure panels and get an energy estimate.

- [ ] Panel model: rated power, dimensions, spacing
- [ ] Feasible panel count within usable roof geometry
- [ ] Monthly and annual generation from a solar-resource model/data source
- [ ] Orientation, tilt, shading, system losses, inverter efficiency
- [ ] Solar calculations as independent, unit-tested Python functions
- [ ] Charts: monthly production + key assumptions
- [ ] Validate against trusted reference examples

**Done when:** a user configures a system and inspects monthly and annual estimates.

## Week 5 — Household energy and financial scenarios
Goal: users compare realistic what-if scenarios.

- [ ] Household usage profile (monthly or hourly demand)
- [ ] User-entered utility, generator, other costs — no hardcoded tariff
- [ ] Battery: capacity, usable capacity, round-trip efficiency, power limits
- [ ] Self-consumption, grid/generator reliance, unmet demand on one time model
- [ ] Upfront cost, operating cost, savings, payback
- [ ] Optimistic / baseline / conservative assumptions
- [ ] Tests for edge cases, units, financial calculations

**Done when:** users compare at least two configurations with assumptions and outcomes.

## Week 6 — Dashboard and reporting
Goal: full journey works end to end.

- [ ] Authentication and ownership checks
- [ ] Property and analysis dashboard
- [ ] Forms: usage, tariffs, equipment, system assumptions
- [ ] Connect vision → solar → financial into one workflow
- [ ] Comparison charts with explanations
- [ ] Save, revisit, compare scenarios
- [ ] Downloadable report showing data limitations

**Done when:** a user can create, save, reopen, and compare a complete analysis.

## Week 7 — Integration, validation, security, deployment
Goal: stable application online.

- [ ] End-to-end tests for the main journey
- [ ] Held-out evaluation of the vision model; record metrics
- [ ] Area-estimation error where references exist
- [ ] Hand-calculated solar and financial scenarios as tests
- [ ] Upload size limits, file-type validation, safe storage, rate limits
- [ ] CI runs lint + tests on every PR *(workflow already in `.github/workflows/ci.yml`)*
- [ ] Deploy frontend, API, database, model
- [ ] Verify logs, errors, backups, secrets, production config

**Done when:** deployed app, passing critical tests, documented model performance.

## Week 8 — Polish and portfolio
Goal: a recruiter can try the app and understand the engineering decisions.

- [ ] Fix high-impact bugs; loading, empty, error states
- [ ] Demo dataset so visitors can explore without uploading
- [ ] Architecture overview, setup, API docs, model card
- [ ] Dataset sources, licenses, metrics, limitations, failure cases
- [ ] Short recorded demo: upload → financial comparison
- [ ] Screenshots, system diagram, tests, project description on GitHub
- [ ] Stable demo + concise write-up of hardest technical decisions

**Done when:** live demo, clear README, architecture diagram, metrics, recorded walkthrough.

---

## Milestones
| End of week | Milestone |
|---|---|
| 2 | AI proof of concept: upload + overlay; baseline metrics |
| 4 | Technical core: calibrated measurement feeds the solar engine |
| 6 | Complete journey: create, configure, compare, save |
| 8 | Portfolio release: deployed demo, docs, tests, honest metrics |

## Weekly rhythm
Mon plan & issues · Tue build core · Wed integrate · Thu test & validate ·
Fri finish & merge · Sat docs, refactor, demo · Sun rest / catch up.

## Out of scope (for now)
Native mobile apps · real-time satellite processing across all of Lebanon ·
bill OCR · custom foundation model · live utility integrations ·
multi-user organisation management.

## Quality guardrails
- Validate data availability and licensing before heavy training.
- Keep the vision model replaceable; always allow manual correction.
- Never convert pixels to m² without scale or georeferencing.
- Transparent assumptions for solar resource, tariffs, generator costs, batteries.
- Report metrics on held-out data; document failure cases.
- A modest, tested, deployed system beats an unvalidated advanced model.
