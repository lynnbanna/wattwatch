import { describe, expect, it } from "vitest";
import { analysisFields } from "./api";
import { formatArea, toImagePixels } from "./overlay";
import { nextReferenceLine, parseMargin, scaleFromForm, type ScaleForm } from "./scale";

const base: ScaleForm = { mode: "gsd", gsdCm: "", start: null, end: null, lengthM: "" };

describe("scaleFromForm", () => {
  it("converts centimetres per pixel to metres", () => {
    expect(scaleFromForm({ ...base, gsdCm: "15" })).toEqual({
      scale: { kind: "gsd", gsdM: 0.15 },
      gsdM: 0.15,
    });
  });

  it("accepts a decimal comma", () => {
    expect(scaleFromForm({ ...base, gsdCm: "7,5" })).toMatchObject({ gsdM: 0.075 });
  });

  it("rejects missing, zero and out-of-range resolutions", () => {
    expect(scaleFromForm(base)).toHaveProperty("error");
    expect(scaleFromForm({ ...base, gsdCm: "0" })).toHaveProperty("error");
    expect(scaleFromForm({ ...base, gsdCm: "500" })).toHaveProperty("error");
  });

  it("derives scale from a reference line", () => {
    const form: ScaleForm = {
      ...base,
      mode: "reference_line",
      start: [0, 0],
      end: [300, 400],
      lengthM: "50",
    };
    const result = scaleFromForm(form);
    expect(result).toMatchObject({ gsdM: 0.1, scale: { kind: "reference_line", lengthM: 50 } });
  });

  it("asks for both points and a length", () => {
    const line: ScaleForm = { ...base, mode: "reference_line", start: [0, 0] };
    expect(scaleFromForm(line)).toEqual({
      error: "Click two points on the image to draw the reference line.",
    });
    expect(scaleFromForm({ ...line, end: [100, 0] })).toHaveProperty("error");
    expect(scaleFromForm({ ...line, end: [3, 0], lengthM: "1" })).toHaveProperty("error");
  });
});

describe("nextReferenceLine", () => {
  it("sets the start, then the end, then starts over", () => {
    const first = nextReferenceLine(null, null, [1, 1]);
    expect(first).toEqual({ start: [1, 1], end: null });
    const second = nextReferenceLine(first.start, first.end, [9, 9]);
    expect(second).toEqual({ start: [1, 1], end: [9, 9] });
    expect(nextReferenceLine(second.start, second.end, [5, 5])).toEqual({
      start: [5, 5],
      end: null,
    });
  });
});

describe("parseMargin", () => {
  it("accepts zero and values within the limit", () => {
    expect(parseMargin("0", 5)).toBe(0);
    expect(parseMargin("0.5", 5)).toBe(0.5);
    expect(parseMargin("6", 5)).toBeNull();
    expect(parseMargin("", 5)).toBeNull();
  });
});

describe("analysisFields", () => {
  it("sends gsd scale and margins", () => {
    expect(
      analysisFields({
        scale: { kind: "gsd", gsdM: 0.15 },
        edgeSetbackM: 0.5,
        obstacleClearanceM: 0.3,
      }),
    ).toEqual({
      imagery_type: "top_down",
      gsd_m: "0.15",
      edge_setback_m: "0.5",
      obstacle_clearance_m: "0.3",
    });
  });

  it("sends a reference line instead of gsd", () => {
    const fields = analysisFields({
      scale: { kind: "reference_line", start: [1, 2], end: [3, 4], lengthM: 10 },
      edgeSetbackM: 0,
      obstacleClearanceM: 0,
    });
    expect(fields).toMatchObject({
      reference_x1: "1",
      reference_y1: "2",
      reference_x2: "3",
      reference_y2: "4",
      reference_length_m: "10",
    });
    expect(fields).not.toHaveProperty("gsd_m");
  });
});

describe("toImagePixels", () => {
  it("maps displayed coordinates to natural image pixels and clamps", () => {
    const box = { left: 100, top: 50, width: 400, height: 200 };
    expect(toImagePixels(300, 150, box, 800, 400)).toEqual([400, 200]);
    expect(toImagePixels(0, 0, box, 800, 400)).toEqual([0, 0]);
  });
});

describe("formatArea", () => {
  it("uses one decimal below 10 m² and whole numbers above", () => {
    expect(formatArea(1.44)).toBe("1.4 m²");
    expect(formatArea(1234.6)).toBe("1,235 m²");
  });
});
