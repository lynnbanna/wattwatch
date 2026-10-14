import { describe, expect, it } from "vitest";
import type { RoofAnalysisResponse, RoofMeasurementsResponse } from "./api";
import { editorReducer, initialEditorState, regionsFromAnalysis } from "./editing";
import { buildResultsView } from "./resultsView";

const sq = (x: number): [number, number][] => [
  [x, 0],
  [x + 10, 0],
  [x + 10, 10],
  [x, 10],
];

const result: RoofAnalysisResponse = {
  model: { name: "roof-unet-r18", version: "0.1.0", is_stub: false, gsd_m: 0.15 },
  image: { width_px: 100, height_px: 100 },
  scale: { gsd_m: 0.1, source: "gsd", model_gsd_m: 0.15, resample_factor: 0.6667 },
  roofs: [{ label: "roof", model_score: 0.9, polygon_px: sq(0), area_m2: 1, usable_area_m2: 0.5 }],
  obstacles: [{ label: "obstacle", model_score: 0.6, polygon_px: sq(50), area_m2: 1 }],
  measurements: {
    roof_area_m2: 1,
    obstacle_area_m2: 0,
    usable_area_m2: 0.5,
    edge_setback_m: 0.5,
    obstacle_clearance_m: 0.3,
  },
  model_score_note: "note",
  assumptions: ["a"],
  limitations: ["l"],
};

const remeasured = (roof: number, usable: number): RoofMeasurementsResponse => ({
  roofs: [{ area_m2: roof, usable_area_m2: usable }],
  obstacles: [],
  measurements: { ...result.measurements, roof_area_m2: roof, usable_area_m2: usable },
  assumptions: [],
});

describe("buildResultsView", () => {
  const original = regionsFromAnalysis(result);

  it("shows the analysis unchanged before any edit", () => {
    const view = buildResultsView(result, original, original, null);
    expect(view.editCount).toBe(0);
    expect(view.stale).toBe(false);
    expect(view.roofs[0]).toMatchObject({ source: "model", score: 0.9, areaM2: 1 });
    expect(view.footer).toContain("10.0 cm per pixel");
  });

  it("marks totals stale until the edited outlines are re-measured", () => {
    const edited = editorReducer(initialEditorState(original), {
      type: "deleteRegion",
      id: "obstacle-0",
    }).regions;
    const pending = buildResultsView(result, edited, original, null);
    expect(pending.stale).toBe(true);
    expect(pending.editCount).toBe(1);
    expect(pending.obstacles).toEqual([]);
    expect(pending.roofs[0].areaM2).toBeNull();

    const done = buildResultsView(result, edited, original, {
      regions: edited,
      response: remeasured(2, 1.5),
    });
    expect(done.stale).toBe(false);
    expect(done.measurements.usable_area_m2).toBe(1.5);
    expect(done.roofs[0]).toMatchObject({ areaM2: 2, usableAreaM2: 1.5, source: "model" });
  });

  it("keeps the last totals visible while a newer edit is being measured", () => {
    const first = editorReducer(initialEditorState(original), {
      type: "moveVertex",
      id: "roof-0",
      index: 0,
      point: [-1, 0],
    }).regions;
    const second = [...first];
    const view = buildResultsView(result, second, original, {
      regions: first,
      response: remeasured(3, 2),
    });
    expect(view.stale).toBe(true);
    expect(view.measurements.roof_area_m2).toBe(3);
    expect(view.roofs[0]).toMatchObject({ source: "edited", areaM2: null });
  });
});
