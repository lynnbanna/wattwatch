import { describe, expect, it } from "vitest";
import {
  compact,
  DEFAULT_FORM,
  formFromDesign,
  niceTicks,
  requestFromForm,
  type SolarDesign,
} from "./solar";

describe("requestFromForm", () => {
  it("converts the defaults to the API's units", () => {
    const result = requestFromForm(DEFAULT_FORM);
    expect(result).toEqual({
      request: {
        location: { city: "Beirut" },
        panel: { power_w: 450, length_m: 1.722, width_m: 1.134, gap_m: 0.02 },
        mounting: { kind: "flat_tilted", tilt_deg: 25, azimuth_deg: 0, orientation: "landscape" },
        losses: {
          soiling: 0.03,
          wiring: 0.02,
          mismatch: 0.01,
          shading: 0.02,
          availability: 0.01,
          inverter_efficiency: 0.96,
        },
      },
    });
  });

  it("uses coordinates when chosen", () => {
    const result = requestFromForm({ ...DEFAULT_FORM, place: "coordinates", lat: "34,43", lon: "35.85" });
    expect(result).toMatchObject({ request: { location: { lat: 34.43, lon: 35.85 } } });
  });

  it("reports the first invalid field", () => {
    expect(requestFromForm({ ...DEFAULT_FORM, tilt: "75" })).toEqual({
      error: "Tilt must be between 0 and 60.",
    });
    expect(requestFromForm({ ...DEFAULT_FORM, place: "coordinates" })).toEqual({
      error: "Latitude must be between -60 and 65.",
    });
  });
});

describe("formFromDesign", () => {
  it("round-trips a saved design back into the form", () => {
    const { request } = requestFromForm({ ...DEFAULT_FORM, shadingPct: "5.5" }) as {
      request: Parameters<typeof formFromDesign>[0];
    };
    const design = {
      ...request,
      location: { name: "Beirut", lat: 33.89, lon: 35.5 },
    } as unknown as SolarDesign;
    expect(formFromDesign(design)).toEqual({ ...DEFAULT_FORM, shadingPct: "5.5" });
  });
});

describe("chart helpers", () => {
  it("picks clean ticks covering the maximum", () => {
    expect(niceTicks(2734)).toEqual([0, 1000, 2000, 3000]);
    expect(niceTicks(380)).toEqual([0, 100, 200, 300, 400]);
    expect(niceTicks(0)).toEqual([0, 1]);
  });

  it("formats compact numbers", () => {
    expect(compact(0)).toBe("0");
    expect(compact(950)).toBe("950");
    expect(compact(1500)).toBe("1.5K");
    expect(compact(26436)).toBe("26K");
    expect(compact(1_200_000)).toBe("1.2M");
  });
});
