"use client";

import { MIN_POINTS, type EditorAction } from "@/lib/editing";

export const BUTTON =
  "rounded-md bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-50";
export const BUTTON_SECONDARY =
  "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40";

export function EditToolbar(props: {
  editing: boolean;
  setEditing: (v: boolean) => void;
  selectedId: string | null;
  draftPoints: number | null;
  canUndo: boolean;
  dispatch: (action: EditorAction) => void;
}) {
  const { editing, dispatch, draftPoints, selectedId } = props;
  if (!editing) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => props.setEditing(true)} className={BUTTON}>
          Correct outlines
        </button>
        <span className="text-sm text-slate-500">
          Fix merged roofs, remove wrong areas or add missed obstacles.
        </span>
      </div>
    );
  }
  return (
    <div className="space-y-2 rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap gap-2">
        {draftPoints === null ? (
          <>
            <button
              type="button"
              className={BUTTON_SECONDARY}
              onClick={() => dispatch({ type: "startDraft", kind: "roof" })}
            >
              Add roof
            </button>
            <button
              type="button"
              className={BUTTON_SECONDARY}
              onClick={() => dispatch({ type: "startDraft", kind: "obstacle" })}
            >
              Add obstacle
            </button>
            <button
              type="button"
              className={BUTTON_SECONDARY}
              disabled={!selectedId}
              onClick={() => selectedId && dispatch({ type: "deleteRegion", id: selectedId })}
            >
              Delete selected
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className={BUTTON_SECONDARY}
              disabled={draftPoints < MIN_POINTS}
              onClick={() => dispatch({ type: "finishDraft" })}
            >
              Finish shape
            </button>
            <button
              type="button"
              className={BUTTON_SECONDARY}
              onClick={() => dispatch({ type: "cancelDraft" })}
            >
              Cancel
            </button>
          </>
        )}
        <button
          type="button"
          className={BUTTON_SECONDARY}
          disabled={!props.canUndo}
          onClick={() => dispatch({ type: "undo" })}
        >
          Undo
        </button>
        <button type="button" className={BUTTON} onClick={() => props.setEditing(false)}>
          Done
        </button>
      </div>
      <p className="text-xs text-slate-500">
        {draftPoints === null
          ? "Click an outline to select it. Drag its corners to move them, drag the small edge dots to add a corner, and double-click a corner to remove it. Delete removes the selected outline; Ctrl+Z undoes."
          : `Click on the image to place corners (${draftPoints} so far), then press Finish shape or Enter. Escape cancels.`}
      </p>
    </div>
  );
}
