import type { Point, RoofAnalysisResponse } from "./api";

export type RegionKind = "roof" | "obstacle";
/** Where an outline came from: the model, the model then changed by the user, or drawn by the user. */
export type RegionSource = "model" | "edited" | "added";

export type Region = {
  id: string;
  kind: RegionKind;
  label: string;
  polygon: Point[];
  source: RegionSource;
  modelScore: number | null;
};

export type Draft = { kind: RegionKind; points: Point[] };

export type EditorState = {
  regions: Region[];
  history: Region[][];
  selectedId: string | null;
  draft: Draft | null;
  nextId: number;
};

export type EditorAction =
  | { type: "load"; regions: Region[] }
  | { type: "select"; id: string | null }
  | { type: "checkpoint" }
  | { type: "moveVertex"; id: string; index: number; point: Point }
  | { type: "insertVertex"; id: string; afterIndex: number; point: Point }
  | { type: "removeVertex"; id: string; index: number }
  | { type: "deleteRegion"; id: string }
  | { type: "startDraft"; kind: RegionKind }
  | { type: "addDraftPoint"; point: Point }
  | { type: "finishDraft" }
  | { type: "cancelDraft" }
  | { type: "undo" };

export const MIN_POINTS = 3;
const MAX_HISTORY = 100;

export function regionsFromAnalysis(result: RoofAnalysisResponse): Region[] {
  return [
    ...result.roofs.map((r, i) => ({
      id: `roof-${i}`,
      kind: "roof" as const,
      label: r.label,
      polygon: r.polygon_px,
      source: "model" as const,
      modelScore: r.model_score,
    })),
    ...result.obstacles.map((o, i) => ({
      id: `obstacle-${i}`,
      kind: "obstacle" as const,
      label: o.label,
      polygon: o.polygon_px,
      source: "model" as const,
      modelScore: o.model_score,
    })),
  ];
}

export function initialEditorState(regions: Region[]): EditorState {
  return { regions, history: [], selectedId: null, draft: null, nextId: 1 };
}

function withHistory(state: EditorState): EditorState {
  return { ...state, history: [...state.history, state.regions].slice(-MAX_HISTORY) };
}

function updatePolygon(
  regions: Region[],
  id: string,
  update: (polygon: Point[]) => Point[] | null,
): Region[] {
  return regions.map((r) => {
    if (r.id !== id) return r;
    const polygon = update(r.polygon);
    if (!polygon) return r;
    return { ...r, polygon, source: r.source === "model" ? "edited" : r.source };
  });
}

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "load":
      return initialEditorState(action.regions);
    case "select":
      return { ...state, selectedId: action.id };
    case "checkpoint":
      // Called once at the start of a drag, so the whole drag undoes in one step.
      return withHistory(state);
    case "moveVertex":
      return {
        ...state,
        regions: updatePolygon(state.regions, action.id, (p) =>
          p.map((pt, i) => (i === action.index ? action.point : pt)),
        ),
      };
    case "insertVertex": {
      const next = withHistory(state);
      return {
        ...next,
        regions: updatePolygon(next.regions, action.id, (p) => [
          ...p.slice(0, action.afterIndex + 1),
          action.point,
          ...p.slice(action.afterIndex + 1),
        ]),
      };
    }
    case "removeVertex": {
      const region = state.regions.find((r) => r.id === action.id);
      if (!region || region.polygon.length <= MIN_POINTS) return state;
      const next = withHistory(state);
      return {
        ...next,
        regions: updatePolygon(next.regions, action.id, (p) =>
          p.filter((_, i) => i !== action.index),
        ),
      };
    }
    case "deleteRegion": {
      const next = withHistory(state);
      return {
        ...next,
        regions: next.regions.filter((r) => r.id !== action.id),
        selectedId: state.selectedId === action.id ? null : state.selectedId,
      };
    }
    case "startDraft":
      return { ...state, draft: { kind: action.kind, points: [] }, selectedId: null };
    case "addDraftPoint":
      if (!state.draft) return state;
      return { ...state, draft: { ...state.draft, points: [...state.draft.points, action.point] } };
    case "finishDraft": {
      if (!state.draft || state.draft.points.length < MIN_POINTS) return state;
      const next = withHistory(state);
      const id = `added-${state.nextId}`;
      const region: Region = {
        id,
        kind: state.draft.kind,
        label: state.draft.kind,
        polygon: state.draft.points,
        source: "added",
        modelScore: null,
      };
      return {
        ...next,
        regions: [...next.regions, region],
        draft: null,
        selectedId: id,
        nextId: state.nextId + 1,
      };
    }
    case "cancelDraft":
      return { ...state, draft: null };
    case "undo": {
      if (state.history.length === 0) return state;
      const regions = state.history[state.history.length - 1];
      const selectedId = regions.some((r) => r.id === state.selectedId) ? state.selectedId : null;
      return { ...state, regions, history: state.history.slice(0, -1), selectedId };
    }
  }
}

export function midpoint([x1, y1]: Point, [x2, y2]: Point): Point {
  return [(x1 + x2) / 2, (y1 + y2) / 2];
}

export function countEdits(regions: Region[], original: Region[]): number {
  const removed = original.filter((o) => !regions.some((r) => r.id === o.id)).length;
  return removed + regions.filter((r) => r.source !== "model").length;
}
