import type { MeasuredAreas, RoofAnalysisResponse } from "./api";
import { countEdits, type Region, type RegionSource } from "./editing";

export type RegionRow = {
  label: string;
  source: RegionSource;
  score: number | null;
  areaM2: number | null;
  usableAreaM2?: number | null;
};

export type ResultsView = {
  isStub: boolean;
  measurements: RoofAnalysisResponse["measurements"];
  roofs: RegionRow[];
  obstacles: RegionRow[];
  modelScoreNote: string;
  assumptions: string[];
  limitations: string[];
  footer: string;
  editCount: number;
  /** Outlines changed since the last measurement; totals are from before the change. */
  stale: boolean;
};

/**
 * Combine the analysis with the current (possibly corrected) outlines.
 * `measured` is the latest re-measurement and the outlines it was computed for.
 */
export function buildResultsView(
  result: RoofAnalysisResponse,
  regions: Region[],
  original: Region[],
  measured: { regions: Region[]; response: MeasuredAreas } | null,
): ResultsView {
  const base = {
    isStub: result.model.is_stub,
    modelScoreNote: result.model_score_note,
    assumptions: result.assumptions,
    limitations: result.limitations,
    footer:
      `Model ${result.model.name} v${result.model.version} · image ` +
      `${result.image.width_px}×${result.image.height_px} px · ` +
      `${(result.scale.gsd_m * 100).toPrecision(3)} cm per pixel`,
  };

  if (regions === original) {
    return {
      ...base,
      measurements: result.measurements,
      roofs: result.roofs.map((r) => ({
        label: r.label,
        source: "model",
        score: r.model_score,
        areaM2: r.area_m2,
        usableAreaM2: r.usable_area_m2,
      })),
      obstacles: result.obstacles.map((o) => ({
        label: o.label,
        source: "model",
        score: o.model_score,
        areaM2: o.area_m2,
      })),
      editCount: 0,
      stale: false,
    };
  }

  const current = measured?.regions === regions ? measured.response : null;
  const rows = (kind: Region["kind"]) =>
    regions
      .filter((r) => r.kind === kind)
      .map((r, i): RegionRow => {
        const areas = kind === "roof" ? current?.roofs[i] : current?.obstacles[i];
        return {
          label: r.label,
          source: r.source,
          score: r.modelScore,
          areaM2: areas?.area_m2 ?? null,
          ...(kind === "roof" && {
            usableAreaM2: (areas as { usable_area_m2?: number } | undefined)?.usable_area_m2 ?? null,
          }),
        };
      });

  return {
    ...base,
    measurements: (current ?? measured?.response)?.measurements ?? result.measurements,
    roofs: rows("roof"),
    obstacles: rows("obstacle"),
    editCount: countEdits(regions, original),
    stale: current === null,
  };
}
