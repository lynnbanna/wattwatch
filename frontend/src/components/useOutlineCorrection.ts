"use client";

import { useEffect, useMemo, useReducer, useState } from "react";
import { measureRoofs, type RoofAnalysisResponse, type RoofMeasurementsResponse } from "@/lib/api";
import {
  editorReducer,
  initialEditorState,
  regionsFromAnalysis,
  type Region,
} from "@/lib/editing";
import { buildResultsView } from "@/lib/resultsView";

const REMEASURE_DELAY_MS = 300;

/** Editable outlines for an analysis, re-measured by the API after each change. */
export function useOutlineCorrection(result: RoofAnalysisResponse | null) {
  const original = useMemo(() => (result ? regionsFromAnalysis(result) : []), [result]);
  const [state, dispatch] = useReducer(editorReducer, original, initialEditorState);
  const [measured, setMeasured] = useState<{
    regions: Region[];
    response: RoofMeasurementsResponse;
  } | null>(null);
  const [error, setError] = useState<{ regions: Region[]; message: string } | null>(null);

  useEffect(() => {
    dispatch({ type: "load", regions: original });
  }, [original]);

  const { regions } = state;
  useEffect(() => {
    if (!result || regions === original) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const polygons = (kind: Region["kind"]) =>
        regions.filter((r) => r.kind === kind).map((r) => r.polygon);
      measureRoofs(
        {
          gsd_m: result.scale.gsd_m,
          roofs: polygons("roof"),
          obstacles: polygons("obstacle"),
          edge_setback_m: result.measurements.edge_setback_m,
          obstacle_clearance_m: result.measurements.obstacle_clearance_m,
        },
        controller.signal,
      )
        .then((response) => setMeasured({ regions, response }))
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setError({
            regions,
            message: err instanceof Error ? err.message : "Could not recalculate areas",
          });
        });
    }, REMEASURE_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [result, original, regions]);

  const view = result ? buildResultsView(result, regions, original, measured) : null;
  return {
    state,
    dispatch,
    view,
    measureError: error?.regions === regions ? error.message : null,
    canUndo: state.history.length > 0,
  };
}
