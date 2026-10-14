export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export type HealthResponse = {
  status: "ok" | "degraded";
  version: string;
  database: "ok" | "unavailable";
};

export function apiUrl(path: string): string {
  return `${API_URL}/api/v1/${path.replace(/^\//, "")}`;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(apiUrl("health"), { signal, cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

export type Point = [number, number];

export type RoofRegion = {
  label: string;
  model_score: number;
  polygon_px: Point[];
  area_m2: number;
  usable_area_m2: number;
};

export type ObstacleRegion = {
  label: string;
  model_score: number;
  polygon_px: Point[];
  area_m2: number;
};

export type RoofAnalysisResponse = {
  model: { name: string; version: string; is_stub: boolean; gsd_m: number };
  image: { width_px: number; height_px: number };
  scale: {
    gsd_m: number;
    source: "gsd" | "reference_line";
    model_gsd_m: number;
    resample_factor: number;
  };
  roofs: RoofRegion[];
  obstacles: ObstacleRegion[];
  measurements: {
    roof_area_m2: number;
    obstacle_area_m2: number;
    usable_area_m2: number;
    edge_setback_m: number;
    obstacle_clearance_m: number;
  };
  model_score_note: string;
  assumptions: string[];
  limitations: string[];
};

export type ScaleInput =
  | { kind: "gsd"; gsdM: number }
  | { kind: "reference_line"; start: Point; end: Point; lengthM: number };

export type AnalysisOptions = {
  scale: ScaleInput;
  edgeSetbackM: number;
  obstacleClearanceM: number;
};

export const DEFAULT_EDGE_SETBACK_M = 0.5;
export const DEFAULT_OBSTACLE_CLEARANCE_M = 0.3;

/** Form fields for POST /roof-analysis (the file is added separately). */
export function analysisFields(options: AnalysisOptions): Record<string, string> {
  const fields: Record<string, string> = {
    imagery_type: "top_down",
    edge_setback_m: String(options.edgeSetbackM),
    obstacle_clearance_m: String(options.obstacleClearanceM),
  };
  const { scale } = options;
  if (scale.kind === "gsd") {
    fields.gsd_m = String(scale.gsdM);
  } else {
    fields.reference_x1 = String(scale.start[0]);
    fields.reference_y1 = String(scale.start[1]);
    fields.reference_x2 = String(scale.end[0]);
    fields.reference_y2 = String(scale.end[1]);
    fields.reference_length_m = String(scale.lengthM);
  }
  return fields;
}

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const ACCEPTED_IMAGE_TYPES = ["image/png", "image/jpeg"];

/** Client-side pre-check; the API validates again by decoding the file. */
export function validateImageFile(file: { type: string; size: number }): string | null {
  if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
    return "Please choose a PNG or JPEG image.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "Image is larger than the 10 MB upload limit.";
  }
  return null;
}

/** Message from the API's standard `{ error: { code, message } }` body, if present. */
export function apiErrorMessage(status: number, body: unknown): string {
  const message = (body as { error?: { message?: unknown } } | null)?.error?.message;
  return typeof message === "string" ? message : `Request failed with status ${status}`;
}

export async function analyzeRoof(
  file: Blob,
  options: AnalysisOptions,
  signal?: AbortSignal,
): Promise<RoofAnalysisResponse> {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(analysisFields(options))) {
    form.append(key, value);
  }
  const res = await fetch(apiUrl("roof-analysis"), { method: "POST", body: form, signal });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(apiErrorMessage(res.status, body));
  }
  return res.json();
}
