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
