"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  apiAsset,
  deleteAnalysis,
  getAnalysis,
  NotFoundError,
  type AnalysisRecord,
} from "@/lib/api";
import { AnalysisResults } from "./AnalysisResults";
import { BUTTON_SECONDARY, EditToolbar } from "./EditToolbar";
import { RegionLayer } from "./RegionLayer";
import { useOutlineCorrection, type SaveStatus } from "./useOutlineCorrection";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; record: AnalysisRecord }
  | { kind: "missing" }
  | { kind: "error"; message: string };

/** A saved analysis: image, editable outlines, results. */
export function AnalysisWorkspace({ id }: { id: string }) {
  const [load, setLoad] = useState<Load>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    getAnalysis(id, controller.signal)
      .then((record) => setLoad({ kind: "ready", record }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        if (err instanceof NotFoundError) setLoad({ kind: "missing" });
        else setLoad({ kind: "error", message: err instanceof Error ? err.message : String(err) });
      });
    return () => controller.abort();
  }, [id]);

  if (load.kind === "loading") return <p className="text-sm text-slate-500">Loading analysis…</p>;
  if (load.kind === "missing") {
    return (
      <p className="text-sm text-slate-600">
        This analysis does not exist or was deleted.{" "}
        <Link href="/analyze" className="text-teal-700 hover:underline">
          Start a new analysis
        </Link>
      </p>
    );
  }
  if (load.kind === "error") {
    return (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
        Could not load the analysis: {load.message}
      </p>
    );
  }
  return <Workspace record={load.record} />;
}

function Workspace({ record }: { record: AnalysisRecord }) {
  const router = useRouter();
  const correction = useOutlineCorrection(record);
  const { state: editor, dispatch } = correction;
  const [editing, setEditing] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const { width_px: width, height_px: height } = record.result.image;

  useEffect(() => {
    if (!editing) return;
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA"].includes(target.tagName)) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        dispatch({ type: "undo" });
      } else if ((e.key === "Delete" || e.key === "Backspace") && editor.selectedId) {
        e.preventDefault();
        dispatch({ type: "deleteRegion", id: editor.selectedId });
      } else if (e.key === "Enter" && editor.draft) {
        dispatch({ type: "finishDraft" });
      } else if (e.key === "Escape") {
        dispatch(editor.draft ? { type: "cancelDraft" } : { type: "select", id: null });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editing, editor.selectedId, editor.draft, dispatch]);

  async function remove() {
    if (!window.confirm("Delete this analysis and its stored image? This cannot be undone.")) {
      return;
    }
    try {
      await deleteAnalysis(record.id);
      router.push("/analyze");
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Could not delete the analysis");
    }
  }

  return (
    <div className="space-y-6">
      <figure className="relative overflow-hidden rounded-lg border border-slate-200">
        {/* eslint-disable-next-line @next/next/no-img-element -- served by the API */}
        <img
          src={apiAsset(record.image_url)}
          alt="Analysed rooftop"
          width={width}
          height={height}
          className="block h-auto w-full select-none"
          draggable={false}
        />
        <RegionLayer
          width={width}
          height={height}
          regions={editor.regions}
          selectedId={editor.selectedId}
          draft={editor.draft}
          editing={editing}
          dispatch={dispatch}
        />
      </figure>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <EditToolbar
          editing={editing}
          setEditing={setEditing}
          selectedId={editor.selectedId}
          draftPoints={editor.draft ? editor.draft.points.length : null}
          canUndo={correction.canUndo}
          dispatch={dispatch}
        />
        <SaveIndicator status={correction.status} />
      </div>

      {correction.saveError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          Your latest change was not saved: {correction.saveError}
        </p>
      )}

      <AnalysisResults view={correction.view} />

      <div className="flex flex-wrap gap-3 border-t border-slate-200 pt-4">
        <Link href="/analyze" className={BUTTON_SECONDARY}>
          New analysis
        </Link>
        <button type="button" onClick={remove} className={BUTTON_SECONDARY}>
          Delete analysis
        </button>
      </div>
      {deleteError && (
        <p role="alert" className="text-sm text-red-700">
          {deleteError}
        </p>
      )}
      <p className="text-xs text-slate-400">
        Anyone with this page&apos;s link can view and edit this analysis until accounts are added.
        Saved {new Date(record.created_at).toLocaleString()}.
      </p>
    </div>
  );
}

function SaveIndicator({ status }: { status: SaveStatus }) {
  const text = { saved: "All changes saved", saving: "Saving…", error: "Not saved" }[status];
  const color = status === "error" ? "text-red-700" : "text-slate-500";
  return (
    <span className={`text-sm ${color}`} role="status" aria-live="polite">
      {text}
    </span>
  );
}
