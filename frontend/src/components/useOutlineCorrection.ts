"use client";

import { useEffect, useMemo, useReducer, useState } from "react";
import { saveCorrections, type AnalysisRecord, type MeasuredAreas } from "@/lib/api";
import {
  correctionsFromRegions,
  editorReducer,
  initialEditorState,
  regionsFromAnalysis,
  regionsFromCorrections,
  type Region,
} from "@/lib/editing";
import { buildResultsView } from "@/lib/resultsView";

const SAVE_DELAY_MS = 400;

export type SaveStatus = "saved" | "saving" | "error";

/** Editable outlines for a saved analysis; each change is saved and re-measured by the API. */
export function useOutlineCorrection(record: AnalysisRecord) {
  const { result } = record;
  const original = useMemo(() => regionsFromAnalysis(result), [result]);
  const initial = useMemo(
    () => (record.corrections ? regionsFromCorrections(record.corrections) : original),
    [record.corrections, original],
  );
  const [state, dispatch] = useReducer(editorReducer, initial, initialEditorState);
  const [measured, setMeasured] = useState<{ regions: Region[]; response: MeasuredAreas } | null>(
    record.corrected ? { regions: initial, response: record.corrected } : null,
  );
  const [error, setError] = useState<{ regions: Region[]; message: string } | null>(null);
  const [saved, setSaved] = useState<Region[]>(initial);

  const { regions } = state;
  useEffect(() => {
    if (regions === saved) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      saveCorrections(record.id, correctionsFromRegions(regions), controller.signal)
        .then((updated) => {
          setSaved(regions);
          if (updated.corrected) setMeasured({ regions, response: updated.corrected });
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setError({
            regions,
            message: err instanceof Error ? err.message : "Could not save your changes",
          });
        });
    }, SAVE_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [record.id, regions, saved]);

  const view = buildResultsView(result, regions, original, measured);
  const saveError = error?.regions === regions ? error.message : null;
  const status: SaveStatus = saveError
    ? "error"
    : regions === saved
      ? "saved"
      : "saving";

  return {
    state,
    dispatch,
    view,
    saveError,
    status,
    canUndo: state.history.length > 0,
  };
}
