# API Conventions

- **Base path:** all endpoints live under `/api/v1`. Breaking changes get a new version prefix.
- **Format:** JSON in and out; `snake_case` field names.
- **Units:** SI units, with the unit in the field name when ambiguous — `area_m2`, `energy_kwh`, `power_kw`, `cost_usd`.
- **Errors:** non-2xx responses use one shape:
  ```json
  { "error": { "code": "invalid_scale", "message": "Scale must be positive" } }
  ```
- **Estimates:** any estimated value is returned with its assumptions and, where available, a confidence or range — never a bare number.
- **Request IDs:** every response carries `x-request-id` (echoed from the request if supplied); logs include it.
- **Logging:** structured JSON lines on stdout.
- **Uploads (from Week 2):** size and type validated server-side; files stored outside the web root.

## Environment variables
| Variable | Service | Default |
|---|---|---|
| `DATABASE_URL` | api | `postgresql+psycopg://wattwatch:wattwatch@localhost:5432/wattwatch` |
| `CORS_ORIGINS` | api | `["http://localhost:3000"]` |
| `LOG_LEVEL` | api | `INFO` |
| `ENVIRONMENT` | api | `development` |
| `MAX_UPLOAD_BYTES` | api | `10485760` (10 MB) |
| `MAX_IMAGE_PIXELS` | api | `12000000` (about 20 s of CPU inference at the limit) |
| `VISION_MODEL` | api | `stub` (`unet` in Docker Compose): `stub` or `unet` |
| `VISION_MODEL_PATH` | api | `../models/roof_unet_r18_gsd015_v0.1.0.onnx` |
| `NEXT_PUBLIC_API_URL` | web | `http://localhost:8000` |

## Current endpoints
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | API status, version, database reachability |
| POST | `/api/v1/roof-analysis` | Multipart: `file` (PNG/JPEG), `imagery_type` (`top_down` required), scale as `gsd_m` **or** `reference_x1/y1/x2/y2` + `reference_length_m`, optional `edge_setback_m` (default 0.5) and `obstacle_clearance_m` (default 0.3). Returns roof/obstacle polygons in original image pixels with `model_score`, areas in m², usable area, scale info, assumptions and limitations |
| POST | `/api/v1/roof-measurements` | JSON: `gsd_m`, `roofs` and `obstacles` (lists of `[x, y]` pixel polygons, 3-2,000 points, up to 500 each), optional `edge_setback_m`, `obstacle_clearance_m`. Returns per-region and total areas with assumptions, using the same geometry as `/roof-analysis` (used after manual correction). 422 `invalid_polygon` for too few or too many points |

## Model scores
`model_score` (0-1) is the model's mean pixel score over a region. It is **not** a probability that the outline is correct and is not calibrated; the API returns an explanatory `model_score_note` with every analysis.

## Upload errors
| Status | Code | When |
|---|---|---|
| 413 | `file_too_large` | File exceeds `MAX_UPLOAD_BYTES` |
| 413 | `image_too_large` | Width × height exceeds `MAX_IMAGE_PIXELS` |
| 415 | `unsupported_file_type` | Content is not a PNG or JPEG (the declared type is not trusted) |
| 400 | `invalid_image` | Image data is corrupt or truncated |
| 422 | `unsupported_imagery` | `imagery_type` is not `top_down` (oblique or ground photos) |
| 422 | `invalid_scale` | No scale, both scales, incomplete or out-of-image reference line, or scale outside 0.02-2 m/px |
| 413 | `image_too_large` | Also when the image would exceed `MAX_IMAGE_PIXELS` after resampling to the model's scale |
| 422 | `invalid_request` | Missing or malformed fields |

Interactive docs: `http://localhost:8000/docs` when the API is running.
