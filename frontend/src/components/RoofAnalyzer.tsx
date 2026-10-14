"use client";

import { useEffect, useRef, useState } from "react";
import {
  ACCEPTED_IMAGE_TYPES,
  analyzeRoof,
  DEFAULT_EDGE_SETBACK_M,
  DEFAULT_OBSTACLE_CLEARANCE_M,
  validateImageFile,
  type Point,
  type RoofAnalysisResponse,
} from "@/lib/api";
import { MIN_POINTS, type EditorAction } from "@/lib/editing";
import { toImagePixels } from "@/lib/overlay";
import { nextReferenceLine, parseMargin, scaleFromForm, type ScaleMode } from "@/lib/scale";
import { AnalysisResults } from "./AnalysisResults";
import { RegionLayer } from "./RegionLayer";
import { useOutlineCorrection } from "./useOutlineCorrection";

type Request =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "done"; result: RoofAnalysisResponse }
  | { kind: "error"; message: string };

type Imagery = "top_down" | "oblique_or_ground" | null;

const BUTTON =
  "rounded-md bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-50";
const BUTTON_SECONDARY =
  "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40";

export function RoofAnalyzer() {
  const [file, setFile] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [imagery, setImagery] = useState<Imagery>(null);
  const [scaleMode, setScaleMode] = useState<ScaleMode>("gsd");
  const [gsdCm, setGsdCm] = useState("");
  const [line, setLine] = useState<{ start: Point | null; end: Point | null }>({
    start: null,
    end: null,
  });
  const [lengthM, setLengthM] = useState("");
  const [setback, setSetback] = useState(String(DEFAULT_EDGE_SETBACK_M));
  const [clearance, setClearance] = useState(String(DEFAULT_OBSTACLE_CLEARANCE_M));
  const [request, setRequest] = useState<Request>({ kind: "idle" });
  const [formError, setFormError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  const result = request.kind === "done" ? request.result : null;
  const correction = useOutlineCorrection(result);
  const { state: editor, dispatch } = correction;

  useEffect(() => {
    return () => {
      if (imageUrl) URL.revokeObjectURL(imageUrl);
    };
  }, [imageUrl]);

  useEffect(() => () => controllerRef.current?.abort(), []);

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

  function chooseFile(next: File | undefined) {
    if (!next) return;
    const invalid = validateImageFile(next);
    controllerRef.current?.abort();
    setRequest({ kind: "idle" });
    setEditing(false);
    setFormError(null);
    setLine({ start: null, end: null });
    if (invalid) {
      setFile(null);
      setImageUrl(null);
      setFileError(invalid);
      return;
    }
    setFileError(null);
    setFile(next);
    setNatural(null);
    setImageUrl(URL.createObjectURL(next));
  }

  const drawing = scaleMode === "reference_line" && imagery === "top_down" && !result;

  function handleImageClick(e: React.MouseEvent<HTMLElement>) {
    if (!drawing || !natural) return;
    const box = e.currentTarget.getBoundingClientRect();
    const point = toImagePixels(e.clientX, e.clientY, box, natural.w, natural.h);
    setLine((l) => nextReferenceLine(l.start, l.end, point));
  }

  function analyze() {
    if (!file) return;
    const scale = scaleFromForm({ mode: scaleMode, gsdCm, ...line, lengthM });
    const edgeSetbackM = parseMargin(setback, 5);
    const obstacleClearanceM = parseMargin(clearance, 3);
    if ("error" in scale) return setFormError(scale.error);
    if (edgeSetbackM === null) return setFormError("Edge setback must be between 0 and 5 m.");
    if (obstacleClearanceM === null) {
      return setFormError("Obstacle clearance must be between 0 and 3 m.");
    }
    setFormError(null);

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setRequest({ kind: "loading" });
    analyzeRoof(file, { scale: scale.scale, edgeSetbackM, obstacleClearanceM }, controller.signal)
      .then((res) => setRequest({ kind: "done", result: res }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setRequest({
          kind: "error",
          message: err instanceof Error ? err.message : "Analysis failed",
        });
      });
  }

  return (
    <div className="space-y-6">
      <label className="block rounded-lg border-2 border-dashed border-slate-300 p-6 text-center hover:border-teal-500">
        <span className="font-medium text-slate-800">
          {file ? "Choose a different image" : "Choose a rooftop image"}
        </span>
        <span className="mt-1 block text-sm text-slate-500">PNG or JPEG, up to 10 MB</span>
        <input
          type="file"
          accept={ACCEPTED_IMAGE_TYPES.join(",")}
          className="sr-only"
          onChange={(e) => {
            chooseFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </label>

      {!file && !fileError && (
        <p className="text-sm text-slate-500">
          Use a top-down aerial, drone or satellite image of the roof. You will be asked for its
          scale so areas can be measured in square metres.
        </p>
      )}

      {fileError && <Alert>{fileError}</Alert>}

      {imageUrl && (
        <figure
          className={`relative overflow-hidden rounded-lg border border-slate-200 ${drawing ? "cursor-crosshair" : ""}`}
          onClick={handleImageClick}
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- local blob URL */}
          <img
            src={imageUrl}
            alt="Uploaded rooftop"
            className="block h-auto w-full select-none"
            draggable={false}
            onLoad={(e) =>
              setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })
            }
          />
          {natural && result && (
            <RegionLayer
              width={natural.w}
              height={natural.h}
              regions={editor.regions}
              selectedId={editor.selectedId}
              draft={editor.draft}
              editing={editing}
              dispatch={dispatch}
            />
          )}
          {natural && !result && scaleMode === "reference_line" && line.start && (
            <svg
              viewBox={`0 0 ${natural.w} ${natural.h}`}
              preserveAspectRatio="none"
              className="pointer-events-none absolute inset-0 h-full w-full"
              aria-hidden="true"
            >
              <ReferenceLine start={line.start} end={line.end} />
            </svg>
          )}
          {request.kind === "loading" && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/60 text-sm font-medium text-slate-700">
              Analyzing roof…
            </div>
          )}
        </figure>
      )}

      {file && !result && (
        <section className="space-y-5 rounded-lg border border-slate-200 p-4">
          <fieldset>
            <legend className="text-sm font-semibold text-slate-800">
              1. What kind of image is this?
            </legend>
            <div className="mt-2 space-y-2 text-sm">
              <Choice
                name="imagery"
                checked={imagery === "top_down"}
                onChange={() => setImagery("top_down")}
                label="Top-down (aerial, drone or satellite, looking straight down)"
              />
              <Choice
                name="imagery"
                checked={imagery === "oblique_or_ground"}
                onChange={() => setImagery("oblique_or_ground")}
                label="Taken at an angle or from the ground"
              />
            </div>
          </fieldset>

          {imagery === "oblique_or_ground" && (
            <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
              Angled and ground-level photos can&apos;t be measured: perspective makes distant parts
              look smaller, so shapes and areas would be wrong. Please use a top-down image, for
              example a drone photo taken straight down.
            </p>
          )}

          {imagery === "top_down" && (
            <>
              <fieldset>
                <legend className="text-sm font-semibold text-slate-800">2. Image scale</legend>
                <div className="mt-2 space-y-2 text-sm">
                  <Choice
                    name="scale"
                    checked={scaleMode === "gsd"}
                    onChange={() => setScaleMode("gsd")}
                    label="I know the resolution"
                  />
                  <Choice
                    name="scale"
                    checked={scaleMode === "reference_line"}
                    onChange={() => setScaleMode("reference_line")}
                    label="I'll draw a line of known length on the image"
                  />
                </div>
                {scaleMode === "gsd" ? (
                  <NumberField
                    label="Resolution"
                    unit="cm per pixel"
                    value={gsdCm}
                    onChange={setGsdCm}
                    hint="Drone images are often 1–5 cm per pixel, aerial 5–15 cm, satellite 30–50 cm."
                  />
                ) : (
                  <div className="mt-3 space-y-2 text-sm text-slate-600">
                    <p>
                      Click two points on the image along an edge you know the length of, such as a
                      roof side or a wall.{" "}
                      {line.start && !line.end && "Now click the second point."}
                      {line.end && "Click again to redraw."}
                    </p>
                    <NumberField
                      label="Real length of the line"
                      unit="m"
                      value={lengthM}
                      onChange={setLengthM}
                    />
                  </div>
                )}
              </fieldset>

              <details className="text-sm">
                <summary className="cursor-pointer font-semibold text-slate-800">
                  3. Margins for usable area (optional)
                </summary>
                <div className="mt-2 grid gap-3 sm:grid-cols-2">
                  <NumberField
                    label="Edge setback"
                    unit="m"
                    value={setback}
                    onChange={setSetback}
                    hint="Space kept free along roof edges."
                  />
                  <NumberField
                    label="Obstacle clearance"
                    unit="m"
                    value={clearance}
                    onChange={setClearance}
                    hint="Space kept free around tanks and other obstacles."
                  />
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Defaults are placeholders; follow local rules and your installer&apos;s advice.
                </p>
              </details>

              {formError && <Alert>{formError}</Alert>}

              <button
                type="button"
                onClick={analyze}
                disabled={request.kind === "loading"}
                className="rounded-md bg-teal-700 px-4 py-2 font-medium text-white hover:bg-teal-800 disabled:opacity-50"
              >
                {request.kind === "loading" ? "Analyzing…" : "Analyze roof"}
              </button>
            </>
          )}
        </section>
      )}

      {request.kind === "error" && <Alert>{request.message}</Alert>}

      {result && (
        <EditToolbar
          editing={editing}
          setEditing={setEditing}
          selectedId={editor.selectedId}
          draftPoints={editor.draft ? editor.draft.points.length : null}
          canUndo={correction.canUndo}
          dispatch={dispatch}
        />
      )}

      {correction.measureError && <Alert>{correction.measureError}</Alert>}

      {correction.view && (
        <>
          <AnalysisResults view={correction.view} />
          <button
            type="button"
            onClick={() => {
              setEditing(false);
              setRequest({ kind: "idle" });
            }}
            className="text-sm font-medium text-teal-700 hover:underline"
          >
            Change scale or margins and analyze again (discards corrections)
          </button>
        </>
      )}
    </div>
  );
}

