import { apiErrorMessage, apiUrl, type Point } from "./api";

// Mirrors backend/app/solar/locations.py.
export const LEBANESE_CITIES = [
  "Beirut",
  "Tripoli",
  "Sidon",
  "Tyre",
  "Jounieh",
  "Byblos",
  "Zahle",
  "Baalbek",
  "Nabatieh",
] as const;

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export type MountingKind = "flat_tilted" | "flush";

export type SolarDesignRequest = {
  location: { city: string } | { lat: number; lon: number };
  panel: { power_w: number; length_m: number; width_m: number; gap_m: number };
  mounting: {
    kind: MountingKind;
    tilt_deg: number;
    azimuth_deg: number;
    orientation: "landscape" | "portrait";
  };
  losses: {
    soiling: number;
    wiring: number;
    mismatch: number;
    shading: number;
    availability: number;
    inverter_efficiency: number;
  };
};

export type SolarDesign = Omit<SolarDesignRequest, "location"> & {
  created_at: string;
  outline_hash: string;
  uses_corrections: boolean;
  location: { name: string | null; lat: number; lon: number };
  layout: {
    panel_count: number;
    kwp: number;
    panels_px: Point[][];
    usable_area_m2: number;
    panel_area_m2: number;
    row_pitch_m: number;
    row_gap_m: number;
    winter_noon_sun_elevation_deg: number | null;
  };
  production: {
    monthly_kwh: number[];
    annual_kwh: number;
    specific_yield_kwh_per_kwp: number;
    capacity_factor: number;
    performance_factor: number;
    year_to_year_sd_kwh: number;
  };
  resource: {
    loss_free_yield_kwh_per_kwp: number;
    database: string;
    years: string;
    attribution: string;
  };
  assumptions: string[];
  limitations: string[];
};

export async function createSolarDesign(
  analysisId: string,
  body: SolarDesignRequest,
  signal?: AbortSignal,
): Promise<SolarDesign> {
  const res = await fetch(apiUrl(`analyses/${encodeURIComponent(analysisId)}/solar-design`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(apiErrorMessage(res.status, data));
  }
  return res.json();
}

/** The form holds text so users can type freely; it is parsed on submit. */
export type SolarForm = {
  place: string; // a city name, or "coordinates"
  lat: string;
  lon: string;
  kind: MountingKind;
  tilt: string;
  azimuth: string;
  orientation: "landscape" | "portrait";
  powerW: string;
  lengthM: string;
  widthM: string;
  soilingPct: string;
  wiringPct: string;
  mismatchPct: string;
  shadingPct: string;
  availabilityPct: string;
  inverterPct: string;
};

export const DEFAULT_FORM: SolarForm = {
  place: "Beirut",
  lat: "",
  lon: "",
  kind: "flat_tilted",
  tilt: "25",
  azimuth: "0",
  orientation: "landscape",
  powerW: "450",
  lengthM: "1.722",
  widthM: "1.134",
  soilingPct: "3",
  wiringPct: "2",
  mismatchPct: "1",
  shadingPct: "2",
  availabilityPct: "1",
  inverterPct: "96",
};

/** Restore a form from a saved design so users can tweak and recalculate. */
export function formFromDesign(d: SolarDesign): SolarForm {
  const pct = (v: number) => String(Math.round(v * 1000) / 10);
  return {
    place: d.location.name ?? "coordinates",
    lat: d.location.name ? "" : String(d.location.lat),
    lon: d.location.name ? "" : String(d.location.lon),
    kind: d.mounting.kind,
    tilt: String(d.mounting.tilt_deg),
    azimuth: String(d.mounting.azimuth_deg),
    orientation: d.mounting.orientation,
    powerW: String(d.panel.power_w),
    lengthM: String(d.panel.length_m),
    widthM: String(d.panel.width_m),
    soilingPct: pct(d.losses.soiling),
    wiringPct: pct(d.losses.wiring),
    mismatchPct: pct(d.losses.mismatch),
    shadingPct: pct(d.losses.shading),
    availabilityPct: pct(d.losses.availability),
    inverterPct: pct(d.losses.inverter_efficiency),
  };
}

function num(text: string, min: number, max: number, what: string): number {
  const value = Number(text.trim().replace(",", "."));
  if (text.trim() === "" || !Number.isFinite(value) || value < min || value > max) {
    throw new Error(`${what} must be between ${min} and ${max}.`);
  }
  return value;
}

/** Validate the form and build the API request; returns an error message instead if invalid. */
export function requestFromForm(
  f: SolarForm,
): { request: SolarDesignRequest } | { error: string } {
  try {
    const location =
      f.place === "coordinates"
        ? { lat: num(f.lat, -60, 65, "Latitude"), lon: num(f.lon, -180, 180, "Longitude") }
        : { city: f.place };
    const lossPct = (text: string, what: string) => num(text, 0, 50, what) / 100;
    return {
      request: {
        location,
        panel: {
          power_w: num(f.powerW, 100, 800, "Panel power"),
          length_m: num(f.lengthM, 0.5, 3, "Panel length"),
          width_m: num(f.widthM, 0.3, 2, "Panel width"),
          gap_m: 0.02,
        },
        mounting: {
          kind: f.kind,
          tilt_deg: num(f.tilt, 0, 60, "Tilt"),
          azimuth_deg: num(f.azimuth, -180, 180, "Azimuth"),
          orientation: f.orientation,
        },
        losses: {
          soiling: lossPct(f.soilingPct, "Soiling loss"),
          wiring: lossPct(f.wiringPct, "Wiring loss"),
          mismatch: lossPct(f.mismatchPct, "Mismatch loss"),
          shading: lossPct(f.shadingPct, "Shading loss"),
          availability: lossPct(f.availabilityPct, "Availability loss"),
          inverter_efficiency: num(f.inverterPct, 80, 100, "Inverter efficiency") / 100,
        },
      },
    };
  } catch (err) {
    return { error: (err as Error).message };
  }
}

/** Clean axis ticks from 0 to a round maximum at or above `max` (about `count` steps). */
export function niceTicks(max: number, count = 4): number[] {
  if (!(max > 0)) return [0, 1];
  const raw = max / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw)!;
  const top = Math.ceil(max / step) * step;
  return Array.from({ length: Math.round(top / step) + 1 }, (_, i) => +(i * step).toFixed(10));
}

/** 0 / 950 / 1.5K / 12K / 1.2M */
export function compact(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e6) return `${+(value / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${+(value / 1e3).toFixed(abs >= 1e4 ? 0 : 1)}K`;
  return String(Math.round(value));
}

export function formatKwh(kwh: number): string {
  return `${Math.round(kwh).toLocaleString("en-US")} kWh`;
}
