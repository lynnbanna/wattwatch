import { describe, expect, it } from "vitest";
import { formatConfidence, formatLabel, polygonToPoints } from "./overlay";

describe("polygonToPoints", () => {
  it("formats pixel coordinates for an SVG polygon", () => {
    expect(
      polygonToPoints([
        [0, 0],
        [10.5, 0],
        [10.5, 20],
      ]),
    ).toBe("0,0 10.5,0 10.5,20");
  });

  it("returns an empty string for an empty polygon", () => {
    expect(polygonToPoints([])).toBe("");
  });
});

describe("formatting", () => {
  it("shows confidence as a whole percentage", () => {
    expect(formatConfidence(0.5)).toBe("50%");
    expect(formatConfidence(0.876)).toBe("88%");
  });

  it("turns snake_case labels into readable text", () => {
    expect(formatLabel("solar_water_heater")).toBe("Solar water heater");
    expect(formatLabel("roof")).toBe("Roof");
  });
});
