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

export type Detection = {
  label: string;
  confidence: number;
  polygon_px: [number, number][];
};

export type RoofAnalysisResponse = {
  model: { name: string; version: string; is_stub: boolean };
  image: { width_px: number; height_px: number };
  roofs: Detection[];
  obstacles: Detection[];
  limitations: string[];
};

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
  signal?: AbortSignal,
): Promise<RoofAnalysisResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(apiUrl("roof-analysis"), { method: "POST", body: form, signal });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(apiErrorMessage(res.status, body));
  }
  return res.json();
}