function EditToolbar(props: {
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

function ReferenceLine({ start, end }: { start: Point; end: Point | null }) {
  return (
    <g className="stroke-fuchsia-600" strokeWidth={3}>
      {end && (
        <line
          x1={start[0]}
          y1={start[1]}
          x2={end[0]}
          y2={end[1]}
          vectorEffect="non-scaling-stroke"
        />
      )}
      {[start, end].map(
        (p, i) =>
          p && (
            <circle
              key={i}
              cx={p[0]}
              cy={p[1]}
              r={4}
              className="fill-white"
              vectorEffect="non-scaling-stroke"
            />
          ),
      )}
    </g>
  );
}

function Choice(props: {
  name: string;
  checked: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <label className="flex items-start gap-2">
      <input
        type="radio"
        name={props.name}
        checked={props.checked}
        onChange={props.onChange}
        className="mt-1"
      />
      <span className="text-slate-700">{props.label}</span>
    </label>
  );
}

function NumberField(props: {
  label: string;
  unit: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
}) {
  return (
    <label className="mt-3 block text-sm">
      <span className="font-medium text-slate-700">{props.label}</span>
      <span className="mt-1 flex items-center gap-2">
        <input
          type="text"
          inputMode="decimal"
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
          className="w-28 rounded-md border border-slate-300 px-2 py-1"
        />
        <span className="text-slate-500">{props.unit}</span>
      </span>
      {props.hint && <span className="mt-1 block text-xs text-slate-500">{props.hint}</span>}
    </label>
  );
}

function Alert({ children }: { children: React.ReactNode }) {
  return (
    <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
      {children}
    </p>
  );
}
